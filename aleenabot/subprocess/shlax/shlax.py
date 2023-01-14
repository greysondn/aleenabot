import asyncio
import functools
import re
import shlex
import sys
import aleenabot.subprocess.buffer as aspBuffer
import aleenabot.subprocess.helpers as aHelpers
import io
import os

aio = asyncio

class ShlaxBuffers(aspBuffer.IOBufferSet):
    def __init__(self):
        super().__init__()

class ShlaxSubprocess:
    def __init__(self, cmd, *args, name:str="Unknown", quiet:bool=False):
        # guard against empty cmd
        if (cmd == None):
            cmd = 'sh'
        
        self.boxes:ShlaxBuffers = ShlaxBuffers()
        """I/O endpoints for this member"""
        
        self.cmd = cmd
        """Requested process plus arguments.
        
        Defaults to `sh -euc`, probably not good
        
        No security or bleaching done, probably not good
        """
        
        self.args = args
        
        self.name:str = name
        '''name of this process, mostly used for inter-routine/etc communication
        '''
        
        self.quiet:bool = quiet
        """Whether this process should print to terminal/etc"""
        
        self.outPipe:asyncio.StreamReader = None # type:ignore
        '''Direct handle on underlying process's std pipe.
        '''
        
        self.errPipe:asyncio.StreamWriter = None # type:ignore
        '''Direct handle on underlying process's std pipe.
        '''
        
        self.inPipe:asyncio.StreamWriter = None # type:ignore
        '''Direct handle on underlying process's std pipe.
        '''
        
        self.stdOutBuffer:str = ""
        """Short term buffer for stdErr, meant mostly to help only output on 
           full lines"""
        
        self.started:bool = False
        '''Whether or not this process has had `start` called.'''
        
        self.taskgroup:aio.TaskGroup = None  # type: ignore
        '''Taskgroup, so that this can register itself the easy way'''
        
        self.waited:bool = False
        '''whether or not the underlying process has had a wait for join called'''

    async def start(self, wait=True):
        # Create the subprocess controlled by DateProtocol;
        # redirect the standard output into a pipe.
        
        self.process = await aio.create_subprocess_exec(
            self.cmd,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=2000000 # 2 MB
        )
        
        self.inPipe  = self.process.stdin  # type: ignore
        self.outPipe = self.process.stdout # type: ignore
        self.errPipe = self.process.stderr # type: ignore
        
        self.started = True

    # basically a join innit?
    async def wait(self, *args, **kwargs):
        if not self.started:
            await self.start()

        if not self.waited:
            # Wait for the subprocess exit using the process_exited()
            # method of the protocol.
            await self.process.wait()

            self.waited = True

        return self