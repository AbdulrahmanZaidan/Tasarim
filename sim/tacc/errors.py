"""Derleyici hataları: `dosya:satır: ileti` biçiminde, Türkçe."""


class CompileError(Exception):
    def __init__(self, msg, file='<kaynak>', line=0):
        super().__init__(f'{file}:{line}: {msg}')
        self.msg = msg
        self.file = file
        self.line = line


def error(msg, where=None):
    """`where`: dosya/satır bilgisi taşıyan herhangi bir düğüm ya da token."""
    if where is None:
        raise CompileError(msg)
    raise CompileError(msg, getattr(where, 'file', '<kaynak>'), getattr(where, 'line', 0))
