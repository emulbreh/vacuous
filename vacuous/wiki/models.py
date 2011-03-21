from django.db import models
from django.conf import settings

from vacuous.adapters import Adapter


class Page(models.Model):
    slug = models.CharField(max_length=100, db_index=True)
    text = models.TextField()


class PageAdapter(Adapter):
    flavor = settings.VACUOUS_WIKI_REPO_FLAVOR
    repo = settings.VACUOUS_WIKI_REPO_PATH
    branch = 'master'
    
    path = Adapter.proxy('slug')
    data = Adapter.proxy('text')
    revision = Adapter.proxy('revision')
    
    @classmethod
    def filter(cls, qs, paths=None, branch=None):
        if paths is not None:
            return qs.filter(slug__in=paths)
        return qs
    

PageAdapter.register(Page)