import aleenabot.subprocess.helpers as hlp
import asyncio as aio
    

class Main(hlp.Manager):
    def __init__(self):
        # call parent constructor
        super().__init__("main")
    
    async def checkDead(self):
        return False
        
    async def main(self):
        # create main program?
        hwProc:hlp.ProcessWrapper = hlp.ProcessWrapper(
            name = "Hello World!",
            command = "python3 .\\helloworld.py"
        )
        
        # add to children
        await self.addChild(hwProc)
        
        # okay um ignite it?
        await hwProc.main()
        
        # and now I wait for that to die?
        await hlp.waitUntilFunctionTrue(self.checkDead)