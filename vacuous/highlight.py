
#This code was derived from django-vcs (https://github.com/alex/django-vcs/), which in turn took it from lodgit (http://dev.pocoo.org/projects/lodgeit/).

import re
from difflib import SequenceMatcher
from django.utils.html import escape


class DiffRenderer(object):
    OLDFILE = '--- '
    NEWFILE = '+++ '
    DELETE = '-'
    INSERT = '+'
    EQUAL = ' '
    
    _chunk_re = re.compile(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')

    def __init__(self, udiff):
        self.lines = [escape(line) for line in udiff.splitlines()]
        
    def get_url(self, filename, revision):
        return None

    def get_context(self):
        in_header = True
        header = []
        lineiter = iter(self.lines)
        files = []
        try:
            line = lineiter.next()
            while True:
                if not line.startswith(self.OLDFILE):
                    files.append({'is_header': True, 'lines': header})
                    while not line.startswith(self.OLDFILE):
                        header.append(line)
                        line = lineiter.next()
                    header = []
                
                chunks = []
                old = self._extract_rev(line, self.OLDFILE)
                new = self._extract_rev(lineiter.next(), self.NEWFILE)
                files.append({
                    'is_header': False,
                    'old_filename': old[0],
                    'old_revision': old[1],
                    'old_url': self.get_url(old[0], old[1]),
                    'new_filename': new[0],
                    'new_revision': new[1],
                    'new_url': self.get_url(new[0], new[1]),
                    'chunks': chunks,
                })

                line = lineiter.next()
                while True:
                    match = self._chunk_re.match(line)
                    if not match:
                        break

                    lines = []
                    chunks.append(lines)

                    old_line, old_span, new_line, new_span = [int(o or 0) for o in match.groups()]
                    old_end = old_line + old_span
                    new_end = new_line + new_span
                    line = lineiter.next()

                    while old_line < old_end or new_line < new_end:
                        if line:
                            command, line = line[0], line[1:]
                        else:
                            command = self.EQUAL
                        
                        old = command != self.INSERT
                        new = command != self.DELETE

                        lines.append({
                            'old_lineno': old_line if old else u'',
                            'new_lineno': new_line if new else u'',
                            'command': command,
                            'line': line,
                        })

                        old_line += old
                        new_line += new
                        line = lineiter.next()
        except StopIteration:
            pass

        for file in files:
            if file['is_header']:
                continue
            for chunk in file['chunks']:
                lineiter = iter(chunk)
                first = True
                try:
                    while True:
                        line = lineiter.next()
                        cmd = line['command']
                        if cmd != self.EQUAL:
                            nextline = lineiter.next()
                            next_cmd = nextline['command']
                            if next_cmd == self.EQUAL or next_cmd == cmd:
                                continue
                            self._highlight_line(line, nextline)
                except StopIteration:
                    pass

        return files

    def _extract_rev(self, line, prefix=None):
        if prefix:
            if not line.startswith(prefix):
                return (None, None)
            line = line[len(prefix):]
        parts = line.split(None, 1)
        return parts[0], parts[1] if len(parts) == 2 else None

    def _highlight_line(self, line, next):
        ops = SequenceMatcher(None, line['line'], next['line']).get_opcodes()
        for l in (line, next):
            cmd = l['command']
            buf = []
            for tag, i0, i1, j0, j1 in ops:
                if cmd == self.INSERT and tag in ('replace', 'insert'):
                    buf.append('<ins>%s</ins>' % l['line'][j0:j1])
                elif cmd == self.DELETE and tag in ('replace', 'delete'):
                    buf.append('<del>%s</del>' % l['line'][i0:i1])
                elif tag == 'equal':
                    buf.append(l['line'][i0:i1])
            l['line'] = "".join(buf)

