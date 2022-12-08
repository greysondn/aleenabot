import asyncio as aio
from collections import deque
from enum import Enum
from typing import Any, Awaitable, cast, Optional

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
                    payload:Any = None
                ):
        self.index:int = InterProcessMail.count
        InterProcessMail.count += 1
        
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
            
            
        return ret

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

    async def guardAgainstLoopback(self, msg:InterProcessMail):
        if (msg.receiver == self.name):
            await self.inbox.put(msg)
        else:
            await self.outbox.put(msg)

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
        await self.guardAgainstLoopback(msg)

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
        await waitUntilDictEntryEquals(self.running, "inBoxToQueue", True)

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
            await aio.sleep(1)
    
    async def outStdToQueue(self):
        # TODO: Enable poisoning...?
        
        # wait for this to officially start
        while (not self.running["outStdToQueue"]):
            await aio.sleep(1)

        # okay, it's running
        while self.running["outStdToQueue"]:
            # FIXME: WOOPS
            swp = await self.stdout.get()
            outgoing:str = "print" + swp[1] # fix type, trim
            
            await self.stdout.put((1000, outgoing))
        
    async def outQueueToBox(self):
        # TODO: write docs about how this is meant to override.
        
        # meanwhile, hae a sort of template for simple std-to-main-output
        
        # wait for this to officially start
        while (not self.running["outQueueToBox"]):
            await aio.sleep(1)
        
        # okay, it's running
        while self.running["outQueueToBox"]:
            msg = (await self.stdout.get())[1]
            print(f"{self.name} : outqueuetobox : {msg}")
            await self.message(message=msg)
        
    async def errStdToQueue(self):
        # wait for this to officially start
        while (not self.running["errStdToQueue"]):
            await aio.sleep(1)
        
        # okay, it's running
        while self.running["errStdToQueue"]:
           await aio.sleep(1) 

    async def errQueueToBox(self):
        # TODO: write docs about how this is meant to override.
        
        # wait for this to officially start
        while (not self.running["errQueueToBox"]):
            await aio.sleep(1)
        
        # okay, it's running
        while self.running["errQueueToBox"]:
            await aio.sleep(1)

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
        
        # remainders
        self.running["childrenOutboxHandler"] = True
        
    # for now the only overridden one was this one
    async def outStdToQueue(self):
        # TODO: Enable poisoning...?
        
        # wait for this to officially start
        await waitUntilDictEntryEquals(self.running, "outStdToQueue", True)

        # okay, it's running
        while self.running["outStdToQueue"]:
            # this can literally go so fast nothing else gets a chance to
            # run. That was my hard lesson for today.
            await aio.sleep(1)
            latest:bytes = await self.process.stdout.readline()
            if (len(latest) > 0):
                decoded:str = latest.decode()

                # and now put it on the queue
                await self.stdout.put((1000, "print " + decoded))

        
class Manager(CoroutineWrapper):
    def __init__(self, name="Unknown"):
        # parent, and fixing some stuff up
        super().__init__(name)
        
        self.tasks:set[aio.Task] = set()
        self.children:dict[str, "CoroutineWrapper"] = {}
        self.commandParser:"ManagerCommandParser" = ManagerCommandParser()

        self.running["childrenOutboxHandler"] = False
        self.poison["childrenOutboxHandler"]   = False

    async def main(self):
        #
        # TODO: python 3.11 - rewrite with a taskgroup
        # this is pretty epic, really, though

        # let's just do it as a list, shall we?
        tasks = [
            self.childrenOutboxHandler(),
        ]
        
        # gets weird right about now, I think
        for task in tasks:
            await self.createTaskAndMessageMain(task)
            
        # I think that's it?

    async def mainProcess(self):
        # Parent
        await super().mainProcess()
        
        # remainders
        self.running["childrenOutboxHandler"] = True
    
    async def addTask(self, task:aio.Task):
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def addChild(self, child:CoroutineWrapper):
        self.children[child.name] = child
    
    async def childrenOutboxHandler(self):
        # TODO: write docs about how this is meant to override.
        # meanwhile, this is basically a template
        
        # TODO: Implement poison pilling
        
        # wait for this to officially start
        await waitUntilDictEntryEquals(self.running, "childrenOutboxHandler", True)
        
        # okay, it's running
        while self.running["childrenOutboxHandler"]:
            # create a list of current children this loop
            childList = list(self.children.values())
            
            print(childList)
            
            
            for child in childList:
                # make sure it's still alive, basically
                if (not child.outbox.empty()):
                    msg:InterProcessMail = (await child.outbox.get())[1]
                    await self.inbox.put(msg)
    
    async def inBoxToQueue(self):
        # wait for this to officially start
        await waitUntilDictEntryEquals(self.running, "inBoxToQueue", True)

        # okay, it's running
        while self.running["inBoxToQueue"]:
            incoming:InterProcessMail = cast(InterProcessMail, (await self.inbox.get())[1])
            
            if (incoming.receiver == self.name):
                # handle individual commands here
                commands:deque[str] = deque(incoming.message.split())
                await self.commandParser.exec(self, commands, incoming)

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
    
    # task
    async def task_add_payload(self, host:Manager, commands:deque[str], msg:InterProcessMail):
        if (await self.checkMaxArgs(host, commands, msg, 0)):
            # add it
            await host.addTask(msg.payload)
            
    
    async def task_add(self, host:Manager, commands:deque[str], msg:InterProcessMail):
        if (await self.checkMinArgs(host, commands, msg, 1)):
            swp = commands.popleft()
            
            if (swp == "payload"):
                await self.task_add_payload(host, commands, msg)
            else:
                await self.special_error(host, commands, msg, "unknown arguments")
    
    async def task(self, host:Manager, commands:deque[str], msg:InterProcessMail):
        if (await self.checkMinArgs(host, commands, msg, 1)):
            swp = commands.popleft()
            
            if (swp == "add"):
                await self.task_add(host, commands, msg)
            else:
                await self.special_error(host, commands, msg, "unknown arguments")

    # output
    async def print(self, host:Manager, commans:deque[str], msg:InterProcessMail):
        # slightly special handling
        print(msg.message[6:])

    # finally run
    async def exec(self, host:Manager, commands:deque[str], msg:InterProcessMail):
        if (await self.checkMinArgs(host, commands, msg, 1)):
            swp = commands.popleft()
            
            if (swp == "task"):
                await self.task(host, commands, msg)
            elif (swp == "print"):
                print("print!")
                await self.print(host, commands, msg)
            else:
                await self.special_error(host, commands, msg, "unknown arguments")