import aleenabot.subprocess.helpers as hlp
import asyncio as aio
    

class Main(hlp.Manager):
    def __init__(self):
        # call parent constructor
        super().__init__("main")
    
    def checkDead(self):
        return False
        
    async def main(self):
        # create main program?
        hwProc:hlp.ProcessWrapper = hlp.ProcessWrapper(
            name = "Hello World!",
            command = "python helloworld.py"
        )
        
        # add to children
        await self.addChild(hwProc)
        
        # just want to sanity check that output
        await hwProc.message(message = "Message wiring is good.")
        
        # okay um ignite it?
        await hwProc.main()
        
        # and now I wait for that to die?
        await hlp.waitUntilFunctionTrue(self.checkDead)

async def aioMain():
    m = Main()
    await m.main()
        
if (__name__ == "__main__"):
    aio.run(aioMain())