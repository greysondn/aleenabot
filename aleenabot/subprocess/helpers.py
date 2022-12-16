import asyncio as aio
from collections import deque
from enum import Enum
from typing import Any, Awaitable, cast, Optional
from aleenabot.subprocess.buffer import IOBufferSet
from aleenabot.subprocess.shlax.shlax import ShlaxSubprocess

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
    count:int = 0
    
    def __init__(
                    self,
                    sender:str="Unknown",
                    receiver:str="Unknown",
                    type_:InterProcessMailType=InterProcessMailType.NULL,
                    priority:int = 1000,
                    message:str = "Message empty.",
                    quiet:bool = False,
                    payload:Any = None
                ):
        self.index:int = InterProcessMail.count
        InterProcessMail.count += 1
        
        self.quiet:bool                = quiet
        self.sender:str                = sender
        self.receiver:str              = receiver
        self.type:InterProcessMailType = type_
        self.priority:int              = priority
        self.message:str               = message
        self.payload:Any               = payload
    
    def __lt__(self, obj:Any):
        ret = self
            
        # make sure it's mail
        if isinstance(obj, InterProcessMail):
            # priority
            if (self.priority < obj.priority):
                ret = self
            elif (self.priority > obj.priority):
                ret = obj
            else:
                # equal, let's try index
                if (self.index < obj.index):
                    ret = self
                else:
                    # doesn't matter, won't be able to sort it any
                    # further anyway
                    ret = obj
        else:
            # we can only compare against mail for now
            # so... that's an error.
            
            # this is expected to go unhandled.
            raise TypeError("InterprocessMail can only compare to InterprocessMail")
        return ret

class SubprocessWrapper:
    def __init__(self, *args, name:str="Unknown", quiet:bool=False, tg:aio.TaskGroup=aio.TaskGroup()):
        self.name:str         = name
        self.tg:aio.TaskGroup = tg
        self.proc             = ShlaxSubprocess(args, name=name, quiet=quiet, tg=tg)
        self.boxes            = self.proc.boxes
        self.processRunning   = False
        self.processPoisoned  = False

    # REMOVED: Loopback check function

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
        # REMOVED: Loopback check call

    async def main(self):
        # this is pretty epic, really, though
        self.tg.create_task(self.mainProcess())
        self.tg.create_task(self.stdinHandler())
            
        # I think that's it?

    async def mainProcess(self):
        # tell everything we're running
        await self.boxes.startAll()
        # start program
        await self.proc.start()
        self.processRunning = True
    
    async def stdinHandler(self):
        # TODO: write docs about how this is meant to override.

        # wait for this to officially start
        while (not self.boxes.inbox.stdin.isRunning):
            await aio.sleep(1)
            
        # okay, it's running
        while (self.boxes.inbox.stdin.isRunning):
            incoming:InterProcessMail = await self.boxes.inbox.stdin.get()
            
            self.proc.inPipe.addLine(incoming.message)
            
            await aio.sleep(1)

        
class Manager(SubprocessWrapper):
    pass

class ManagerCommandParser:
    def __init__(self):
        pass
    
    # just an error handler, mostly
    async def special_error(self, host:Manager, commands:deque[str], msg:InterProcessMail, err:str):
        pass
    
    # check too many or not enough args
    async def checkMinArgs(self, host:Manager, commands:deque[str], msg:InterProcessMail, count:int) -> bool:
        ret:bool = False
        
        if (len(commands) >= count):
            ret = True
        else:
            ret = False
            await self.special_error(host, commands, msg, "not enough arguments")
        
        return ret
    
    async def checkMaxArgs(self, host:Manager, commands:deque[str], msg:InterProcessMail, count:int) -> bool:
        ret:bool = False
        
        if (len(commands) <= count):
            ret = True
        else:
            ret = False
            await self.special_error(host, commands, msg, "too many arguments")
        
        return ret

    # output
    async def print(self, host:Manager, commans:deque[str], msg:InterProcessMail):
        # slightly special handling
        print(msg.message[6:])

    # finally run
    async def exec(self, host:Manager, commands:deque[str], msg:InterProcessMail):
        if (await self.checkMinArgs(host, commands, msg, 1)):
            swp = commands.popleft()
            
            if (swp == "print"):
                print("print!")
                await self.print(host, commands, msg)
            else:
                await self.special_error(host, commands, msg, "unknown arguments")