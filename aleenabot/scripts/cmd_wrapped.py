import aleenabot.subprocess.wrappers as hlp
import asyncio as aio
import logging

logging.basicConfig(level=logging.DEBUG)

async def aioMain():
    main = hlp.Manager()
    proc = hlp.SubprocessWrapper(
        'cmd',
        "",
        name = "cmd",
        tg = main.tg
    )
    
    await main.addChild(proc)
    
    await main.start()
    await main.wait()
    
if (__name__ == "__main__"):
    aio.run(aioMain())