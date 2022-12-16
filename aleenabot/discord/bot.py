# This example requires the 'message_content' intent.
import asyncio as aio
import discord
from ruamel.yaml import YAML

# load yaml conf
yaml = YAML()
conf = yaml.load(open("aleena.yaml"))

# intents
intents = discord.Intents.default()
intents.message_content = True

# ignite client
client = discord.Client(intents=intents)

# client events
@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if (message.author != client.user):
        if str(message.channel.id) in conf["discord"]["channels"]["listen"]:
            if message.content.startswith('$hello'):
                await message.channel.send('Hello!')

# run it - perma block, must be last
client.run(conf["discord"]["core"]["token"])