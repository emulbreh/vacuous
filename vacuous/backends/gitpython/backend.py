import os
import shutil
from StringIO import StringIO
from contextlib import contextmanager
from git import Repo, Blob, BaseIndexEntry
from gitdb import IStream

from vcs_sync.backends.base import BaseBackend, WRITE, RENAME, DELETE

@contextmanager
def ENV(**bind):
    env = os.environ
    original = {}
    for var, val in bind.iteritems():
        if var in env:
            original[var] = env[var]
            if val is None:
                del env[var]
        if val is not None:
            env[var] = val
    try:
        yield
    finally:
        for var in bind.iterkeys():
            if var in original:
                env[var] = original[var]
            elif var in env:
                del env[var]


class Backend(BaseBackend):
    file_mode = 0100644
    #directory_mode = 
    
    @property
    def repo(self):
        if not hasattr(self, '_repo'):
            self._repo =  Repo(self.path)
        return self._repo

    def init_repo(self):
        self._repo = Repo.init(path=self.path, bare=True)
        
    def delete_repo(self):
        shutil.rmtree(self.path)
        
    def has_branch(self, name):
        return any(lambda h: h.name == "refs/heads/%s" % name, self.repo.heads)
        
    def create_branch(self, name):
        self.repo.create_head(name)
        
    def delete_branch(self, name):
        self.repo.delete_head(name)

    def commit(self, message='', branch='master', parent=None, **kwargs):
        repo = Repo(self.path)
        index = repo.index

        for path, (action, data) in self.changes.iteritems():
            abspath = os.path.join(self.path, path)
            if action == WRITE:
                istream = IStream(Blob.type, len(data), StringIO(data))
                repo.odb.store(istream)
                blob = Blob(repo, istream.binsha, self.file_mode, path)
                index.entries[(path, 0)] = BaseIndexEntry.from_blob(blob)
                
            elif action == DELETE:
                #for bit in path.split(os.path.sep):
                self.repo.git.rm(['--cached', '--'], [path], r=True)

            elif action == RENAME:
                #print self.repo.git.status()
                self.repo.git.rm(['--cached', '--'], [data], r=True)
                data = self.read(data)
                istream = IStream(Blob.type, len(data), StringIO(data))
                repo.odb.store(istream)
                blob = Blob(repo, istream.binsha, self.file_mode, path)
                index.entries[(path, 0)] = BaseIndexEntry.from_blob(blob)
        
        committer_name = kwargs.get('committer_name', self.committer_name)
        committer_email = kwargs.get('committer_email', self.committer_email)
        author_name = kwargs.get('author_name', self.committer_name)
        author_email = kwargs.get('author_email', self.committer_email)
        
        with ENV(GIT_AUTHOR_NAME=author_name, GIT_AUTHOR_EMAIL=author_email, GIT_COMMITTER_EMAIL=committer_email, GIT_COMMITTER_NAME=committer_name):
            commit = index.commit(message)
        
        self.changes = {}
        
        return commit.hexsha
            
    def read(self, path, revision=None, encoding='utf-8'):
        tree = self.repo.tree(revision or self.repo.heads.master.commit.hexsha)
        for bit in path.split(os.path.sep):
            tree = tree/bit
        data = tree.data_stream.read()
        if encoding:
            data = data.decode(encoding)
        return data


