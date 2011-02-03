from difflib import unified_diff

class Diff(object):
    def __init__(self, a, b, fromfile=None, tofile=None, fromfile_revision=None, tofile_revision=None):
        self.a = a.splitlines()
        self.b = b.splitlines()
        self.fromfile = fromfile
        self.tofile = tofile
        self.fromfile_revision = fromfile_revision
        self.tofile_revision = tofile_revision
    
    @property
    def udiff(self):
        return "\n".join(unified_diff(self.a, self.b,
            fromfile=self.fromfile,
            tofile=self.tofile, 
            fromfiledate="(%s)" % self.fromfile_revision, 
            tofiledate="(%s)" % self.tofile_revision, 
            lineterm="",
        ))
    
    def __unicode__(self):
        return self.udiff