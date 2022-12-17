import aleenabot.subprocess.wrappers as hlp
import asyncio as aio

async def aioMain():
    main = hlp.Manager()
    await main.start()
    print ("yeah, hoss")
        
if (__name__ == "__main__"):
    aio.run(aioMain())