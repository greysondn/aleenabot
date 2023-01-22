from aleenabot.subprocess.buffers import IOBufferSet
from aleenabot.subprocess.helpers import InterProcessMail
# from aleenabot.subprocess.wrappers import STANDARD_YIELD_LENGTH
STANDARD_YIELD_LENGTH = 0.2
from aleenabot.subprocess.wrappers.subprocess_wrapper import SubprocessWrapper
from aleenabot.subprocess.wrappers.command_parser import CommandParser
from typing import cast

import aioconsole as aioc
import asyncio as aio
import logging


class Manager(SubprocessWrapper):
    def __init__(self, tg:set = set()):
        self.name = "main"
        self.parser = CommandParser()
        self.boxes = IOBufferSet()
        self.tg:set     = tg
        self.children  = set()
        self.childBoxes = dict()
        self.processRunning   = False
        self.processPoisoned  = False
        self.managerTaskCount = 0
        
        # self.addChild(self)
        # self.children.add(self)
        self.childBoxes[self.name] = self
    
    async def cliHandler(self):
        logging.debug(f"{self.name} -> cliHandler -> start")
        
        # wait for this to officially start
        while (not (self.processRunning)):
            await aio.sleep(STANDARD_YIELD_LENGTH)
        
        logging.debug(f"{self.name} -> cliHandler -> process started")
        
        while (self.processRunning):
            uinput = await aioc.ainput()
            logging.debug(f"{self.name} -> cliHandler -> input ack: || {uinput} ||")
            
            await self.message(receiver="cmd", message=uinput + "\n")
            logging.debug(f"{self.name} -> cliHandler -> message sent!")
        
        logging.debug(f"{self.name} -> cliHandler -> end")
    
    async def addChild(self, child:SubprocessWrapper):
        if (child not in self.children):
            self.children.add(child)
            self.childBoxes[child.name] = child

    async def stdinHandler(self):
        # wait for this to officially start
        while (not (self.processRunning)):
            await aio.sleep(STANDARD_YIELD_LENGTH)
            
        # okay, it's running
        while (self.processRunning):
            incoming:InterProcessMail = await self.boxes.inbox.stdin.get()
            await self.parser.exec(incoming.message, incoming)
            await aio.sleep(STANDARD_YIELD_LENGTH)

    async def mailroom(self):
        # aight, let's do this
        while (not self.processRunning):
            await aio.sleep(STANDARD_YIELD_LENGTH)
        while (self.processRunning):
            for child in self.children.union({self}):
                _ch = cast(SubprocessWrapper, child)
                if not(_ch.boxes.outbox.stdout.empty()):
                    msg = await _ch.boxes.outbox.stdout.get()
                    # do we know where it goes?
                    logging.debug(f"{self.name} -> Manager:mailroom -> message seen in an outbox!" + "\n" +
                                  f"    -> sender: {msg.sender}" + "\n" +
                                  f"    -> receiver: {msg.receiver}" + "\n" +
                                  f"    -> message: {msg.message}" + "\n" +
                                  f"    -> objectend")
                    
                    if (msg.receiver in self.childBoxes.keys()):
                        await self.childBoxes[msg.receiver].boxes.inbox.stdin.put(msg)
                    else:
                        print("Discarded dead letter to " + msg.receiver)
                
            await aio.sleep(STANDARD_YIELD_LENGTH)
    
    async def start(self):
        self._addTaskToTg(aio.create_task(self.mailroom()))
        self.managerTaskCount = self.managerTaskCount + 1
        
        self._addTaskToTg(aio.create_task(self.stdinHandler()))
        self.managerTaskCount = self.managerTaskCount + 1
        
        self._addTaskToTg(aio.create_task(self.cliHandler()))
        self.managerTaskCount = self.managerTaskCount + 1
        
        self.processRunning = True
        
        for child in self.children:
            await child.main()
    
    async def terminate(self):
        self.processRunning = False
        
        print("[*] Waiting ten seconds for soft termination.")
        await aio.sleep(10)
        
        if len(self.tg) > 0:
            logging.info(f"[*] Now forcefully closing remaining tasks.")
            for t in self.tg:
                if not t.done():
                    t.cancel()
                else:
                    self.tg.remove(t)
    
    async def wait(self, cli=False):
        if (not self.processRunning):
            await self.start()
        startLen = 0
        while (len(self.tg) > 0):
            if (len(self.tg) != startLen):
                for task in self.tg:
                    pass
                    # logging.debug(f"{self.name} -> Manager:wait -> outstanding task: {task._coro}")
                startLen = len(self.tg)
                logging.debug(f"{self.name} -> Manager:wait -> outstanding tasks: {startLen}")
            if (len(self.tg) <= self.managerTaskCount):
                logging.debug(f"{self.name} -> Manager:wait -> only see self, shutting down")
                print("[*] Only the manager.")
                print("[*] Waiting 30 seconds for messages to finish.")
                await aio.sleep(30)
                print("[*] Messages now discarded, terminating.")
                await self.terminate()
                
            await aio.sleep(STANDARD_YIELD_LENGTH)
        print("Goodnight!")