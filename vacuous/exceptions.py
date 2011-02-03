
class BackendError(Exception):
    def __init__(self, backend, *args, **kwargs):
        self.backend = backend
        super(Exception, self).__init__(*args, **kwargs)

class FileDoesNotExist(BackendError): pass
class BranchDoesNotExist(BackendError): pass
class BranchDoesAlreadyExist(BackendError): pass
class CommitDoesNotExist(BackendError): pass
