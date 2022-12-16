import asyncio as aio
from collections import deque
from enum import Enum
import shlex
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
    def __init__(self, *args, name:str="Unknown", quiet:bool=False):
        self.name:str         = name
        self.tg:aio.TaskGroup = None # type: ignore
        self.proc             = ShlaxSubprocess(args, name=name, quiet=quiet)
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

class CommandParser:
    def __init__(self):
        self.commands = self.defineGroupCommand()
        
        self.commands["print"] = self.defineLeafCommand(
            self.print,
            "Prints text",
            "_greedy"
        )
        
        self.commands["echo"] = self.defineLeafCommand(
            self.print,
            "Prints text",
            "_greedy"
        )
    
    def defineLeafCommand(self, _cmd, help_txt, _args):
        ret = {}
        ret["_type"]        = "final"
        ret["_cmd"]         = _cmd
        ret["_help_txt"]    = help_txt
        ret["_args"]        = _args
    
    def defineGroupCommand(self, _children={}):
        ret = {}
        ret["_type"] = "group"
        ret["_children"] = _children
        return ret

    # output
    async def print(self, txt:str):
        print(txt)

    # finally run
    async def exec(self, command:str, msg:InterProcessMail|None = None):
        # we'll set it aside because we can
        swp = self.commands
        
        # shlex
        cm = shlex.split(command)
        
        # aight
        end = False
        while (not end):
            if (cm[0] in swp.keys()):
                swp = swp[cm[0]]
                cm = cm[1:]
                
                # leaf?
                if (swp["_type"] == "final"):
                    # let's do things
                    end = True
                    if swp["_args"] == "_greedy":
                        await swp["_cmd"](" ".join(cm))
                    else:
                        await self.print("Error: unsupported! : " + command)
                elif (swp["_type"] == "group"):
                    # this is fine
                    pass
                else:
                    end = True
                    await self.print("Error: unsupported type in tree! : " + command)
            else:
                end = True
                await self.print("Error: Could not find command! : " + command)

class Manager(SubprocessWrapper):
    def __init__(self):
        self.name = "main"
        self.parser = CommandParser()
        self.boxes = IOBufferSet()
        self.tg:aio.TaskGroup = None # type: ignore        
        self.children  = set()
        self.childBoxes = dict()
        
        # self.addChild(self)
        self.children.add(self)
        self.childBoxes[self.name] = self
    
    async def addChild(self, child:SubprocessWrapper):
        if (child not in self.children):
            self.children.add(child)
            self.childBoxes[child.name] = child

    async def stdinHandler(self):
        # wait for this to officially start
        while (not self.boxes.inbox.stdin.isRunning):
            await aio.sleep(1)
            
        # okay, it's running
        while (self.boxes.inbox.stdin.isRunning):
            incoming:InterProcessMail = await self.boxes.inbox.stdin.get()
            
            await self.parser.exec(incoming.message, incoming)
            
            await aio.sleep(1)

    async def mailroom(self):
        # aight, let's do this
        while (not self.processRunning):
            await aio.sleep(1)
        while (self.processRunning):
            for child in self.children:
                _ch = cast(SubprocessWrapper, child)
                if not(_ch.boxes.outbox.stdout.empty):
                    msg = await _ch.boxes.outbox.stdout.get()
                    # do we know where it goes?
                    if (msg.receiver in self.childBoxes.keys()):
                        await self.childBoxes[msg.receiver].boxes.inbox.stdin.put(msg)
                    else:
                        print("Discarded dead letter to " + msg.receiver)
                
                await aio.sleep(1)
    
    async def start(self):
        async with aio.TaskGroup() as tg:
            self.tg = tg
            tg.create_task(self.mailroom())
            tg.create_task(self.stdinHandler())