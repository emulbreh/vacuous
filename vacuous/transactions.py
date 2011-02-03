from vacuous.backends import iter_cached_backends

class commit_on_success(object):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            for backend in iter_cached_backends():
                backend.rollback()
        else:
            for backend in iter_cached_backends():
                backend.commit(**self.kwargs)

    def __call__(self, func):
        @wraps(func)
        def decorated(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return decorated
