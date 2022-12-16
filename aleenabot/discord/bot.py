# This example requires the 'message_content' intent.

import discord
import logging

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')


logHandler = logging.FileHandler(
                                    filename="discord.log", 
                                    encoding="utf-8",
                                    mode="a"
                                )


client.run(
                'your token here',
                log_handler=logHandler
          )