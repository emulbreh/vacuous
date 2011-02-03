from StringIO import StringIO

from celery.task import Task
from celery.task.sets import TaskSet, subtask

from dulwich.protocol import ReceivableProtocol
from dulwich.server import ReceivePackHandler

from vacuous.backends import load_backend
from vacuous.backends.dulwich.utils import WebBackend
from vacuous.tasks import SyncTask


class _ReceivePackHandler(ReceivePackHandler):
    def _apply_pack(self, refs):
        result = super(_ReceivePackHandler, self)._apply_pack(refs)
        status = dict(result)
        self._good_refs = []
        for oldsha, newsha, ref in refs:
            if status[ref] == 'ok':
                self._good_refs.append((oldsha, newsha, ref))
        return result


class ReceivePackTask(Task):
    def run(self, flavor, repo_path, data):
        backend = load_backend(flavor, repo_path, cache=False)
        out = StringIO()
        proto = ReceivableProtocol(StringIO(data).read, out.write)
        handler = _ReceivePackHandler(WebBackend(), [backend], proto, stateless_rpc=True)
        handler.handle()
        
        sync_tasks = []
        for oldrev, newrev, name in handler._good_refs:
            if name.startswith('refs/heads/'):
                branch = name[11:]
                sync_tasks.append(subtask(SyncTask, args=[backend.flavor, backend.path, oldrev, newrev, branch]))
                
        if sync_tasks:
            taskset = TaskSet(tasks=sync_tasks)
            taskset.apply_async().join()
        
        return out.getvalue(), handler._good_refs
        
