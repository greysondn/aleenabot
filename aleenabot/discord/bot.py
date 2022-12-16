# This example requires the 'message_content' intent.

import argparse
import discord
import logging

class AleenaBotDiscord():
    # figuring out what intents I need is like
    # https://discordpy.readthedocs.io/en/stable/intents.html
    # provides checklist

    intents = discord.Intents.default()
    # auto_moderation
    # auto_moderation_configuration
    # auto_moderation_execution
    # bans
    # dm_messages
    # dm_reactions
    # dm_typing
    # emojis
    # emojis_and_stickers
    # guild_messages
    # guild_reactions
    # guild_scheduled_events
    # guild_typing
    # guilds
    # integrations
    # invites
    # members
    intents.message_content = True
    # messages
    # presences
    # reactions
    # typing
    # value
    # voice_states
    # webhooks

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

def main():
    parser = argparse.ArgumentParser(
                prog = 'AleenaBot',
                description = 'A robit to make other robits fear being robits',
                epilog = '(c) 2022 - now j. "greysondn" l.'
            )
    
    args = parser.parse_args()