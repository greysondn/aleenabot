import asyncio as aio

class IOBuffer(aio.PriorityQueue):
    # an io buffer, singular
    def __init__(self, maxsize:int = 0):
        super().__init__(maxsize)

class IOBufferStdIo():
    # defines three IO boxes, for standard types of I/O
    def __init__(self):
        self.stdin:IOBuffer   = IOBuffer()
        self.stdout:IOBuffer  = IOBuffer()
        self.stderr:IOBuffer  = IOBuffer()

class IOBufferSet():
    # defines two io sets - one for incoming to this context, one for outgoing
    def __init__(self):
        self.inbox          = IOBufferStdIo()
        self.outbox         = IOBufferStdIo()
        self.loopbackChecks = []
    async def checkLoopback(self, name, msg):
        for check in self.loopbackChecks:
            check(self, name, msg)