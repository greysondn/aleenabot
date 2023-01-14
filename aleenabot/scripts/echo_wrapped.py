import aleenabot.subprocess.wrappers as hlp
import asyncio as aio
import logging

# logging.basicConfig(level=logging.DEBUG)

async def aioMain():
    main = hlp.Manager()
    proc = hlp.SubprocessWrapper(
        'python',
        "C:\\Users\\Dorian Greyson\\git\\aleenabot\\aleenabot\\scripts\\echo.py",
        name = "echo",
        tg = main.tg
    )
    
    await main.addChild(proc)
    
    await main.start(cli=True)
    await main.wait()
    
if (__name__ == "__main__"):
    aio.run(aioMain())