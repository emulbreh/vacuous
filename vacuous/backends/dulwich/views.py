import re
import os
from base64 import b64decode
from StringIO import StringIO
from gzip import GzipFile
from functools import wraps

from django.http import HttpResponse, HttpResponseNotFound, HttpResponseForbidden, HttpResponseServerError, HttpResponseRedirect, Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.core.urlresolvers import reverse
from django.conf.urls.defaults import url, patterns
from django.conf import settings

from dulwich.web import HTTPGitRequest, get_text_file, get_info_refs, get_info_packs, get_loose_object, get_pack_file, get_idx_file
from dulwich.protocol import ReceivableProtocol
from dulwich.server import DEFAULT_HANDLERS, UploadPackHandler

from vacuous.backends.dulwich.utils import WebBackend
from vacuous.backends.dulwich.tasks import ReceivePackTask
from vacuous.signals import post_push


_http_basic_auth_re = re.compile(r'^basic ([a-z0-9+/=]+)$', re.IGNORECASE)

class GitServer(object):
    def authenticate(self, request, username, password, **kwargs):
        return settings.DEBUG
    
    def get_backend_or_404(self, request, **kwargs):
        raise NotImplementedError()
        
    def realm(self, request, **kwargs):
        return os.path.basename(kwargs['backend'].path)
        
    def wrap(self, view):
        @wraps(view)
        def wrapped(request, **kwargs):
            kwargs['backend'] = self.get_backend_or_404(request, **kwargs)
            response = None
            match = _http_basic_auth_re.match(request.META.get('HTTP_AUTHORIZATION', ''))
            if match:
                try:
                    username, password = b64decode(match.group(1)).split(':')
                except (ValueError, TypeError):
                    pass
                else:
                    if self.authenticate(request, username, password, **kwargs):
                        response = view(request, **kwargs)
            if not response:
                response = HttpResponse(status=401)
                response['WWW-Authenticate'] = 'Basic realm="%s"' % self.realm(request, **kwargs)
            return response
        return wrapped
    
    def get_url(self, **kwargs):
        return reverse(self.info, kwargs=kwargs)[:-1]
    
    def info(self, request, **kwargs):
        return HttpResponse('git clone %s' % request.build_absolute_uri(request.path[:-1]), content_type='text/plain')
    
    def get_urls(self):
        return patterns('',
            url(r'^$', self.info),
            url(r'^(?P<path>HEAD)$', self.wrap(serve_text_file)),
            url(r'^(?P<path>objects/info/alternates)$', self.wrap(serve_text_file)),
            url(r'^(?P<path>objects/info/http-alternates)$', self.wrap(serve_text_file)),
            url(r'^info/refs$', self.wrap(info_refs)),
            url(r'^objects/info/packs$', self.wrap(objects_info_packs)),
            url(r'^objects/(?P<hexsha_hi>[0-9a-f]{2})/(?P<hexsha_lo>[0-9a-f]{38})$', self.wrap(loose_object)),
            url(r'^(?P<path>objects/pack/pack-[0-9a-f]{40}\.pack)$', self.wrap(objects_pack_pack)),
            url(r'^(?P<path>objects/pack/pack-[0-9a-f]{40}\.idx)$', self.wrap(objects_pack_idx)),
            url(r'^git-upload-pack$', self.wrap(git_upload_pack)),
            url(r'^git-receive-pack$', self.wrap(git_receive_pack)),
        )


def require_ssl(view):
    @wraps(view)
    def with_ssl(request, *args, **kwargs):
        if not settings.DEBUG and not request.is_secure():
            return HttpResponseRedirect(request.build_absolute_uri().replace('http://', 'https://'))
        return view(request, *args, **kwargs)
    return with_ssl


def gitview(method, cache=None, ssl=None, push=False):
    def decorator(func):
        @require_http_methods([method])
        @wraps(func)
        def decorated(request, *args, **kwargs):
            try:
                return func(request, *args, **kwargs)
            except Exception as e:
                print e
                raise
        if cache is False:
            decorated = never_cache(decorated)
        if ssl:
            decorated = require_ssl(decorated)
        decorated.push = push
        return decorated
    return decorator


@gitview('GET', cache=False)
def serve_text_file(request, backend=None, path=None, **kwargs):
    repo = backend.repo
    return HttpResponse(repo.get_named_file(path), content_type='text/plain')


@gitview('GET', cache=True)
def loose_object(request, backend=None, hexsha_hi=None, hexsha_lo=None, **kwargs):
    repo = backend.repo
    hexsha = "%s%s" % (hexsha_hi, hexsha_lo)
    if not repo.object_store.contains_loose(hexsha):
        return HttpResponseNotFound('Object not found')
    try:
        return HttpResponse(repo.object_store[hexsha].as_legacy_object(), content_type='application/x-git-loose-object')
    except IOError:
        return HttpResponseServerError('Error reading object')


@gitview('GET', cache=True)
def objects_pack_pack(request, backend=None, path=None, **kwargs):
    return HttpResponse(backend.repo.get_named_file(path), content_type='application/x-git-packed-objects')


@gitview('GET', cache=True)
def objects_pack_idx(request, backend=None, path=None, **kwargs):
    return HttpResponse(backend.repo.get_named_file(path), content_type='application/x-git-packed-objects-toc')
    

@gitview('GET', cache=False)
def objects_info_packs(request, backend=None, **kwargs):
    response = HttpResponse(content_type='text/plain')
    for pack in backend.repo.object_store.packs:
        reponse.write('P pack-%s.pack\n' % pack.name())
    return response


@gitview('GET', cache=False)
def info_refs(request, backend=None, **kwargs):
    repo = backend.repo
    service = request.GET.get('service', None)
    if service:
        if service not in DEFAULT_HANDLERS:
            return HttpResponseForbidden('Unsupported service %s' % service)

        handler_cls = DEFAULT_HANDLERS[service]
        response = HttpResponse(content_type='application/x-%s-advertisement' % service)
        proto = ReceivableProtocol(StringIO().read, response.write)
        handler = handler_cls(WebBackend(), [backend], proto, stateless_rpc=True, advertise_refs=True)
        handler.proto.write_pkt_line('# service=%s\n' % service)
        handler.proto.write_pkt_line(None)
        handler.handle()
    else:
        response = HttpResponse(content_type='text/plain')
        refs = repo.get_refs()
        for name in sorted(refs.iterkeys()):
            if name == 'HEAD':
                continue
            hexsha = refs[name]
            o = repo[hexsha]
            if not o:
                continue
            response.write('%s\t%s\n' % (hexsha, name))
            peeled_sha = repo.get_peeled(name)
            if peeled_sha != hexsha:
                response.write('%s\t%s^{}\n' % (peeled_sha, name))
    return response


class PatchedUploadPackHandler(UploadPackHandler):
    def progress(self, msg):
        return
        if msg in ("dul-daemon says what\n", "how was that, then?\n"):
            return
        super(PatchedUploadPackHandler, self).progress(msg)
        
    #@classmethod
    #def capabilities(cls):
    #    return ("multi_ack", "side-band-64k", "thin-pack", "ofs-delta", "no-progress", "include-tag")

        

@gitview('POST', cache=False)
def git_upload_pack(request, backend=None, **kwargs):
    response = HttpResponse(content_type='application/x-git-upload-pack-response')
    
    if request.META.get('HTTP_CONTENT_ENCODING') == 'gzip':
        unzipped = GzipFile(mode='r', fileobj=StringIO(request.read()))
        unzipped.seek(0)
        read = unzipped.read
    else:
        read = request.read
    
    proto = ReceivableProtocol(read, response.write)
    handler = PatchedUploadPackHandler(WebBackend(), [backend], proto, stateless_rpc=True)
    handler.handle()
    return response


@gitview('POST', cache=False, ssl=True, push=True)
def git_receive_pack(request, backend=None, **kwargs):
    result = ReceivePackTask.apply_async(args=[backend.flavor, backend.path, request.read()])
    data, refs = result.wait()
    post_push.send_robust(sender=type(backend), backend=backend, refs=refs)
    return HttpResponse(data, content_type='application/x-git-receive-pack-response')
