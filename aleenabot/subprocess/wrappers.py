import asyncio as aio
import aiofiles as aiof
import aioconsole as aioc
import shlex
import logging

from aleenabot.subprocess.helpers import InterProcessMail, InterProcessMailType
from aleenabot.subprocess.buffers import IOBufferSet
from aleenabot.subprocess.shlax.shlax import ShlaxSubprocess
from typing import Any, Awaitable, cast, Optional

STANDARD_YIELD_LENGTH:float = 0.2

class SubprocessWrapper:
    def __init__(self, cmd, *args, name:str="Unknown", quiet:bool=False, tg:set = set()):
        self.name:str         = name
        self.tg:set           = tg
        self.proc             = ShlaxSubprocess(cmd, *args, name=name, quiet=quiet)
        self.boxes            = self.proc.boxes
        self.processRunning   = False
        self.processPoisoned  = False
        self.exitcode         = None

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
        await self.boxes.outbox.stdout.put(msg)

    def _addTaskToTg(self, task):
        self.tg.add(task)
        task.add_done_callback(self.tg.discard)

    async def main(self):
        # this is pretty epic, really, though
        self._addTaskToTg(aio.create_task(self.mainProcess()))
        self._addTaskToTg(aio.create_task(self.stdinHandler()))
        self._addTaskToTg(aio.create_task(self.stdoutHandler()))
        
        # I think that's it?

    async def mainProcess(self):
        # start program
        await self.proc.start()
        self.processRunning = True
        
        # wait on program to exit
        self.exitcode = await self.proc.process.wait()
        
        # mark everything as exited when the program exits
        self.processRunning = False
    
    async def stdinHandler(self):
        # TODO: write docs about how this is meant to override.

        # wait for this to officially start
        while (not self.processRunning):
            await aio.sleep(0.1)
        
        # okay, it's running
        stdin = self.proc.inPipe
        
        while (self.processRunning):
            try:
                incoming:InterProcessMail = self.boxes.inbox.stdin.get_nowait()
                inputStr = incoming.message.encode()
                stdin.write(inputStr)
                await stdin.drain()
                
            except aio.queues.QueueEmpty:
                # this is fine, for the record
                pass
            
            await aio.sleep(STANDARD_YIELD_LENGTH * 5)

    async def _stdoutHandler_doOutput(self):
        logging.debug(f"{self.name} -> _stdoutHandler_doOutput -> start")
        stdout = self.proc.outPipe
        logging.debug(f"{self.name} -> _stdoutHandler_doOutput -> read")
        outgoing = await stdout.read()
        if (len(outgoing) > 0):
            logging.debug(f"{self.name} -> _stdoutHandler_doOutput -> had data")
            decoded = outgoing.decode("UTF-8")
            
            for ln in decoded.split("\n"):
                outgoingStr = "print " + ln
                logging.debug(f"{self.name} -> _stdoutHandler_doOutput -> send msg")
                await self.message(message=outgoingStr)
        logging.debug(f"{self.name} -> _stdoutHandler_doOutput -> end")

    async def stdoutHandler(self):
        # TODO: write docs about how this is meant to override.
        logging.debug(f"{self.name} -> _stdoutHandler -> start")
        # wait for this to officially start
        while (not self.processRunning):
            await aio.sleep(0.1)
        
        logging.debug(f"{self.name} -> _stdoutHandler -> process running")
        # okay, it's running
        stdout = self.proc.outPipe
        
        while (self.processRunning):
            logging.debug(f"{self.name} -> _stdoutHandler -> loop start")
            await self._stdoutHandler_doOutput()
            await aio.sleep(STANDARD_YIELD_LENGTH)

        logging.debug(f"{self.name} -> _stdoutHandler -> process dead")
        # empty the accursed thing at the end
        while (not stdout.at_eof()):
            logging.debug(f"{self.name} -> _stdoutHandler -> await EOF")
            await self._stdoutHandler_doOutput()
            
        logging.debug(f"{self.name} -> _stdoutHandler -> end")
        
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
        return ret
    
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
    
    async def cliHandler(self):
        while (not self.processRunning):
            await aio.sleep(STANDARD_YIELD_LENGTH)
        while (self.processRunning):
            userInput = await aioc.ainput("> ")
            if userInput.strip() == "main exit":
                await self.terminate()
            else:
                pass
    
    async def start(self, cli=False):
        self._addTaskToTg(aio.create_task(self.mailroom()))
        self.managerTaskCount = self.managerTaskCount + 1
        
        self._addTaskToTg(aio.create_task(self.stdinHandler()))
        self.managerTaskCount = self.managerTaskCount + 1
        
        if (cli):
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
            await self.start(cli)
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