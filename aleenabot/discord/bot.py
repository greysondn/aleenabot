# This example requires the 'message_content' intent.

import argparse
import discord
import logging

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

        @self.client.event
        async def on_ready():
            print(f'We have logged in as {self.client.user}')

        @self.client.event
        async def on_message(message):
            if message.author == self.client.user:
                return

            if message.content.startswith('$hello'):
                await message.channel.send('Hello!')


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

def main():
    parser = argparse.ArgumentParser(
                prog = 'AleenaBot',
                description = 'A robit to make other robits fear being robits',
                epilog = '(c) 2022 - now j. "greysondn" l.'
            )
    
    args = parser.parse_args()