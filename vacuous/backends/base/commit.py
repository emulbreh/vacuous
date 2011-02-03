from vacuous.exceptions import FileDoesNotExist
from vacuous.diffs import Diff


class BaseCommit(object):
    def __init__(self, backend, **kwargs):
        self.backend = backend
        for name, value in kwargs.iteritems():
            setattr(self, name, value)
            
    def _get_diff(self, path):
        fromfile, tofile = path, path
        try:
            a, fromfile = self.backend.read(path, revision=self.parent_revision), path
        except FileDoesNotExist:
            a, fromfile = '', '/dev/null'
        try:
            b, tofile = self.backend.read(path, revision=self.revision), path
        except FileDoesNotExist:
            b, tofile = '', '/dev/null'
        return Diff(a, b, fromfile=fromfile, tofile=tofile, fromfile_revision=self.parent_revision, tofile_revision=self.revision)
        
    def __getitem__(self, path):
        if not path in self.paths:
            raise KeyError(path)
        return self._get_diff(path)
        
    def diffs(self):
        for path in self.paths:
            yield self._get_diff(path)
    
    @property
    def udiff(self):
        return "\n".join(diff.udiff for diff in self.diffs())
        
        