import datetime

from vacuous.backends.base import BaseCommit
from vacuous.backends.dulwich.utils import tree_diff


class TZ(datetime.tzinfo):
    def __init__(self, offset):
        self.__offset = datetime.timedelta(seconds=offset)

    def utcoffset(self, dt):
        return self.__offset

    def tzname(self, dt):
        return "+%02i%02i" % divmod(self.__offset.seconds // 60, 60)

    def dst(self, dt):
        return datetime.timedelta(0)


def make_datetime(timestamp, tz):
    return datetime.datetime.fromtimestamp(timestamp, TZ(tz))


class DulwichCommit(BaseCommit):
    def __init__(self, backend, commit):
        self._commit = commit
        super(DulwichCommit, self).__init__(backend)
    
    @property
    def revision(self):
        return self._commit.id
    
    @property
    def parent_revision(self):
        return self._commit.parents[0] if self._commit.parents else self.backend.null_revision
    
    @property
    def author_time(self):
        if not hasattr(self, '_author_time'):
            self._author_time = make_datetime(self._commit.author_time, self._commit.author_timezone)
        return self._author_time

    @property
    def commit_time(self):
        if not hasattr(self, '_commit_time'):
            self._commit_time = make_datetime(self._commit.commit_time, self._commit.commit_timezone)
        return self._commit_time

    def __getattribute__(self, attr):
        if attr in ('committer', 'message', 'author'):
            return getattr(self._commit, attr)
        return super(DulwichCommit, self).__getattribute__(attr)
    
    @property
    def paths(self):
        if not hasattr(self, '_paths'):
            repo = self.backend.repo
            commit = repo[self.revision]
            parent_tree = repo[commit.parents[0]].tree if commit.parents else None
            self._paths = list(tree_diff(repo, commit.tree, parent_tree))
        return self._paths
