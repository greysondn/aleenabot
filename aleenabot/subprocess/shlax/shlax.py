import asyncio
import functools
import re
import shlex
import sys
import aleenabot.subprocess.buffer as aspBuffer
import aleenabot.subprocess.helpers as aHelpers
import io

aio = asyncio

class ShlaxBuffers(aspBuffer.IOBufferSet):
    def __init__(self):
        super().__init__()

class ShlaxSubprocessInputIOWrapper(io.BytesIO):
    # Wrapping it as a file so you don't have to.
    def __init__(self, initial_bytes=b""):
        super().__init__(initial_bytes)
        
    def add(self, txt):
        self.write(txt.encode())
    
    def addLine(self, txt):
        self.add(txt + "\n")

class ShlaxSubprocessOutputsProtocol(asyncio.SubprocessProtocol):
    # this gets handed the child ShlaxSubProcess
    def __init__(self, proc):
        self.proc = proc

    def pipe_data_received(self, fd, data):
        if fd == 1:
            # helper function ShlaxProcess.stdout
            self.proc.stdout(data)
        elif fd == 2:
            # helper function ShlaxProcess.stderr
            self.proc.stderr(data)

    def process_exited(self):
        # future of proc object
        self.proc.exit_future.set_result(True)

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
        """
        
        self.name:str = name
        '''name of this process, mostly used for inter-routine/etc communication
        '''
        
        self.quiet:bool = quiet
        """Whether this process should print to terminal/etc"""
        
        self.stdErrBuffer:str = ""
        """Short term buffer for stdErr, meant mostly to help only output on 
           full lines"""
        
        self.inPipe:ShlaxSubprocessInputIOWrapper = ShlaxSubprocessInputIOWrapper()
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
        # Get a reference to the event loop as we plan to use
        # low-level APIs.
        loop = asyncio.get_running_loop()

        # neat but probably not meaningful
        self.exit_future = asyncio.Future(loop=loop)

        # Create the subprocess controlled by DateProtocol;
        # redirect the standard output into a pipe.
        self.transport, self.protocol = await loop.subprocess_exec(
            lambda: ShlaxSubprocessOutputsProtocol(self),
            *self.args,
            stdin=self.inPipe,
        )
        
        self.started = True

    # basically a join innit?
    async def wait(self, *args, **kwargs):
        if not self.started:
            await self.start()

        if not self.waited:
            # Wait for the subprocess exit using the process_exited()
            # method of the protocol.
            await self.exit_future

            # Close the stdout pipe.
            self.transport.close()

            self.waited = True

        return self

    def _stdOutErr(self, data, which:str):
        """Helper to consoliate stdOut and stdErr's common code

        Args:
            data (maybe binary string): data the application tried to stream out.
            which (str): either "out" or "err" - which stream this is from
        """
        # this is written to be comparatively time efficient for what it is.
        
        # it does not spark joy.

        # in buffer data
        txt:str = data.decode()
        curBuffer:str = ""

        if (which == "out"):
            self.stdOutBuffer = self.stdOutBuffer + txt
            curBuffer = self.stdOutBuffer
        elif(which == "err"):
            self.stdErrBuffer = self.stdErrBuffer + txt
            curBuffer = self.stdErrBuffer
        else:
            raise ValueError("which must be `err` or `out`")
        
        # check for newline - would mean do output
        if ("\n" in curBuffer):
            # separate into remainder and current shtuff
            splits:list[str] = curBuffer.split("\n", 1)
        
            # get the current stuff
            cur:str = splits[0]
            
            # placeholder interprocess mail
            swp:aHelpers.InterProcessMail = aHelpers.InterProcessMail(
                sender      = self.name,
                receiver    = "main",
                quiet       = self.quiet,
                message     = cur
            )
            
            # late deferred stuff
            # - assign remainder from splits
            # - put into correct outgoing box
            # - cycle back in case we missed another line
            if (which == "out"):
                self.stdOutBuffer = splits[1]
                self.boxes.outbox.stdout.put_nowait(swp)
                self.stdout(b'')
            elif(which == "err"):
                self.stdErrBuffer = splits[1]
                self.boxes.outbox.stderr.put_nowait(swp)
                self.stderr(b'')
            else:
                raise ValueError("which must be `err` or `out`")
        
    def stdout(self, data):
        """stream handler for underlying subprocess's stdout.

        Args:
            data (maybe binary string): data the application tried to std out.
        """
        self._stdOutErr(data, "out")

    def stderr(self, data):
        """stream handler for underlying subprocess's stderr.

        Args:
            data (maybe binary string): data the application tried to std err.
        """
        self._stdOutErr(data, "err")

    @functools.cached_property
    def rc(self):
        return self.transport.get_returncode()