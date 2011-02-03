import hashlib

from celery.task import Task
from django.core.cache import cache

from vacuous.backends import load_backend
from vacuous.adapters import iter_adapters
from vacuous.signals import post_sync


class CommitTask(Task):
    def run(self, flavor, repo_path, changes, kwargs, **info):
        lock_key = hashlib.sha1("%s#%s#%s" % (flavor, repo_path, kwargs['branch']))
        backend = load_backend(flavor, repo_path)
        backend.changes = changes
        commit = backend.do_commit(**kwargs)
        return commit.revision


class SyncTask(Task):
    def run(self, flavor, repo_path, oldrev, newrev, name):
        backend = load_backend(flavor, repo_path, cache=False)

        commit_map = {}
        for commit in backend.history(revision=newrev, since_revision=oldrev):
            print commit
            for path in commit.paths:
                commit_map.setdefault(path, commit)
        
        paths = commit_map.keys()
        print commit_map
        for adapter in iter_adapters(flavor=flavor):
            for obj in adapter.iter_objects(paths=paths):
                print "syncing object", obj
                a = adapter(obj)
                a.sync(commit_map[a.path])
                
        