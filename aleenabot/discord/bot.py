# This example requires the 'message_content' intent.

import argparse
import asyncio as aio
from typing import cast
import discord
import logging
from random import choice
from ruamel.yaml import YAML

def debugPrint(txt:str):
    if True:
        print(str)

# ruamel
yaml=YAML()
conf = yaml.load(open("aleena.yaml"))


_intents = conf.get("intents",{})
_mainconf = conf.get("core", {})


# intents
intents = discord.Intents.default()

intents.auto_moderation = _intents.get("auto_moderation", intents.auto_moderation)
intents.auto_moderation_configuration = _intents.get("auto_moderation_configuration", intents.auto_moderation_configuration)
intents.auto_moderation_execution = _intents.get("auto_moderation_execution", intents.auto_moderation_execution)
intents.bans = _intents.get("bans", intents.bans)
intents.dm_messages = _intents.get("dm_messages", intents.dm_messages)
intents.dm_reactions = _intents.get("dm_reactions", intents.dm_reactions)
intents.dm_typing = _intents.get("dm_typing", intents.dm_typing)
intents.emojis = _intents.get("emojis", intents.emojis)
intents.emojis_and_stickers = _intents.get("emojis_and_stickers", intents.emojis_and_stickers)
intents.guild_messages = _intents.get("guild_messages", intents.guild_messages)
intents.guild_reactions = _intents.get("guild_reactions", intents.guild_reactions)
intents.guild_scheduled_events = _intents.get("guild_scheduled_events", intents.guild_scheduled_events)
intents.guild_typing = _intents.get("guild_typing", intents.guild_typing)
intents.guilds = _intents.get("guilds", intents.guilds)
intents.integrations = _intents.get("integrations", intents.integrations)
intents.invites = _intents.get("invites", intents.invites)
intents.members = _intents.get("members", intents.members)
intents.messages = _intents.get("messages", intents.messages)
intents.presences = _intents.get("presences", intents.presences)
intents.reactions = _intents.get("reactions", intents.reactions)
intents.typing = _intents.get("typing", intents.typing)
intents.value = _intents.get("value", intents.value)
intents.voice_states = _intents.get("voice_states", intents.voice_states)
intents.webhooks = _intents.get("webhooks", intents.webhooks)
        
# client
client = discord.Client(
                                intents=intents
                            )



logHandler = logging.FileHandler(
                            filename=_mainconf.get("log_path", "discord_aleena.log"), 
                            encoding="utf-8",
                            mode="a"
                        )



@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

# ------------------------------------------------------------------------------

client.run(
                _mainconf.get("token", "ERROR, FORGOT YOUR TOKEN IN CONF"),
                log_handler=logHandler
        )

# bot
appid = aio.run(client.application_info())

# boot phrases
start_phrases = [
        "Johnny Five is ALIVE",                                               # Johnny 5
        "To act too soon could seal their fate.",                             # Sonic Underground opening
        "Would you like to play global thermonuclear war?",                   # WarGames
        "Your light is going out on me.",                                     # The Megas
]

print("-------------------------------------------------------------------")
print(choice(start_phrases))
print("-------------------------------------------------------------------")

# whack the button
print(discord.utils.oauth_url(appid.id))