from django.db.models.signals import post_save, post_init, pre_delete
from django.db.models import Q

from vacuous.backends import load_backend
from vacuous.exceptions import FileDoesNotExist, BranchDoesNotExist
from vacuous.signals import post_sync

_adapters = set()

def iter_adapters(flavor=None):
    from django.db.models.loading import get_models
    # force models to be loaded
    get_models()
    print "loaded adapters", _adapters
    for adapter in _adapters:
        if flavor is None or adapter.flavor == flavor:
            yield adapter


class AdapterDescriptor(object):
    def __init__(self, adapter_cls):
        self.adapter_cls = adapter_cls

    def __get__(self, instance, model):
        if instance is None:
            return self.adapter_cls
        return self.adapter_cls(instance)


class AdapterBase(type):
    _required_properties = (
        ('flavor', False), ('repo', False), ('branch', False), 
        ('path', True), ('revision', True), ('data', True),
    )

    def __new__(cls, name, bases, attrs):
        newcls = super(AdapterBase, cls).__new__(cls, name, bases, attrs)
        
        if newcls.__module__ != cls.__module__:
            for name, writable in cls._required_properties:
                if hasattr(newcls, name):
                    continue
                getter_name, setter_name = 'get_%s' % name, 'set_%s' % name
                getter, setter = getattr(newcls, getter_name), getattr(newcls, setter_name, None)

                assert getter != getattr(Adapter, getter_name), "Adapter subclasses must provide a `%s` property or a %s() method" % (name, getter_name)
                if writable:
                    assert setter != getattr(Adapter, setter_name), "Adapter subclasses must provide a `%s` property or a %s() method" % (name, setter_name)
                
                attrs[name] = property(getter, setter)
            _adapters.add(newcls)
            
        return newcls
        
    def register(cls, model, descriptor='vacuous'):
        post_save.connect(cls.post_save, sender=model)
        pre_delete.connect(cls.pre_delete, sender=model)
        post_init.connect(cls.post_init, sender=model)
        cls.models.add(model)
        if descriptor is not None:
            setattr(model, descriptor, AdapterDescriptor(cls))
            
    def update_state(cls, obj):
        adapter = cls(obj)
        setattr(obj, adapter.stateattr, adapter.path)
        
    def post_init(cls, sender, **kwargs):
        cls.update_state(kwargs['instance'])

    def post_save(cls, sender, **kwargs):
        obj, created = kwargs['instance'], kwargs['created']
        adapter = cls(obj)
        if not adapter.is_active():
            return

        backend = adapter.get_backend()

        old_path, old_data = getattr(obj, adapter.stateattr, None), None
        new_path, new_data = adapter.path, adapter.data
        renamed = old_path and old_path != new_path

        if old_path:
            try:
                old_data = backend.read(old_path, branch=adapter.branch)
            except (FileDoesNotExist, BranchDoesNotExist):
                pass

        if not new_path:
            if old_path:
                backend.delete(old_path)
        elif old_data != new_data:
            adapter.write()
            if renamed:
                backend.delete(old_path)
        elif renamed:
            backend.rename(old_path, new_path)

        cls.update_state(obj)


    def pre_delete(cls, sender, **kwargs):
        adapter = cls(kwargs['instance'])
        if adapter.is_active():
            adapter.delete()
            
    def get_paths_q(cls, paths):
        return Q(**{"%s__in" % self.path_attr: paths})
        
    def filter(cls, queryset, paths=None, branch=None):
        raise NotImplementedError()

    def iter_objects(cls, paths=None, branch=None):
        for model in cls.models:
            for obj in cls.filter(model.objects.all(), paths=paths, branch=branch):
                yield obj
                
    def proxy(cls, attr):
        return property(
            lambda self: getattr(self.obj, attr), 
            lambda self, value: setattr(self.obj, attr, value),
        )


class Adapter(object):
    __metaclass__ = AdapterBase
    models = set()
    stateattr = '_vacuous_state'
    proxies = {}
    encoding = 'utf-8'
    
    def __init__(self, obj):
        if type(obj) not in type(self).models:
            raise TypeError("%s is not registered for type %s" % (type(self), type(obj)))
        self.obj = obj

    ## repo properties

    def get_flavor(self):
        return self.flavor

    def get_repo(self, obj):
        return self.repo
        
    def get_branch(self, obj):
        return self.branch
        
    def get_encoding(self):
        return self.encoding
        
    def get_path(self):
        return self.path
        
    def set_path(self, path):
        self.path = path
        
    def get_revision(self):
        return self.revision
        
    def set_revision(self, revision):
        self.revision = revision
        
    def get_data(self):
        return self.data
        
    def set_data(self, data):
        self.data = data

    ## utility methods ##
    def is_active(self):
        return self.flavor and self.repo and self.path
    
    def get_backend(self, cached=True):
        if not self.flavor or not self.path:
            return None
        return load_backend(self.flavor, self.repo)
        
    def read(self, revision=None):
        if revision is None:
            revision = self.revision
        self.get_backend().read(self.path, revision)
        
    def write(self, data=None):
        if data is None:
            data = self.data
        self.get_backend().write(self.path, data)
        
    def delete(self):
        self.get_backend().delete(self.path)
        
    def sync(self, commit):
        backend = self.get_backend()
        self.set_data(backend.read(self.path, revision=commit.revision))
        self.obj.save()
        post_sync.send_robust(
            sender=type(self.obj), 
            adapter=self, 
            instance=self.obj, 
            commit=commit,
        )
    
    def history(self):
        return self.get_backend().history(path=self.path)
