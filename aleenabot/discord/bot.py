# This example requires the 'message_content' intent.

import argparse
import asyncio as aio
import discord
import logging
from random import choice
from ruamel.yaml import YAML

# godawful scoping
client:discord.Client   = None  # type: ignore 
bot:"AleenaBotDiscord"  = None  # type: ignore

class AleenaBotDiscord():
    def __init__(self, conf:dict):
        # config
        self.conf = conf.get("discord", {})
        
        # intents
        self.intents = discord.Intents.default()
        _intents = self.conf.get("intents",{})
        self.intents.auto_moderation = _intents.get("auto_moderation", self.intents.auto_moderation)
        self.intents.auto_moderation_configuration = _intents.get("auto_moderation_configuration", self.intents.auto_moderation_configuration)
        self.intents.auto_moderation_execution = _intents.get("auto_moderation_execution", self.intents.auto_moderation_execution)
        self.intents.bans = _intents.get("bans", self.intents.bans)
        self.intents.dm_messages = _intents.get("dm_messages", self.intents.dm_messages)
        self.intents.dm_reactions = _intents.get("dm_reactions", self.intents.dm_reactions)
        self.intents.dm_typing = _intents.get("dm_typing", self.intents.dm_typing)
        self.intents.emojis = _intents.get("emojis", self.intents.emojis)
        self.intents.emojis_and_stickers = _intents.get("emojis_and_stickers", self.intents.emojis_and_stickers)
        self.intents.guild_messages = _intents.get("guild_messages", self.intents.guild_messages)
        self.intents.guild_reactions = _intents.get("guild_reactions", self.intents.guild_reactions)
        self.intents.guild_scheduled_events = _intents.get("guild_scheduled_events", self.intents.guild_scheduled_events)
        self.intents.guild_typing = _intents.get("guild_typing", self.intents.guild_typing)
        self.intents.guilds = _intents.get("guilds", self.intents.guilds)
        self.intents.integrations = _intents.get("integrations", self.intents.integrations)
        self.intents.invites = _intents.get("invites", self.intents.invites)
        self.intents.members = _intents.get("members", self.intents.members)
        self.intents.messages = _intents.get("messages", self.intents.messages)
        self.intents.presences = _intents.get("presences", self.intents.presences)
        self.intents.reactions = _intents.get("reactions", self.intents.reactions)
        self.intents.typing = _intents.get("typing", self.intents.typing)
        self.intents.value = _intents.get("value", self.intents.value)
        self.intents.voice_states = _intents.get("voice_states", self.intents.voice_states)
        self.intents.webhooks = _intents.get("webhooks", self.intents.webhooks)
        
        # client
        self.client = discord.Client(
                                        intents=self.intents
                                    )
        client = self.client
        
        # analog to self
        bot = self
        
    def run(self):
        _conf = self.conf.get("core",{})
        logHandler = logging.FileHandler(
                                    filename=_conf.get("log_path", "discord_aleena.log"), 
                                    encoding="utf-8",
                                    mode="a"
                                )

        self.client.run(
                        _conf.get("token", "ERROR, FORGOT YOUR TOKEN IN CONF"),
                        log_handler=logHandler
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

def main():
    # argparse all of one input
    parser = argparse.ArgumentParser(
                prog = 'AleenaBot',
                description = 'A robit to make other robits fear being robits',
                epilog = '(c) 2022 - now j. "greysondn" l.'
            )
    
    parser.add_argument("conf")
    args = parser.parse_args()
    
    # ruamel
    yaml = YAML()
    confFile = yaml.load(args.conf)
    
    
    
    # bot
    bot = AleenaBotDiscord(confFile)
    appid = aio.run(bot.client.application_info())
    
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
    bot.run()

if (__name__ == "__main__"):
    main()