import aleenabot.subprocess.helpers as hlp
import asyncio as aio

async def aioMain():
    main = hlp.Manager()
    proc = hlp.SubprocessWrapper(
            "python helloworld.py",
            name="Hello, World!",
            tg = main.tg
        )
    await proc.main()
    await main.start()
        
if (__name__ == "__main__"):
    aio.run(aioMain())