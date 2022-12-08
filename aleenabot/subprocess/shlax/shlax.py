import asyncio
import functools
import re
import shlex
import sys
import aleenabot.subprocess.buffer as aspBuffer
import aleenabot.subprocess.helpers as aHelpers


class ShlaxBuffers(aspBuffer.IOBufferSet):
    def __init__(self):
        super().__init__()

class ShlaxSubprocessProtocol(asyncio.SubprocessProtocol):
    # this gets handed the child ShlaxProcess
    def __init__(self, proc):
        self.proc = proc
        self.output = bytearray()

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
    def __init__(self, *args, name:str="Unknown", quiet:bool=False, write=None, flush=None):
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
        
        # ---
        
        # probably remove
        self.awrite = write or sys.stdout.buffer.write
        # probably remove
        self.aflush = flush or sys.stdout.flush
        # not so bad
        self.started = False
        # ew, only on joins
        self.waited = False

    async def start(self, wait=True):
        if not self.quiet:
            # probably attempts to notify it was started, or at least called to
            # start. Some of this was butchered out.
            #
            # FIXME: Fix or cut the rest of the way out
            self.output(
                b'+ '
                + shlex.join([
                    arg.replace('\n', '\\n')
                    for arg in self.args
                ]).encode(),
                highlight=False
            )

        # Get a reference to the event loop as we plan to use
        # low-level APIs.
        loop = asyncio.get_running_loop()

        # neat but probably not meaningful
        self.exit_future = asyncio.Future(loop=loop)

        # Create the subprocess controlled by DateProtocol;
        # redirect the standard output into a pipe.
        self.transport, self.protocol = await loop.subprocess_exec(
            lambda: ShlaxSubprocessProtocol(self),
            *self.args,
            # FIXME: I will want stdin to be a pipe, too.
            stdin=None,
        )
        # note on above fixme:
        # proc.stdin.write(input)
        # await process.stdin.drain() # flush
        
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

    # FIXME: trash, replace with to-buffer handling
    def stdout(self, data):
        if not self.quiet:
            self.output(data)

    # FIXME: trash, replace with to-buffer handling
    def stderr(self, data):
        if not self.quiet:
            self.output(data)

    @functools.cached_property
    def out(self):
        return self.out_raw.decode().strip()

    @functools.cached_property
    def err(self):
        return self.err_raw.decode().strip()

    @functools.cached_property
    def rc(self):
        return self.transport.get_returncode()

    # FIXME: trash, maybe entirely
    def output(self, data, highlight=True, flush=True):
        for line in data.strip().split(b'\n'):
            line = [self.highlight(line) if highlight else line]
            line.append(b'\n')
            line = b''.join(line)
            self.write(line)

        if flush:
            self.flush()

    def highlight(self, line, highlight=True):
        ret = b""
        
        if  (
                (
                    not highlight
                ) or (
                    (
                        b'\x1b[' in line
                    ) or (
                        b'\033[' in line
                    ) or (
                        b'\\e['  in line
                    )
                )
        ):
            ret = line
        else:
            ret = line.encode()

        return ret

    def prefix_line(self):
        return [
            b' ',
            b'| '
        ]