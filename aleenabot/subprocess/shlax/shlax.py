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
    def __init__(self, *args, name:str="Unknown", quiet:bool=False):
        # guard against empty args
        if (len(args) == 1 and ' ' in args[0]):
            args = ['sh', '-euc', args[0]]
        
        self.boxes:ShlaxBuffers = ShlaxBuffers()
        """I/O endpoints for this member"""
        
        self.args = args
        """Requested process plus arguments.
        
        Defaults to `sh -euc`, probably not good
        
        No security or bleaching done, probably not good
        """
        
        self.name:str = name
        '''name of this process, mostly used for inter-routine/etc communication
        '''
        
        self.quiet:bool = quiet
        """Whether this process should print to terminal/etc"""
        
        self.outPipeR,self.outPipeW =os.pipe()
        self.outPipe = self.outPipeR
        '''Direct handle on underlying process's std pipe.
        '''
        
        self.errPipeR,self.errPipeW =os.pipe()
        self.errPipe = self.errPipeR
        '''Direct handle on underlying process's std pipe.
        '''
        
        self.inPipeR,self.inPipeW =os.pipe()
        self.inPipe = self.inPipeW
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
        
        self.process = await aio.create_subprocess_shell(
            " ".join(self.args),
            stdin=self.inPipeR,
            stdout=self.outPipeW,
            stderr=self.errPipeW
        )
        
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