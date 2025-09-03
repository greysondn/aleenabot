# This example requires the 'message_content' intent.
import asyncio
import asyncio.subprocess
import discord
import logging
import pytz
import re
import subprocess
import sys
import time

from .helpers import BotLogger
from .helpers import getCurrentUTCTime
from .state import State

from ..database.database import db as database
from ..database.database import initDB

from ..database.database import Permission
from ..database.database import Permissions
from ..database.database import User

from ..database.database import DiscordUser

from ..database.database import MinecraftAdvancement
from ..database.database import MinecraftDeath
from ..database.database import MinecraftDeathCause
from ..database.database import MinecraftDeathObject
from ..database.database import MinecraftDeathSource
from ..database.database import MinecraftDeathTaunt
from ..database.database import MinecraftInstance
from ..database.database import MinecraftUser
from ..database.database import MinecraftUserAdvancement

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from discord.ext import commands
from discord.ext.commands import cooldown
from discord.ext.commands import BucketType
from pathlib import Path
from peewee import fn
from typing import cast

# Set up logging with rotation
BotLogger()
logger              = logging.getLogger(__name__)
unrecognized_logger = logging.getLogger("unrecognized")

# initialize state
bot_state = State()
bot_state.loadFromConfig(Path(__file__).parent / ".." / ".."/ "config.yaml")

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------------------------------------------------------------
# Database Helpers
# ------------------------------------------------------------------------------
def minecraftNameToMinecraftUser(name:str):
    return MinecraftUser.get_or_none(name=name)

def minecraftNameToUser(name:str):
    swp = minecraftNameToMinecraftUser(name)
    
    if (swp is not None):
        ret = swp.user
    
    return ret

# ------------------------------------------------------------------------------
# Minecraft server input helpers
# ------------------------------------------------------------------------------

async def inputToMinecraftConsole(message, discord_channel):
    """Send as input to minecraft console whatever this message is"""
    global bot_state
    
    # make sure server is running
    if ((not bot_state.server_running) or (bot_state.server_process is None)):
        raise Exception("Server is not running!")
    
    # actually try sending message
    try:
        bot_state.server_process.stdin.write(f"{message}\n".encode("utf-8")) #type: ignore
        await bot_state.server_process.stdin.drain() #type: ignore
        logger.info(f"Sent to server: {message}")
    except Exception as e:
        await discord_channel.send(f"Error sending message: {str(e)}")
        logger.error(f"Error sending message: {e}")
        raise Exception({e})
        
# ------------------------------------------------------------------------------
# Minecraft server output helpers
# ------------------------------------------------------------------------------

async def handle_chat(player, message, discord_channel):
    """Handle chat messages and in-game commands."""
    global bot_state
    
    await bot_state.handle_action()
    
    user = minecraftNameToUser(player)
    
    if (user is not None):
        name = user.displayName
    else:
        name = player
    
    await discord_channel.send(f"**{name}**: {message}")

# TODO: Write this function
async def send_to_server(msg):
    pass

async def handle_join(player, discord_channel):
    """Handle player join events."""
    global bot_state
    
    await bot_state.activate_player(player)
    
    await discord_channel.send(f"**{player} joined the game**")
    
    # await apply_op_status()

async def handle_leave(line, player, discord_channel):
    """Handle player leave events."""
    global bot_state
    await bot_state.deactivate_player(player)
    await discord_channel.send(f"**{player} left the game**")

async def handle_system_item(line, action, data, discord_channel):
    pass


async def handle_death(line, name, cause, source, indirectSource, obj, discord_channel):
    """Handle death events with custom fields."""
    # Validate inputs
    for var, value in [("name", name), ("cause", cause), ("source", source), ("indirectSource", indirectSource), ("obj", obj)]:
        if value is not None and not isinstance(value, str):
            logger.error(f"Invalid {var} type in handle_death: {value} (type: {type(value)})")
            return

    # Resolve instance
    global current_instance
    mcInstance = MinecraftInstance.get_or_create(name=bot_state.current_instance or "default")[0]

    # Resolve user
    mcUser = minecraftNameToMinecraftUser(name)

    # Set defaults
    cause = cause or "none"
    source = source or "none"
    indirectSource = indirectSource or "none"
    obj = obj or "none"

    # Create DB objects
    try:
        mcCause = MinecraftDeathCause.get_or_create(name=cause)[0]
        mcSource = MinecraftDeathSource.get_or_create(name=source)[0]
        mcIndirectSource = MinecraftDeathSource.get_or_create(name=indirectSource)[0]
        mcObject = MinecraftDeathObject.get_or_create(name=obj)[0]

        # Log death
        MinecraftDeath.create(
            cause=mcCause,
            deathString=line,
            deathObject=mcObject,
            user=mcUser,
            source=mcSource,
            indirectSource=mcIndirectSource,
            instance=mcInstance,
            datetime=getCurrentUTCTime()
        )
        logger.info(f"Logged death for {name}: {cause}")
    except Exception as e:
        logger.error(f"Error logging death for {name}: {e}")
        await discord_channel.send(f"Error logging death: {str(e)}")

    # TODO: Add death taunting
    # await discord_channel.send(f"**{name} died: {cause}**")

async def handle_server_output(line, discord_channel):
    """Handle server output, parsing chat, advancements, items, deaths."""
    global bot_state
    
    logger.info(f"Server: {line}")

    # Check line and discord_channel
    if not isinstance(line, str):
        logger.error(f"Non-string line received: {line} (type: {type(line)})")
        unrecognized_logger.debug(f"Unrecognized server output: {line}")
        return
    if not line.strip():  # Skip empty lines
        logger.debug("Skipping empty line")
        return
    if not isinstance(discord_channel, discord.TextChannel):
        logger.error(f"Invalid discord_channel: {discord_channel} (type: {type(discord_channel)})")
        return

    # Regex patterns
    chat_pattern = re.compile(r"\[Server thread/INFO\] \[minecraft/Server\]: <([^>]+)> (.+)")
    join_pattern = re.compile(r"\[Server thread/INFO\]: (\S+) joined the game")
    leave_pattern = re.compile(r"\[Server thread/INFO\]: (\S+) left the game")
    advancement_pattern = re.compile(r"\[Server thread/INFO\]: (\S+) has made the advancement \[(.+)\]")
    default_death_pattern = re.compile(
        r"\[Server thread/INFO\]: (?P<player>\S+) (?P<cause>was slain by|fell from a high place|drowned|burned to death|hit the ground too hard|died from dehydration|was blown up by|was killed by)(?: (?P<source>\S+))?(?: (?P<details>.+))?"
    )
    system_item_pattern = re.compile(r"\[Server thread/INFO\] \[minecraft/Server\]: <System> items (add|remove|query) (.+)")
    action_pattern = re.compile(r"\[Server thread/INFO\]: (\S+) (placed|mined|broke|used|crafted).+")

    # Ignored patterns from config
    ignored_patterns = [re.compile(p) for p in bot_state.config.get("ignored_patterns", [])]

    # Custom death patterns from config
    custom_death_patterns = []
    for name, p in bot_state.config.get("death_patterns", {}).items():
        try:
            if not isinstance(p, dict) or "pattern" not in p:
                logger.error(f"Invalid death pattern for {name}: expected dict with 'pattern' key, got {p}")
                continue
            custom_death_patterns.append((name, re.compile(p["pattern"])))
            logger.debug(f"Loaded death pattern {name}: {p['pattern']}")
        except re.error as e:
            logger.error(f"Invalid regex in death pattern {name}: {e}")
        except Exception as e:
            logger.error(f"Failed to load death pattern {name}: {e}")
    
    with database.atomic():
        # Check ignored patterns first
        if any(p.search(line) for p in ignored_patterns):
            logger.debug(f"Ignored line: {line}")
            return

        # Process known patterns
        try:
            if match := chat_pattern.search(line):
                player, message = match.groups()
                await handle_chat(player, message, discord_channel)
            elif match := join_pattern.search(line):
                player = match.group(1)
                await handle_join(player, discord_channel)
            elif match := leave_pattern.search(line):
                player = match.group(1)
                await handle_leave(line, player, discord_channel)
            elif match := advancement_pattern.search(line):
                player, advancement = match.groups()
                # TODO: Handle
                # await handle_advancement(line, player, advancement, discord_channel)
            elif match := default_death_pattern.search(line):
                groups = match.groupdict()
                await handle_death(
                    line,
                    name=groups.get("player", "unknown"),
                    cause=groups.get("cause", "none"),
                    source=groups.get("source", None),
                    indirectSource=None,  # Not captured
                    obj=groups.get("details", None),
                    discord_channel=discord_channel
                )
            else:
                # Process custom death patterns safely
                for name, pattern in custom_death_patterns:
                    if match := pattern.search(line):
                        groups = match.groupdict()
                        logger.debug(f"Custom death match for pattern '{name}': {groups}")
                        await handle_death(
                            line,
                            name=groups.get("name", "unknown"),
                            cause=groups.get("cause", "none"),
                            source=groups.get("source", None),
                            indirectSource=groups.get("indirectsource", None),
                            obj=groups.get("details", None),
                            discord_channel=discord_channel
                        )
                        break
                else:
                    unrecognized_logger.debug(f"Unrecognized server output: {line}")
        except Exception as e:
            logger.error(f"Error handling server output '{line}': {e}", exc_info=True)

# ------------------------------------------------------------------------------
# Minecraft server binary helpers
# ------------------------------------------------------------------------------
async def check_idle_shutdown(discord_channel):
    """Check for idle server and shut down after timeout."""
    global bot_state
    
    while bot_state.server_running:
        if ((time.time() - bot_state.last_player_activity) > bot_state.idle_timeout): # type: ignore
            await discord_channel.send(f"No players active for {bot_state.idle_timeout} seconds, shutting down...")
            logger.info(f"Idle timeout reached, shutting down server")
            await stop_server(discord_channel)
            break
        await asyncio.sleep(10)

async def run_sync_script(sync_script):
    """Run the sync script for an instance."""
    sync_script = Path(sync_script)
    if not sync_script.exists():
        logger.error(f"Sync script {sync_script} not found")
        return False
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(sync_script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=sync_script.parent
        )
        stdout, stderr = await process.communicate()
        if stdout:
            logger.info(f"Sync script output: {stdout.decode().strip()}")
        if stderr:
            logger.error(f"Sync script error: {stderr.decode().strip()}")
        if process.returncode == 0:
            logger.info("Sync script completed successfully")
            return True
        else:
            logger.error(f"Sync script failed with code {process.returncode}")
            return False
    except Exception as e:
        logger.error(f"Failed to run sync script: {e}")
        return False

async def run_mmm(mmm_script):
    """Run the mmm executable for an instance."""
    mmm_script = Path(mmm_script)
    if not mmm_script.exists():
        logger.error(f"mmm script {mmm_script} not found")
        return False
    try:
        process = await asyncio.create_subprocess_exec(
            str(mmm_script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=mmm_script.parent
        )
        stdout, stderr = await process.communicate()
        if stdout:
            logger.info(f"mmm output: {stdout.decode().strip()}")
        if stderr:
            logger.error(f"mmm error: {stderr.decode().strip()}")
        if process.returncode == 0:
            logger.info("mmm completed successfully")
            return True
        else:
            logger.error(f"mmm failed with code {process.returncode}")
            return False
    except Exception as e:
        logger.error(f"Failed to run mmm: {e}")
        return False

# TODO: Fix Logic
async def read_stream(stream, callback):
    """Read a stream asynchronously."""
    # Regex to strip ANSI escape codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            try:
                # Decode bytes to string
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace").strip()
                elif isinstance(line, dict):
                    logger.error(f"Received dict in stream: {line}")
                    continue
                elif not isinstance(line, str):
                    logger.error(f"Unexpected line type {type(line)}: {line}")
                    continue
                # Strip ANSI codes
                line = ansi_escape.sub('', line).strip()
                await callback(line)
            except Exception as e:
                logger.error(f"Error processing line '{line}': {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error reading stream: {e}", exc_info=True)

# TODO: Fix Logic
async def start_server(discord_channel, instance_name="default"):
    """Start the Minecraft server after running sync and mmm."""
    global bot_state
    
    if (bot_state.server_running):
        await discord_channel.send("Server is already running!")
        return

    instance = cast(dict, bot_state.instances.get(instance_name))
    server_dir = Path(instance["server_dir"])  # Instance-specific
    java_path = instance.get("java_path", "java")
    sync_script = instance.get("sync_script", None)
    mmm_script = instance.get("mmm", None)
    server_jar = instance.get("jar", None)
    launch_script = instance.get("script")
    server_args = instance.get("args", [])
    
    bot_state.current_instance = instance_name # type: ignore

    # Ensure server_dir exists
    if not server_dir.exists():
        await discord_channel.send(f"Server directory {server_dir} does not exist!")
        logger.error(f"Server directory {server_dir} does not exist")
        return

    # Run sync script if specified
    if sync_script and sync_script != "null":
        if not await run_sync_script(sync_script):
            await discord_channel.send("Sync script failed, aborting server start.")
            logger.error("Aborting server start due to sync script failure")
            return

    # Run mmm script if specified
    if mmm_script and mmm_script != "null":
        if not await run_mmm(mmm_script):
            await discord_channel.send("mmm script failed, aborting server start.")
            logger.error("Aborting server start due to mmm failure")
            return

    try:
        if launch_script and launch_script != "null":
            # Launch via shell script
            if not Path(launch_script).exists():
                await discord_channel.send(f"Launch script {launch_script} does not exist!")
                logger.error(f"Launch script {launch_script} does not exist")
                return
            server_process = await asyncio.create_subprocess_exec(
                "/bin/sh",
                launch_script,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=server_dir
            )
            logger.info(f"Started server via script {launch_script} (instance: {instance_name})")
        else:
            # Launch via Java
            server_process = await asyncio.create_subprocess_exec(
                java_path,
                *server_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=server_dir
            )
            logger.info(f"Started server via Java command (instance: {instance_name})")
        
        
        if server_process.returncode is not None:
            bot_state.server_running = False
            bot_state.server_process = None
            await discord_channel.send("Server failed to start (process died).")
            logger.error("Server process died immediately")
            return
        
        bot_state.server_running = True
        bot_state.last_player_activity = time.time()
        bot_state.save()
        await discord_channel.send(f"Minecraft server started (instance: {instance_name})!")
        logger.info(f"Server started (instance: {instance_name})")

        asyncio.create_task(read_stream(bot_state.server_process.stdout, lambda line: handle_server_output(line, discord_channel))) # type: ignore
        asyncio.create_task(read_stream(bot_state.server_process.stderr, lambda line: handle_server_output(line, discord_channel))) # type: ignore
        # TODO: Implement idle shutdown correctly and enable it
        #       Hint: You need enough parsing to see if players are active or not
        # asyncio.create_task(check_idle_shutdown(discord_channel))

        await bot_state.server_process.wait() # type: ignore
        bot_state.server_running = False
        bot_state.clear()
        await discord_channel.send("Minecraft server stopped.")
        logger.info("Server stopped")

    except Exception as e:
        bot_state.server_running = False
        bot_state.server_process = None
        await discord_channel.send(f"Failed to start server: {str(e)}")
        logger.error(f"Failed to start server: {e}")

# TODO: Fix Logic
async def stop_server(discord_channel):
    """Stop the Minecraft server gracefully."""
    global bot_state
    if not bot_state.server_running or bot_state.server_process is None:
        await discord_channel.send("Server is not running!")
        return

    try:
        await inputToMinecraftConsole("stop", discord_channel)
        await discord_channel.send("Sent stop command to server...")
        logger.info("Sent stop command")
        try:
            return_code = await asyncio.wait_for(bot_state.server_process.wait(), timeout=600)
            if return_code == 0:
                await discord_channel.send("Server stopped gracefully (exit code 0).")
                logger.info("Server stopped gracefully (exit code 0)")
            else:
                await discord_channel.send(f"Server stopped with error (exit code {return_code}).")
                logger.warning(f"Server stopped with error (exit code {return_code})")
        except asyncio.TimeoutError:
            bot_state.server_process.terminate()
            try:
                await asyncio.wait_for(bot_state.server_process.wait(), timeout=5)
                await discord_channel.send("Server terminated after timeout.")
                logger.warning("Server terminated after timeout")
            except asyncio.TimeoutError:
                bot_state.server_process.kill()
                await discord_channel.send("Server forcefully killed.")
                logger.warning("Server forcefully killed")
    except Exception as e:
        await discord_channel.send(f"Error stopping server: {str(e)}")
        logger.error(f"Error stopping server: {e}")
    finally:
        bot_state.server_running = False
        bot_state.server_process = None
        bot_state.current_instance = None
        bot_state.clear()

# ------------------------------------------------------------------------------
# Permission Helpers
# ------------------------------------------------------------------------------
def hasPermission(user:User, permissionName:str) -> bool:
    """Check if user has permission for a command."""
    ret = False
    
    with database.atomic():
        # normal check
        permission = Permission.get_or_none(name=permissionName)
        
        if (permission is not None):
            grant = Permissions.get_or_none(user=user, permission=permission)
            
            if (grant is not None):
                if grant.active:
                    ret = True
                    
        # check for admin
        if (ret == False):
            permission = Permission.get(name="bot:admin")
            grant = Permissions.get_or_none(user=user, permission=permission)
            if (grant is not None):
                ret = True
    
    return ret

def hasPermissionDiscord(discordId:str, permissionName:str) -> bool:
    '''Check if user has permission for a command using their discord ID'''
    ret = False
    
    with database.atomic():
        # discord user exists?
        discordUser = DiscordUser.get_or_none(accountid = discordId)
        if (discordUser is not None):
            user = discordUser.user
            ret = hasPermission(user, permissionName)
    
    return ret
    

# ------------------------------------------------------------------------------
# Bot events
# ------------------------------------------------------------------------------

# TODO: Fix Logic
@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user}")
    
    # local hook globals
    global bot_state
    
    # try to grab admin data
    admin_account = await(bot.fetch_user(bot_state.default_admin_id))
    admin_accountID = admin_account.id
    admin_name = admin_account.global_name
    admin_displayName = admin_account.display_name
    
    # try to access channel
    channel = bot.get_channel(bot_state.discord_channel_id)
    if (channel is None):
        channel = await bot.fetch_channel(bot_state.discord_channel_id)
    
    if not channel:
        logger.error(f"Cannot access Discord channel {bot_state.discord_channel_id}")
        sys.exit(1)
        
    # init and hook database
    try:
        initDB("mysql", bot_state.db_config)
        with database.atomic():
            logger.info("Connected to MariaDB")
    except Exception as e:
        logger.error(f"Failed to connect to MariaDB: {e}")
        sys.exit(1)
        
    # connect and/or create admin for database
    with database.atomic():
        # try to find, one piece at a time
        permission = None
        permission = Permission.get_or_none(name="bot:admin")
        if (permission is None):
            permission = Permission.create(name="bot:admin", description="a user with admin level for all bot operations")

        permissionGrant = None
        permissionGrant = Permissions.get_or_none(permission=permission)
        if (permissionGrant is None):
            # uh oh
            user = User.get_or_create(name=admin_name, displayName=admin_displayName)[0]
            dUser = DiscordUser.get_or_create(user=user, accountid = admin_accountID)[0]
            permissionGrant = Permissions.get_or_create(user=user, permission=permission, active=True, datetime=getCurrentUTCTime(), reason="Granted via config file")

    # Initialize scheduler
    scheduler = AsyncIOScheduler(timezone=pytz.UTC)
    scheduler.start()
    logger.info("Scheduler started")
    
    # Schedule weekly messages from config
    for sch_msg_config in bot_state.scheduled_messages:
        try:
            sch_channel_id = int(sch_msg_config["channel_id"])
            message = sch_msg_config["message"]
            cron_schedule = sch_msg_config.get("cron_schedule", "0 9 * * 6")
            timezone_str = sch_msg_config.get("timezone", "America/New_York")
            sch_channel = bot.get_channel(sch_channel_id) or await bot.fetch_channel(sch_channel_id)
            if not isinstance(sch_channel, discord.TextChannel):
                logger.error(f"Invalid channel ID {sch_channel_id} for scheduled message")
                continue
            
            try:
                tz = pytz.timezone(timezone_str)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.error(f"Invalid timezone {timezone_str} for channel {sch_channel_id}")
                continue
            
            async def send_scheduled_message():
                logger.debug(f"[{datetime.now(pytz.UTC)}] Attempting to send scheduled message to channel {sch_channel_id}: {message}")
                try:
                    await sch_channel.send(message) # type: ignore
                    logger.info(f"Sent scheduled message to channel {sch_channel_id}: {message}")
                except Exception as e:
                    logger.error(f"Failed to send scheduled message to {sch_channel_id}: {e}")
            
            job = scheduler.add_job(
                send_scheduled_message,
                trigger=CronTrigger.from_crontab(cron_schedule, timezone=tz),
                id=f"scheduled_message_{sch_channel_id}_{hash(message)}",
                replace_existing=True
            )
            logger.info(f"Scheduled message for channel {sch_channel_id}: {message} with cron {cron_schedule} in {timezone_str}")
            logger.debug(f"Next run time for {sch_channel_id}: {job.next_run_time}")
        except Exception as e:
            logger.error(f"Failed to schedule message for channel {sch_channel_id}: {e}")

    # Log all scheduled jobs
    for job in scheduler.get_jobs():
        logger.debug(f"Job {job.id}: next run at {job.next_run_time}")

    # check for clean shutdown
    state = bot_state.load()
    if state and state.get("server_running"):
        logger.warning("Detected potential crash: server_running=True in state.json")
        pid = None
        try:
            result = subprocess.run(["pgrep", "-f", "java.*server.jar"], capture_output=True, text=True)
            pid = int(result.stdout.strip()) if result.stdout.strip() else None
        except Exception as e:
            logger.error(f"Failed to check Java process: {e}")
        if pid:
            logger.info(f"Java process (PID {pid}) still running, attempting to stop")
            try:
                subprocess.run(["kill", "-TERM", str(pid)], check=True)
                await asyncio.sleep(5)
                if subprocess.run(["pgrep", "-f", "java.*server.jar"]).returncode == 0:
                    subprocess.run(["kill", "-KILL", str(pid)], check=True)
                    logger.warning(f"Killed lingering Java process (PID {pid})")
            except Exception as e:
                logger.error(f"Failed to stop Java process: {e}")
        bot_state.server_running = False
        bot_state.server_process = None
        bot_state.active_players = set()
        bot_state.last_player_activity = None
        bot_state.current_instance = None
        bot_state.clear()
        await channel.send("Detected crash (server was running). Cleaned up state.") # type: ignore
    else:
        logger.info("No crash detected, starting fresh")
        await channel.send("God has decided to let me live another day, and I'm about to make it everyone's problem.") # type: ignore
        
# TODO: Fix Logic
@bot.command()
@cooldown(1, 10, BucketType.user)
async def startserver(ctx, instance_name="[none given]"):
    global bot_state
    """Start the server with specified instance."""
    if not hasPermissionDiscord(str(ctx.author.id), "bot:command:startserver"):
        await ctx.send("You don't have permission!")
        return
    if instance_name not in bot_state.instances:
        await ctx.send(f"Unknown instance: {instance_name}. Available: {', '.join(bot_state.instances.keys())}")
        return
    await start_server(ctx.channel, instance_name)

# TODO: Fix Logic
@bot.command()
@cooldown(1, 10, BucketType.user)
async def stopserver(ctx):
    """Stop the server."""
    if hasPermissionDiscord(str(ctx.author.id), "bot:command:stopserver"):
        await ctx.send("You don't have permission")
        return
    await stop_server(ctx.channel)

'''
# TODO: Fix Logic
@bot.event
async def on_message(message):
    """Relay Discord messages to Minecraft (excluding commands)."""
    if message.author.bot or message.channel.id != DISCORD_CHANNEL_ID:
        return
    if not message.content.startswith("!"):
        global server_process, server_running
        if server_running and server_process:
            try:
                user = User.get_or_none(User.discord_id == message.author.id)
                name = user.minecraft_id or message.author.name
                server_process.stdin.write(f"say [Discord] {name}: {message.content}\n".encode("utf-8"))
                await server_process.stdin.drain()
                logger.info(f"Relayed Discord message from {name}: {message.content}")
            except Exception as e:
                logger.error(f"Error relaying Discord message: {e}")
    await bot.process_commands(message)
'''

# TODO: Fix Logic
@bot.command()
@cooldown(1, 5, BucketType.user)
async def exec(ctx, message):
    """Send a message to the server."""
    global server_process
    global server_running
    
    # keep track of whether we had an error
    hadError = False
    
    # make sure user has permission
    try:
        if not hasPermissionDiscord(ctx.author.id, "bot:command:exec"):
            await ctx.send("You don't have permission!")
            return #TODO: fix multiple returns
    except Exception as e:
        await ctx.send(f"Error checking database: {e}")
        logger.error(f"Error checking database: {e}")
        hadError = True

    # send message to minecraft console
    try:
        await inputToMinecraftConsole(message, ctx)
    except Exception as e:
        await ctx.send(f"Error sending message: {str(e)}")
        logger.error(f"Error sending message: {e}")
        hadError = True
        
    # report back
    if (not hadError):
        await ctx.send(f"Sent to server: {message}")
        
    

'''
# TODO: Fix Logic
@bot.command()
async def advancements(ctx, player=None):
    """Check player advancements."""
    if not check_permission(ctx.author.id, "advancements"):
        await ctx.send("You don't have permission, you filthy mutt!")
        return
    try:
        user = User.get_or_none(User.discord_id == ctx.author.id)
        target_player = player or (user.minecraft_id if user else None)
        if not target_player:
            await ctx.send("Player not found or you haven't linked a Minecraft ID.")
            return
        advancements = Advancement.select().join(User).where(User.minecraft_id == target_player)
        if advancements:
            msg = f"{target_player}'s advancements:\n" + "\n".join([f"- {a.advancement} ({a.timestamp})" for a in advancements])
        else:
            msg = f"{target_player} has no advancements."
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"Error fetching advancements: {str(e)}")
'''

'''
# TODO: Fix Logic
@bot.command()
async def awardadvancements(ctx, player=None):
    """Attempt to re-award stored advancements."""
    if not check_permission(ctx.author.id, "awardadvancements"):
        await ctx.send("You don't have permission, you filthy mutt!")
        return
    try:
        user = User.get_or_none(User.discord_id == ctx.author.id)
        target_player = player or (user.minecraft_id if user else None)
        if not target_player:
            await ctx.send("Player not found or you haven't linked a Minecraft ID.")
            return
        await award_advancements(target_player, ctx.channel)
    except Exception as e:
        await ctx.send(f"Error awarding advancements: {str(e)}")
'''

'''
# TODO: Fix Logic
@bot.command()
async def items(ctx, player=None, page=1):
    """Check player items with pagination."""
    if not check_permission(ctx.author.id, "items"):
        await ctx.send("You don't have permission, you filthy mutt!")
        return
    try:
        user = User.get_or_none(User.discord_id == ctx.author.id)
        target_player = player or (user.minecraft_id if user else None)
        if not target_player:
            await ctx.send("Player not found or you haven't linked a Minecraft ID.")
            return
        page = max(1, int(page))
        offset = (page - 1) * ITEMS_PER_PAGE
        items = Item.select().join(User).where(User.minecraft_id == target_player).order_by(Item.timestamp.desc()).offset(offset).limit(ITEMS_PER_PAGE)
        total_items = Item.select().join(User).where(User.minecraft_id == target_player).count()
        total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        if items:
            msg = f"{target_player}'s items (Page {page}/{total_pages}):\n"
            for item in items:
                item_data = json.loads(item.item_data)
                msg += "\n".join([f"- {i.get('id', 'unknown')} x{i.get('Count', 1)}" for i in item_data]) + f" ({item.timestamp})\n"
        else:
            msg = f"{target_player} has no recorded items on page {page}."
        await ctx.send(msg)
    except ValueError:
        await ctx.send("Invalid page number.")
    except Exception as e:
        await ctx.send(f"Error fetching items: {str(e)}")
'''

'''
# TODO: Fix Logic
@bot.command()
async def deaths(ctx, player=None):
    """Check player death stats."""
    if not check_permission(ctx.author.id, "deaths"):
        await ctx.send("You don't have permission, you filthy mutt!")
        return
    try:
        user = User.get_or_none(User.discord_id == ctx.author.id)
        target_player = player or (user.minecraft_id if user else None)
        if not target_player:
            await ctx.send("Player not found or you haven't linked a Minecraft ID.")
            return
        deaths = Death.select().join(User).where(User.minecraft_id == target_player)
        if deaths:
            total = sum(d.count for d in deaths)
            top_causes = Death.select(Death.cause, Death.count).join(User).where(User.minecraft_id == target_player).order_by(Death.count.desc()).limit(10)
            msg = f"{target_player}'s deaths: {total}\nTop causes:\n" + ("\n".join([f"- {d.cause} ({d.count})" for d in top_causes]) or "None")
        else:
            msg = f"{target_player} has no deaths."
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"Error fetching deaths: {str(e)}")
'''

'''
# TODO: Fix Logic
@bot.command()
async def serverdeaths(ctx):
    """Check server-wide death stats."""
    if not check_permission(ctx.author.id, "serverdeaths"):
        await ctx.send("You don't have permission, you filthy mutt!")
        return
    try:
        total_deaths = Death.select(fn.SUM(Death.count).alias("total")).scalar() or 0
        top_causes = Death.select(Death.cause, fn.SUM(Death.count).alias("total")).group_by(Death.cause).order_by(fn.SUM(Death.count).desc()).limit(10)
        top_players = Death.select(User.minecraft_id, fn.SUM(Death.count).alias("total")).join(User).group_by(User.minecraft_id).order_by(fn.SUM(Death.count).desc()).limit(5)
        msg = f"Server deaths: {total_deaths}\nTop causes:\n" + "\n".join([f"- {c.cause} ({c.total})" for c in top_causes]) + \
              "\nTop players:\n" + "\n".join([f"- {p.minecraft_id} ({p.total})" for p in top_players])
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"Error fetching server deaths: {str(e)}")
'''

@bot.command()
@cooldown(1, 5, BucketType.user)
async def users(ctx):
    """List all users with their Discord and Minecraft IDs, and admin status."""
    if not hasPermissionDiscord(str(ctx.author.id), "bot:command:users"):
        await ctx.send("You don't have permission")
        return

    try:
        with database.atomic():
            users = User.select().order_by(User.name)
            if not users.exists():
                await ctx.send("No users found in the database.")
                logger.info(f"{ctx.author.id} checked user list, no users found")
                return

            user_list = []
            admin_perm = Permission.get_or_none(Permission.name == "bot:admin")

            for user in users:
                # Get Discord ID (first account, if any)
                discord_id = "None"
                try:
                    discord_id = user.discord_accounts[0].accountid if user.discord_accounts else "None"
                except IndexError:
                    pass

                # Get Minecraft name/UUID (current account, if any)
                mc_name, mc_uuid = "None", "N/A"
                try:
                    mc_account = next((mc for mc in user.minecraft_accounts if mc.current), None)
                    if mc_account:
                        mc_name = mc_account.name
                        mc_uuid = mc_account.uuid
                except (IndexError, AttributeError):
                    pass

                # Check admin status
                is_admin = False
                if admin_perm:
                    is_admin = any(
                        grant.permission.id == admin_perm.id and grant.active
                        for grant in user.grants
                    )

                user_list.append({
                    "displayName": user.displayName,
                    "discord_id": discord_id,
                    "mc_name": mc_name,
                    "mc_uuid": mc_uuid,
                    "is_admin": is_admin
                })

            msg = "Users:\n" + "\n".join([
                f"- {u['displayName']} (Discord: {u['discord_id']}, MC: {u['mc_name']} [{u['mc_uuid']}], Admin: {'Yes' if u['is_admin'] else 'No'})"
                for u in user_list
            ])
            await ctx.send(msg)
            logger.info(f"{ctx.author.id} checked user list")
    except Exception as e:
        await ctx.send(f"Error checking users: {str(e)}")
        logger.error(f"Error checking users: {e}")

@bot.command()
@cooldown(1, 5, BucketType.user)
async def register(ctx, discord_id: str):
    """Register a new user with their Discord ID."""
    if not hasPermissionDiscord(str(ctx.author.id), "bot:command:register"):
        await ctx.send("You don't have permission")
        return

    if not discord_id.isdigit() or len(discord_id) < 17:
        await ctx.send("Invalid Discord ID. Must be a numeric ID (e.g., 123456789012345678).")
        return

    try:
        with database.atomic():
            # Check if Discord ID is already linked
            existing_discord = DiscordUser.get_or_none(DiscordUser.accountid == discord_id)
            if existing_discord:
                await ctx.send(f"Discord ID {discord_id} is already linked to user {existing_discord.user.displayName}.")
                return
            
            # try to fetch discord user for later use
            try:
                discord_user = await bot.fetch_user(int(discord_id))
            except Exception as e:
                logger.warning(f"Could not fetch Discord user for {discord_id}: {e}")
            
            # Determine global name of user on discord
            try:
                name = discord_user.global_name
            except Exception as e:
                logger.warning(f"Could not fetch Discord global name for {discord_id}: {e}")


            # Try to fetch Discord username for displayName
            try:
                display_name = discord_user.display_name
            except Exception as e:
                logger.warning(f"Could not fetch Discord display name for {discord_id}: {e}")

            # Create User and DiscordUser
            user = User.create(name=name, displayName=display_name)
            DiscordUser.create(user=user, accountid=discord_id)

            await ctx.send(f"Registered user {user.displayName} with Discord ID {discord_id}.")
            logger.info(f"{ctx.author.id} registered user {user.name} with Discord ID {discord_id}")
    except Exception as e:
        await ctx.send(f"Error registering user: {str(e)}")
        logger.error(f"Error registering user with Discord ID {discord_id}: {e}")



@bot.command()
@cooldown(1, 5, BucketType.user)
async def addperm(ctx, discord_id: str, permission: str):
    """Add a permission to a user by their Discord ID."""
    if not hasPermissionDiscord(str(ctx.author.id), "bot:command:addperm"):
        await ctx.send("You don't have permission")
        return

    if not discord_id.isdigit() or len(discord_id) < 17:
        await ctx.send("Invalid Discord ID. Must be a numeric ID (e.g., 123456789012345678).")
        return

    try:
        with database.atomic():
            # Find user by Discord ID
            discord_user = DiscordUser.get_or_none(DiscordUser.accountid == discord_id)
            if not discord_user:
                await ctx.send(f"No user found with Discord ID {discord_id}.")
                return
            target_user = discord_user.user

            # Create or get permission
            perm, _ = Permission.get_or_create(
                name=permission,
                defaults={"description": f"Permission {permission}"}
            )

            # Grant permission
            perm_grant, created = Permissions.get_or_create(
                user=target_user,
                permission=perm,
                defaults={
                    "active": True,
                    "datetime": getCurrentUTCTime(),
                    "reason": f"Granted by {ctx.author.id} via !addperm"
                }
            )

            if not created and not perm_grant.active:
                # Reactivate if previously deactivated
                perm_grant.active = True
                perm_grant.datetime = getCurrentUTCTime()
                perm_grant.reason = f"Reactivated by {ctx.author.id} via !addperm"
                perm_grant.save()

            await ctx.send(f"Added permission {permission} to {target_user.displayName}.")
            logger.info(f"{ctx.author.id} added permission {permission} to user {target_user.name} (Discord ID: {discord_id})")
    except Exception as e:
        await ctx.send(f"Error adding permission: {str(e)}")
        logger.error(f"Error adding permission {permission} for Discord ID {discord_id}: {e}")

@bot.command()
@cooldown(1, 5, BucketType.user)
async def listallpermissions(ctx):
    """List all permissions in the database."""
    if not hasPermissionDiscord(str(ctx.author.id), "bot:command:listpermissions"):
        await ctx.send("You don't have permission")
        return

    try:
        with database.atomic():
            permissions = Permission.select().order_by(Permission.name)
            if not permissions.exists():
                await ctx.send("No permissions found in the database.")
                logger.info(f"{ctx.author.id} checked permissions, none found")
                return

            perm_list = []
            for perm in permissions:
                active_grants = sum(1 for grant in perm.grants if grant.active)
                perm_list.append({
                    "name": perm.name,
                    "description": perm.description or "No description",
                    "active_grants": active_grants
                })

            msg = "Permissions:\n" + "\n".join([
                f"- {p['name']} (Description: {p['description']}, Active Grants: {p['active_grants']})"
                for p in perm_list
            ])
            await ctx.send(msg)
            logger.info(f"{ctx.author.id} listed permissions")
    except Exception as e:
        await ctx.send(f"Error listing permissions: {str(e)}")
        logger.error(f"Error listing permissions: {e}")

'''
# TODO: Fix Logic
@bot.command()
async def listperms(ctx, player=None):
    """List permissions for a player."""
    if not check_permission(ctx.author.id, "manage_permissions"):
        await ctx.send("You don't have permission, you filthy mutt!")
        return
    try:
        user = User.get_or_none(User.discord_id == ctx.author.id)
        target_player = player or (user.minecraft_id if user else None)
        if not target_player:
            await ctx.send("Player not found or you haven't linked a Minecraft ID.")
            return
        target_user = User.get(User.minecraft_id == target_player)
        perms = Permission.select().where(Permission.user == target_user)
        msg = f"Permissions for {target_player}:\n" + ("\n".join([f"- {p.command}" for p in perms]) or "None")
        await ctx.send(msg)
        logger.info(f"Listed permissions for {target_player} by {ctx.author.id}")
    except User.DoesNotExist:
        await ctx.send(f"Player {target_player} not found")
    except Exception as e:
        await ctx.send(f"Error listing permissions: {str(e)}")
        logger.error(f"Error listing permissions: {e}")
'''

'''
# TODO: Fix Logic
@bot.command()
async def link(ctx, minecraft_id):
    """Link Discord and Minecraft IDs."""
    try:
        with database.atomic():
            user, created = User.get_or_create(discord_id=ctx.author.id, defaults={"minecraft_id": minecraft_id})
            if not created:
                user.minecraft_id = minecraft_id
                user.save()
            await ctx.send(f"Linked {ctx.author.name} to Minecraft ID {minecraft_id}")
            logger.info(f"Linked {ctx.author.id} to {minecraft_id}")
    except Exception as e:
        await ctx.send(f"Error linking ID: {str(e)}")
        logger.error(f"Error linking {ctx.author.id} to {minecraft_id}: {e}")
'''
'''
# TODO: Fix Logic
@bot.command()
async def help(ctx):
    """List available commands."""
    commands = {
        "startserver": "Start the server (instance name optional).",
        "stopserver": "Stop the server.",
        # "say": "Send a message to the server.",
        # "advancements": "Check player advancements.",
        # "awardadvancements": "Re-award advancements to a player.",
        # "items": "Check player items (with pagination).",
        # "deaths": "Check player deaths.",
        # "serverdeaths": "Check server-wide death stats.",
        # "users": "List registered users.",
        # "addperm": "Add a permission for a player.",
        # "removeperm": "Remove a permission for a player.",
        # "listperms": "List permissions for a player.",
        # "link": "Link your Discord and Minecraft IDs.",
        "help": "Show this help message."
    }
    msg = "Commands:\n" + "\n".join([f"!{cmd}: {desc}" for cmd, desc in commands.items() if check_permission(ctx.author.id, cmd)])
    await ctx.send(msg)
'''

def main():
    global bot_state
    
    # Run the bot
    bot.run(bot_state.discord_token)
