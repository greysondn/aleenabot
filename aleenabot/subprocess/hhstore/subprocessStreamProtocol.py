import asyncio as aio
import asyncio.subprocess as subprocess

PIPE = subprocess.PIPE
STDOUT = subprocess.STDOUT
DEVNULL = subprocess.DEVNULL


#
# SubprocessStream protocol:
#
class SubprocessStreamProtocol(aio.SubprocessProtocol):
    """Like StreamReaderProtocol, but for a subprocess."""

    # okay?
    def __init__(self, limit, loop):
        super().__init__()
        self.loop = loop
        self._limit = limit
        self.stdin = self.stdout = self.stderr = None
        self._transport = None

    # okay?
    def __repr__(self):
        info = [self.__class__.__name__]
        if self.stdin is not None:
            info.append('stdin=%r' % self.stdin)
        if self.stdout is not None:
            info.append('stdout=%r' % self.stdout)
        if self.stderr is not None:
            info.append('stderr=%r' % self.stderr)
        return '<%s>' % ' '.join(info)

    def connection_made(self, transport):
        self._transport = transport

        stdout_transport = transport.get_pipe_transport(1)
        if stdout_transport is not None:
            self.stdout = streams.StreamReader(limit=self._limit,
                                               loop=self._loop)
            self.stdout.set_transport(stdout_transport)

        stderr_transport = transport.get_pipe_transport(2)
        if stderr_transport is not None:
            self.stderr = streams.StreamReader(limit=self._limit,
                                               loop=self._loop)
            self.stderr.set_transport(stderr_transport)

        stdin_transport = transport.get_pipe_transport(0)
        if stdin_transport is not None:
            self.stdin = streams.StreamWriter(stdin_transport,
                                              protocol=self,
                                              reader=None,
                                              loop=self._loop)

    def pipe_data_received(self, fd, data):
        if fd == 1:
            reader = self.stdout
        elif fd == 2:
            reader = self.stderr
        else:
            reader = None
        if reader is not None:
            reader.feed_data(data)

    def pipe_connection_lost(self, fd, exc):
        if fd == 0:
            pipe = self.stdin
            if pipe is not None:
                pipe.close()
            self.connection_lost(exc)
            return
        if fd == 1:
            reader = self.stdout
        elif fd == 2:
            reader = self.stderr
        else:
            reader = None
        if reader != None:
            if exc is None:
                reader.feed_eof()
            else:
                reader.set_exception(exc)

    def process_exited(self):
        self._transport.close()
        self._transport = None