#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import contextlib
import io
import itertools
import resource
import select
import subprocess

class FakePipe(io.BytesIO):
    def close(self):
        self.close_value = self.getvalue()
        return super(FakePipe, self).close()


class FakePoll(object):
    def __init__(self):
        self._fds = {}
        self.return_count = None

    def register(self, fd,
                 eventmask=select.POLLIN | select.POLLOUT | select.POLLPRI):
        self._fds[fd] = eventmask

    def unregister(self, fd):
        del self._fds[fd]

    def poll(self, timeout=None):
        if timeout is not None:
            return []
        assert self._fds, "FakePoll checked when no fds registered"
        return_count = len(self._fds) if (self.return_count is None) else self.return_count
        return [(fd, self._fds[fd])
                for _, fd in zip(range(return_count), self._fds)]


class FakePopen(object):
    @classmethod
    @contextlib.contextmanager
    def with_returncode(cls, returncode):
        cls.end_returncode = returncode
        cls.open_procs = []
        try:
            yield
        finally:
            del cls.end_returncode, cls.open_procs

    @classmethod
    def get_stdin(cls, index=-1):
        stdin = cls.open_procs[index].stdin
        if stdin.closed:
            return stdin.close_value
        else:
            return stdin.getvalue()

    def __init__(self, command, stdin, *args, **kwargs):
        self.command = command
        self.stdin = FakePipe() if (stdin is subprocess.PIPE) else stdin
        self.args = args
        self.kwargs = kwargs
        self.returncode = None
        self.open_procs.append(self)

    def poll(self):
        if self.stdin.closed:
            self.returncode = self.end_returncode
        return self.returncode


class FakeProcessWriter(object):
    _max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    FILENOS = itertools.cycle(range(_max_fd + 1, _max_fd + 130))

    def __init__(self, returncode, success=None, need_writes=0):
        self._fileno = next(self.FILENOS)
        self._need_writes = need_writes
        self._end_returncode = returncode
        self._end_success = (returncode == 0) if (success is None) else success
        self._success = None
        self.returncode = None
        self.write(0)

    def write(self, bytecount):
        if bytecount < self._need_writes:
            self._need_writes -= bytecount
        else:
            self._need_writes = 0
            self._success = self._end_success
            self.returncode = self._end_returncode

    def done_writing(self):
        return self._success is not None

    def poll(self):
        return self.returncode

    def success(self):
        return self._success

    def fileno(self):
        return self._fileno
