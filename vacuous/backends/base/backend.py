import os
import hashlib

from django.utils.functional import wraps

from vacuous.exceptions import FileDoesNotExist
from vacuous.constants import WRITE, RENAME, DELETE
from vacuous.tasks import CommitTask


class CommitOnSuccess(object):
    def __init__(self, backend, kwargs):
        self.backend = backend
        self.kwargs = kwargs

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.backend.rollback()
        else:
            self.backend.commit(**self.kwargs)

    def __call__(self, func):
        @wraps(func)
        def decorated(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return decorated


class BaseBackend(object):
    default_encoding = 'utf-8'
    default_branch = None
    null_revision = 'null'

    def __init__(self, path, committer_name=None, committer_email=None):
        self.path = path
        self.committer_name = committer_name
        self.committer_email = committer_email
        self.changes = {}
    
    @property
    def committer(self):
        if self.committer_name is not None:
            if self.committer_email is not None:
                return "%s <%s>" % (self.committer_name, self.committer_email)
            else:
                return self.committer_name
        elif self.committer_email is not None:
            return "<%s>" % self.committer_email
        else:
            return None
    
    def is_dirty(self):
        return bool(self.changes)
        
    def write(self, path, data, **kwargs):
        encoding = kwargs.pop('encoding', self.default_encoding)
        if encoding:
            data = data.encode(encoding)
        self.changes[path] = (WRITE, data)

    def delete(self, path):
        self.changes[path] = (DELETE, None)

    def rename(self, old_path, new_path):
        self.changes[new_path] = self.changes.get(old_path, (RENAME, old_path))
        
    def rollback(self):
        self.changes.clear()
    
    def commit_on_success(self, **kwargs):
        return CommitOnSuccess(self, kwargs)
        
    def commit(self, message='', force=False, **kwargs):
        if not self.is_dirty() and not force:
            return
        kwargs['message'] = message
        kwargs.setdefault('branch', self.default_branch)
        result = CommitTask.apply_async(
            args=[self.flavor, self.path, self.changes, kwargs],
            routing_key='vacuous.repo.%s.commit' % self.flavor,
        )
        self.changes.clear()
        return result.wait()
        
    def read(self, path, **kwargs):
        encoding = kwargs.pop('encoding', self.default_encoding)
        data = self.do_read(path, **kwargs)
        if encoding:
            data = data.decode(encoding)
        return data
    
    ## backend specific
    
    def history(self, path=None, revision=None, branch=None):
        raise NotImplementedError
        
    def revision(self, revision=None, branch=None):
        raise NotImplementedError

    def do_read(self, path, **kwargs):
        raise NotImplementedError

    def do_commit(self, message='', **kwargs):
        raise NotImplementedError
    
    def create_branch(self, name, revision=None):
        raise NotImplementedError
        
    def delete_branch(self):
        raise NotImplementedError

    def rename_branch(self, old_name, new_name):
        raise NotImplementedError
        
    def has_branch(self):
        raise NotImplementedError
        
    def init_repo(self):
        raise NotImplementedError
        
    def delete_repo(self):
        raise NotImplementedError
        