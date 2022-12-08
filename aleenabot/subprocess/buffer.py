import asyncio as aio

class IOBuffer(aio.PriorityQueue):
    # an io buffer, singular
    def __init__(self, maxsize:int = 0):
        super().__init__(maxsize)
        
        self.isRunning:bool = False
        self.isPoisoned:bool = False
        
        self.poisonPill:str = "[EOF]" # we'll have to set it manually
        
    async def start(self):
        self.isRunning = True
    
    async def poison(self):
        self.isPoisoned = False
        
    async def attemptToPoison(self, pill:str):
        if (self.poisonPill == pill):
            await self.poison()

class IOBufferStdIo():
    # defines three IO boxes, for standard types of I/O
    def __init__(self):
        self.stdin:IOBuffer   = IOBuffer()
        self.stdout:IOBuffer  = IOBuffer()
        self.stderr:IOBuffer  = IOBuffer()
    async def startAll(self):
        await self.stdin.start()
        await self.stdout.start()
        await self.stderr.start()
    async def poisonAll(self):
        await self.stdin.poison()
        await self.stdout.poison()
        await self.stderr.poison()

class IOBufferSet():
    # defines two io sets - one for incoming to this context, one for outgoing
    def __init__(self):
        self.inbox          = IOBufferStdIo()
        self.outbox         = IOBufferStdIo()
        self.loopbackChecks = []
    async def startAll(self):
        await self.inbox.startAll()
        await self.outbox.startAll()
    async def poisonAll(self):
        await self.inbox.poisonAll()
        await self.outbox.poisonAll()
    async def checkLoopback(self, name, msg):
        for check in self.loopbackChecks:
            check(self, name, msg)