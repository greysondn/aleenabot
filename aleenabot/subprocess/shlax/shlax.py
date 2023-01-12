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
    def __init__(self, cmd, name:str="Unknown", quiet:bool=False):
        # guard against empty cmd
        if (cmd == None):
            cmd = 'sh -euc'
        
        self.boxes:ShlaxBuffers = ShlaxBuffers()
        """I/O endpoints for this member"""
        
        self.cmd = cmd
        """Requested process plus arguments.
        
        Defaults to `sh -euc`, probably not good
        
        No security or bleaching done, probably not good
        """
        
        self.name:str = name
        '''name of this process, mostly used for inter-routine/etc communication
        '''
        
        self.quiet:bool = quiet
        """Whether this process should print to terminal/etc"""
        
        self.outPipe = None
        '''Direct handle on underlying process's std pipe.
        '''
        
        self.errPipe = None
        '''Direct handle on underlying process's std pipe.
        '''
        
        self.inPipe = None
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
        
        print(self.cmd)
        
        self.process = await aio.create_subprocess_shell(
            shlex.join(self.cmd),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        self.inPipe  = self.process.stdin
        self.outpipe = self.process.stdout
        self.errPipe = self.process.stderr
        
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