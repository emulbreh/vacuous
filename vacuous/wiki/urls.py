from django.conf.urls.defaults import *
from django.conf import settings
from vacuous.backends.dulwich.views import GitServer
from vacuous.backends import load_backend

SLUG = r'[a-zA-Z0-9/_.-]+'

class GitServ(GitServer):
    def get_backend_or_404(self, request, **kwargs):
        return load_backend(settings.VACUOUS_WIKI_REPO_FLAVOR, settings.VACUOUS_WIKI_REPO_PATH)
        
    def authenticate(self, request, user, password, **kwargs):
        return user == 'foo' and password == 'bar'
        

git_server = GitServ()

urlpatterns = patterns('',
    url(r'^$', 'django.views.generic.simple.redirect_to', {'url': '/wiki/'}),
    url(r'^wiki/$', 'vacuous.wiki.views.page_list'),
    url(r'^wiki/(?P<slug>%s)$' % SLUG, 'vacuous.wiki.views.view_page'),
    url(r'^wiki/(?P<slug>%s)~$' % SLUG, 'vacuous.wiki.views.edit_page'),
    url(r'^history/(?P<slug>%s)$' % SLUG, 'vacuous.wiki.views.page_history'),
    url(r'^git/(?P<repo_name>wiki)\.git/', include(git_server.get_urls())),
)

if settings.DEVELOPMENT:
    urlpatterns += patterns('', 
        url(r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': '/Users/emulbreh/Projekte/Verlag/pbbx.net/lib/djff/static'}),
    )
    