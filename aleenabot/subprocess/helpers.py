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
                if (self.index > obj.index):
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

