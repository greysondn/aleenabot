import asyncio as aio
from enum import Enum
from typing import Any, Awaitable, Optional

async def waitUntilFunctionTrue(function_, pollIntervalInSeconds:float = 1.0):
    while (function_() != True):
        await aio.sleep(pollIntervalInSeconds)
    return True

async def waitUntilDictEntryEquals(_dict:dict, key:Any, value:Any, pollIntervalInSeconds:float = 1.0):
    while (_dict[key] != value):
        await aio.sleep(pollIntervalInSeconds)

class InterProcessMailType(Enum):
    NULL   = 0,
    STDIN  = 1,
    STDOUT = 2,
    STDERR = 3,
    KILL   = 4

class InterProcessMail:
    def __init__(
                    self,
                    sender:str="Unknown",
                    receiver:str="Unknown",
                    type_:InterProcessMailType=InterProcessMailType.NULL,
                    priority:int = 1000,
                    message:str = "Message empty.",
                    payload:Any = None
                ):
        self.sender:str                = sender
        self.receiver:str              = receiver
        self.type:InterProcessMailType = type_
        self.priority:int              = priority
        self.message:str               = message
        self.payload:Any               = payload
    
    def clone(self) -> "InterProcessMail":
        return InterProcessMail(
            sender   = self.sender,
            receiver = self.receiver,
            type_    = self.type,
            priority = self.priority,
            message  = self.message,
            payload  = self.payload
        )

    def toPriorityQueue(self) -> tuple[int, "InterProcessMail"]:
        return (self.priority, self)

class CoroutineWrapper:
    def __init__(self, name:str="Unknown"):
        self.name:str    = name
        self.inbox       = aio.PriorityQueue()
        self.outbox      = aio.PriorityQueue()
        self.errbox      = aio.PriorityQueue()
        self.stdin       = aio.PriorityQueue()
        self.stdout      = aio.PriorityQueue()
        self.stderr      = aio.PriorityQueue()

        self.running = {
            "mainProcess"   : False,
            "inBoxToQueue"  : False,
            "inQueueToStd"  : False,
            "outStdToQueue" : False,
            "outQueueToBox" : False,
            "errStdToQueue" : False,
            "errQueueToBox" : False,
        }
        
        self.poison = {
            "mainProcess"   : False,
            "inBoxToQueue"  : False,
            "inQueueToStd"  : False,
            "outStdToQueue" : False,
            "outQueueToBox" : False,
            "errStdToQueue" : False,
            "errQueueToBox" : False,
        }

    async def message(
                        self, 
                        receiver:str = "main",
                        type_:InterProcessMailType = InterProcessMailType.STDOUT,
                        priority:int = 1000,
                        message:str = "Empty message.",
                        payload:Any = None
                    ):
        # so we make the message
        msg =   InterProcessMail(
                        sender = self.name,
                        receiver = receiver,
                        type_ = type_,
                        priority = priority,
                        message = message,
                        payload = payload
                    )
        # and then huck it into the outbox
        await self.outbox.put(msg.toPriorityQueue())

    async def createTaskAndMessageMain(self, coro):
        task = aio.create_task(coro)
        
        await self.message(
            receiver = "main",
            message = "task add payload",
            payload = task
        )

    async def main(self):
        #
        # TODO: python 3.11 - rewrite with a taskgroup
        # this is pretty epic, really, though

        # let's just do it as a list, shall we?
        tasks = [
            self.mainProcess(),
            self.inBoxToQueue(),
            self.inQueueToStd(),
            self.outStdToQueue(),
            self.outQueueToBox(),
            self.errStdToQueue(),
            self.errQueueToBox(),
        ]
        
        # gets weird right about now, I think
        for task in tasks:
            await self.createTaskAndMessageMain(task)
            
        # I think that's it?

    async def mainProcess(self):
        # tell everything we're running
        for key in list(self.running.keys()):
            self.running[key] = True

    async def inBoxToQueue(self):
        # wait for this to officially start
        await waitUntilDictEntryEquals(self.running, "inboxToQueue", True)

        # okay, it's running
        while self.running["inBoxToQueue"]:
            expect:Any = await self.inbox.get()   # unresolved coroutine or tuple, I think
            incoming:InterProcessMail = expect[1] # fix type, trim priority anyway
    
    async def inQueueToStd(self):
        # TODO: write docs about how this is meant to override.

        # wait for this to officially start
        while (not self.running["inQueueToStd"]):
            await aio.sleep(1)
        
        # okay, it's running
        while self.running["inQueueToStd"]:
            pass
    
    async def outStdToQueue(self):
        # TODO: Enable poisoning...?
        
        # wait for this to officially start
        while (not self.running["outStdToQueue"]):
            await aio.sleep(1)

        # okay, it's running
        while self.running["outStdToQueue"]:
            pass
        
    async def outQueueToBox(self):
        # TODO: write docs about how this is meant to override.
        
        # meanwhile, hae a sort of template for simple std-to-main-output
        
        # wait for this to officially start
        while (not self.running["outQueueToBox"]):
            await aio.sleep(1)
        
        # okay, it's running
        while self.running["outQueueToBox"]:
            swp = await self.stdout.get()
            outgoing:str = swp[1] # fix type, trim
            
            await self.message(message=outgoing)
        
    async def errStdToQueue(self):
        # wait for this to officially start
        while (not self.running["errStdToQueue"]):
            await aio.sleep(1)
        
        # okay, it's running
        while self.running["errStdToQueue"]:
            pass

    async def errQueueToBox(self):
        # TODO: write docs about how this is meant to override.
        
        # wait for this to officially start
        while (not self.running["errQueueToBox"]):
            await aio.sleep(1)
        
        # okay, it's running
        while self.running["errQueueToBox"]:
            pass

class ProcessWrapper(CoroutineWrapper):
    def __init__(self, name:str = "Unknown", command:str=""):
        # parent constructor
        super().__init__(name)
        
        # unique to this object
        self.command:str = command
        self.process:Any = None # uhhh?
        
    async def mainProcess(self):
        # ignite process like a lunatic
        process = await aio.create_subprocess_shell(
            self.command,
            stdin =  aio.subprocess.PIPE,
            stdout = aio.subprocess.PIPE,
            stderr = aio.subprocess.PIPE
        )
        
        # set process so we can access std streams
        self.process = process
        
        # Parent
        await super().mainProcess()
        
    # for now the only overridden one was this one
    async def outStdToQueue(self):
        latest:bytes = await self.process.stdout.readline()
        decoded:str = latest.decode()
        
        # and now put it on the queue
        await self.stdout.put((1000, decoded))
        
class Manager(CoroutineWrapper):
    def __init__(self, name="Unknown"):
        # parent, and fixing some stuff up
        super().__init__(name)
        
        self.tasks:set[aio.Task] = set()
        self.children:dict[str, "ProcessWrapper"] = {}
        
    async def addTask(self, task:aio.Task):
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    