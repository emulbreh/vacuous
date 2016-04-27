import os
import stat
import time
import shutil
import datetime
from operator import itemgetter, attrgetter

from dulwich.objects import Commit, Blob, Tree
from dulwich.repo import Repo

from vacuous.backends.base import BaseBackend
from vacuous.exceptions import FileDoesNotExist, BranchDoesNotExist, BranchDoesAlreadyExist, CommitDoesNotExist
from vacuous.constants import WRITE, RENAME, DELETE

from vacuous.backends.dulwich.utils import clean_path, iter_blob_paths, tree_diff, get_by_path, is_same_object
from vacuous.backends.dulwich.commit import DulwichCommit


class Backend(BaseBackend):
    default_branch = 'master'
    null_revision = 'null'
    file_mode = 0100644
    directory_mode = 040755

    @property
    def repo(self):
        if not hasattr(self, '_repo'):
            self._repo = Repo(self.path)
        return self._repo
        
    def _get_commit(self, revision=None, branch=None):
        repo = self.repo
        if not revision:
            try:
                revision = repo.refs['refs/heads/%s' % branch]
            except KeyError:
                raise BranchDoesNotExist(self, branch)
        elif isinstance(revision, DulwichCommit):
            revision = revision.revision
        try:
            commit = repo[revision]
            if not isinstance(commit, Commit):
                raise CommitDoesNotExist(self, revision)
            return commit
        except KeyError:
            raise CommitDoesNotExist(self, revision)
    
    def _collect(self, tree, path, cache=None):
        result = [(None, None, tree)]
        bits = filter(None, path.split(os.path.sep))
        repo = self.repo
        for i, bit in enumerate(bits):
            found = False
            for mode, name, hexsha in tree.items():
                if name == bit:
                    found = True
                    if cache and hexsha in cache:
                        tree = cache[hexsha]
                    else:
                        tree = repo[hexsha]
                    result.append((mode, name, tree))
                    break
            if not found:
                result += [(self.directory_mode, bit, Tree()) for bit in bits[i:]]
                break
        return result
        
    def _link(self, seq):
        cache = {}
        for i in xrange(len(seq) - 1, -1, -1):
            mode, name, obj = seq[i]
            cache[obj.id] = obj
            if i > 0:
                seq[i - 1][2][name] = (mode, obj.id)
        return cache
        
    ### repo ###

    def init_repo(self):
        if os.path.exists(self.path):
            return
        os.mkdir(self.path)
        self._repo = Repo.init_bare(self.path)
        
    def delete_repo(self):
        shutil.rmtree(self.path)
        
    ### branches ###

    def has_branch(self, name):
        return 'refs/heads/%s' % name in self.repo.refs
        
    def create_branch(self, name, revision=None):
        if self.has_branch(name):
            raise BranchDoesAlreadyExist(self, name)
        self.repo.refs['refs/heads/%s' % name] = self._get_commit(revision, 'master').id
        
    def delete_branch(self, name):
        try:
            del self.repo.refs['refs/heads/%s' % name]
        except KeyError:
            raise BranchDoesNotExist(self, name)
        
    def rename_branch(self, old_name, new_name):
        if old_name == new_name:
            return
        if not self.has_branch(old_name):
            raise BranchDoesNotExist(self, old_name)
        if self.has_branch(new_name):
            raise BranchDoesAlreadyExist(new_name)
        self.create_branch(new_name, 'refs/heads/%s' % old_name)
        self.delete_branch(old_name)
    
    ### api ###
    
    def revision(self, revision=None, branch='master'):
        return DulwichCommit(self, self._get_commit(revision, branch))
        
    def _walk(self, path, tree):
        repo = self.repo
        blobs, subtrees = [], []
        for mode, name, hexsha in tree.items():
            if stat.S_ISREG(mode):
                blobs.append(name)
            elif stat.S_ISDIR(mode):
                subtrees.append(name)
        yield (path, subtrees, blobs)
        for name in subtrees:
            mode, hexsha = tree[name]
            for t in self._walk(os.path.join(path, name), repo[hexsha]):
                yield t
        
    def walk(self, path, revision=None, branch='master'):
        root = repo[self._get_commit(revision, branch).tree]
        return self._walk(path, root)
    
    def history(self, path=None, revision=None, branch='master', since_revision=None, since=None, sort=True):
        if revision == self.null_revision:
            return []

        if path is not None:
            path = clean_path(path)
        
        if since_revision:
            ctime = self.revision(since_revision).commit_time
            if since:
                since = max(ctime, since)
            else:
                since = ctime
                
        if revision or branch:
            pending = set([self._get_commit(revision, branch).id])
        else:
            pending = set(self._repo.get_refs().values())

        visited = set()
        result = []
        repo = self.repo

        while pending:
            commit_id = pending.pop()
            commit = self.revision(commit_id)
            
            if commit_id in visited:
                continue
            visited.add(commit_id)
            
            if since and since > commit.commit_time:
                continue

            if commit_id != since_revision:
                pending.update(commit._commit.parents)
                
            if path:
                tree = repo[commit._commit.tree]
                found = False
                parents = commit._commit.parents
                for parent in parents:
                    parent_tree = repo[repo[parent].tree]
                    if not is_same_object(repo, tree, parent_tree, path):
                        found = True
                        break
                if not parents and get_by_path(repo, tree, path):
                    found = True
                if not found:
                    continue
            result.append(commit)
        if sort:
            result.sort(key=attrgetter('commit_time'), reverse=True)
        return result
        
    def do_read(self, path, revision=None, branch='master'):
        path = clean_path(path)
        repo = self.repo
        if revision == self.null_revision:
            raise FileDoesNotExist(self, "'%s' does not exist at revision null" % path)
        c = self._get_commit(revision, branch)
        obj = get_by_path(repo, repo[c.tree], path)
        if not obj:
            raise FileDoesNotExist(self, "'%s' does not exist" % path)
        if not isinstance(obj, Blob):
            raise FileDoesNotExist(self, "'%s' is not a regular file" % path)
        data = obj.as_pretty_string()
        return data
        
    def do_commit(self, message='', author=None, committer=None, branch='master', parent=None):
        if isinstance(message, unicode):
            message = message.encode('utf-8')
        repo = self.repo
        try:
            parent = self._get_commit(parent, branch)
            root = repo[parent.tree]
        except BranchDoesNotExist:
            if branch == 'master': # initial commit
                root = Tree()
            else:
                raise
            
        cache = {}
        paths = set()
        objects = set()
        
        for path, (action, data) in self.changes.iteritems():
            path = clean_path(path)
            paths.add(path)
            dirname, filename = os.path.split(path)
            trees = self._collect(root, dirname, cache)

            if action == WRITE:
                blob = Blob.from_string(data)
                trees[-1][2][filename] = (self.file_mode, blob.id)
                cache[blob.id] = blob

            elif action == DELETE:
                del trees[-1][2][filename]

            elif action == RENAME:
                old = self._collect(root, data, cache)
                mode, name, obj = old[-1]
                del old[-2][2][name]
                trees[-1][2][filename] = (mode, obj.id)
                cache.update(self._link(old[:-1]))
                paths.add(data)

            cache.update(self._link(trees))
        else:
            objects.add(root)

        # collect all objects that have to be committed
        for path in paths:
            objects.update([obj for mode, name, obj in self._collect(root, path, cache)])
            
        # create the commit
        c = Commit()
        if parent:
            c.parents = [parent.id]
        c.tree = root.id
        c.committer = committer or self.committer
        c.author = author or c.committer

        t = time.localtime()
        c.commit_time = c.author_time = int(time.mktime(t))
        c.commit_timezone = c.author_timezone = t.tm_isdst * 3600 - time.timezone
        c.encoding = "UTF-8"
        c.message = message
        objects.add(c)

        # write everything to disk
        for obj in objects:
            repo.object_store.add_object(obj)

        repo.refs['refs/heads/%s' % branch] = c.id

        return DulwichCommit(self, c)
