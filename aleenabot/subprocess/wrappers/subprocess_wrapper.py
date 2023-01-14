from aleenabot.subprocess.helpers import InterProcessMail, InterProcessMailType
from aleenabot.subprocess.shlax.shlax import ShlaxSubprocess
from aleenabot.subprocess.wrappers import STANDARD_YIELD_LENGTH
from typing import Any

import asyncio as aio
import logging



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