import os
import stat


def clean_path(path):
    try:
        path = str(path)
    except UnicodeEncodeError:
        raise ValueError("dulwich requires bytestring path names")
    path = os.path.normpath(path)
    if '..' in path:
        raise ValueError("found '..' in path")
    return path


def iter_blob_paths(repo, h):
    for mode, name, hexsha in repo[h].entries():
        if stat.S_ISREG(mode):
            yield name
        elif stat.S_ISDIR(mode):
            for path in iter_blob_paths(repo, hexsha):
                yield os.path.join(name, path)


def tree_diff(repo, a, b):
    a = repo[a] if a else None
    b = repo[b] if b else None
    if a:
        for name in a:
            it = None
            a_mode, a_hexsha = a[name]
            a_isdir = stat.S_ISDIR(a_mode)
            if b and name in b:
                b_mode, b_hexsha = b[name]
                b_isdir = stat.S_ISDIR(b_mode)
                if not a_isdir or not b_isdir:
                    yield name
                it = tree_diff(repo, a_hexsha if a_isdir else None, b_hexsha if b_isdir else None)
            else:
                if a_isdir:
                    it = iter_blob_paths(repo, a_hexsha)
                else:
                    yield name
            if it:
                for path in it:
                    yield os.path.join(name, path)
    if b:
        for name in b:
            if not a or name not in a:
                mode, hexsha = b[name]
                if stat.S_ISDIR(mode):
                    for path in iter_blob_paths(repo, hexsha):
                        yield os.path.join(name, path)
                else:
                    yield name


def get_by_path(repo, tree, path):
    for bit in path.split(os.path.sep):
        found = False
        for mode, name, hexsha in tree.entries():
            if name == bit:
                tree = repo[hexsha]
                found = True
                break
        if not found:
            return None
    return tree


def is_same_object(repo, a, b, path):
    for bit in path.split(os.path.sep):
        in_a = bit in a
        in_b = bit in b
        if not in_a or not in_b:
            return in_a == in_b
        a_mode, a_sha = a[bit]
        b_mode, b_sha = b[bit]
        if a_mode != b_mode:
            return False
        a = repo[a_sha]
        b = repo[b_sha]
    return a == b


class WebBackend(object):
    def open_repository(self, backend):
        return backend.repo
