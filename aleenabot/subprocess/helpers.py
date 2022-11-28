import asyncio as aio
from enum import Enum
from typing import Any, Awaitable, Optional


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

class ProcessWrapper:
    def __init__(self):
        self.name:str    = "Unknown"
        self.command:str = ""
        self.inbox       = aio.PriorityQueue()
        self.outbox      = aio.PriorityQueue()
        self.errbox      = aio.PriorityQueue()
        self.stdin       = aio.PriorityQueue()
        self.stdout      = aio.PriorityQueue()
        self.stderr      = aio.PriorityQueue()
        self.process:Optional[aio.subprocess.Process] = None # uhhh?
        self.running = {
            "in"  : False,
            "out" : False,
            "err" : False,
            "main": False
        }

    async def main(self):
        #
        # TODO: python 3.11 - rewrite with a taskgroup
        # this is pretty epic, really, though
        msgTmpl =   InterProcessMail(
                        sender = self.name,
                        receiver = "main",
                        type_ = InterProcessMailType.STDOUT,
                        message = "task add payload"
                    )
        
        mainTask = aio.create_task(self.run())
        inTask   = aio.create_task(self.input_loop())
        outTask  = aio.create_task(self.output_loop())
        errTask  = aio.create_task(self.err_loop())
        
        # gets weird right about now, I think
        
        
        
        

    async def run(self):
        process = await aio.create_subprocess_shell(
            "",
            stdin =  aio.subprocess.PIPE,
            stdout = aio.subprocess.PIPE,
            stderr = aio.subprocess.PIPE
        )
        
        self.process = process
        
        self.running["main"] = True
        self.running["err"] = True
        self.running["out"] = True
        self.running["in"] = True

    
    async def input_loop(self):
        # wait for this to officially start
        while (not self.running["in"]):
            await aio.sleep(1)
        
        # okay, it's running
        while self.running["in"]:
            expect:Any = await self.inbox.get()   # unresolved coroutine or tuple, I think
            incoming:InterProcessMail = expect[1] # fix type, trim priority anyway
            
            if (incoming.type == InterProcessMailType.KILL):
                pass
            else:
                self.handleInput(incoming)
    
    def handleInput(self, incoming:InterProcessMail):
        # TODO: write docs about how this is meant to override.
        pass
        
    
    async def output_loop(self):
        # wait for this to officially start
        while (not self.running["out"]):
            await aio.sleep(1)
        
        # okay, it's running
        while self.running["out"]:
            latest:str = await self.process.stdout.readline()
        
    def handleOutput(self):
        # TODO: write docs about how this is meant to override.
        pass
        
    async def err_loop(self):
        # wait for this to officially start
        while (not self.running["err"]):
            await aio.sleep(1)
        
        # okay, it's running
        while self.running["err"]:
            pass

    def handle_err(self):
        # TODO: write docs about how this is meant to override.
        pass