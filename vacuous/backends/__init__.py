import threading
from django.conf import settings
from django.utils.importlib import import_module
from django.core.signals import request_finished

_cache = threading.local()

def __init():
    if not hasattr(_cache, 'backends'):
        _cache.backends = {}

def load_backend(flavor, path, cache=True):
    __init()
    key = (flavor, path)
    if key not in _cache.backends or not cache:
        import_path = getattr(settings, 'VACUOUS_BACKENDS')[flavor]
        module_path, cls_name = import_path.rsplit('.', 1)
        cls = getattr(import_module(module_path), cls_name)
        backend = cls(path)
        backend.flavor = flavor
        if not cache:
            return backend
        _cache.backends[key] = backend
    return _cache.backends[key]
    

def purge_backend_cache():
    __init()
    _cache.backends = {}


def iter_cached_backends():
    __init()
    return _cache.backends.itervalues()
    
request_finished.connect(lambda sender, **kwargs: purge_backend_cache())

    