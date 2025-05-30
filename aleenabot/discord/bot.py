# This example requires the 'message_content' intent.
import asyncio
import asyncio.subprocess
import discord
import json
import logging
import logging.handlers
import re
import subprocess
import sys
import time
import yaml

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

from datetime import datetime
from datetime import timezone
from discord.ext import commands
from discord.ext.commands import cooldown
from discord.ext.commands import BucketType
from logging.handlers import RotatingFileHandler
from pathlib import Path
from peewee import fn
from peewee import JOIN

# Set up logging with rotation
handler = logging.handlers.RotatingFileHandler("minecraft_wrapper.log", maxBytes=10*1024*1024, backupCount=5)
unrecognized_handler = logging.handlers.RotatingFileHandler("unrecognized_server_output.log", maxBytes=1*1024*1024, backupCount=5)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), handler, unrecognized_handler]
)
logger = logging.getLogger(__name__)
unrecognized_logger = logging.getLogger("unrecognized")
unrecognized_handler.setLevel(logging.DEBUG)
unrecognized_logger.addHandler(unrecognized_handler)



# Load config from YAML
CONFIG_PATH = Path(__file__).parent / ".." / ".."/ "config.yaml"
try:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    logger.error(f"Failed to load config.yaml: {e}")
    sys.exit(1)

# Config variables
DISCORD_TOKEN = config["discord_token"]
DISCORD_CHANNEL_ID = config["discord_channel_id"]
DEFAULT_ADMIN_ID = config["default_admin_id"]
IDLE_TIMEOUT = config.get("idle_timeout", 300)
DB_CONFIG = config["database"]
INSTANCES = config["instances"]
ITEMS_PER_PAGE = config.get("items_per_page", 5)
STATE_FILE = Path(__file__).parent / "bot_state.json"

# globals
server_process = None
server_running = False
active_players = set()
last_player_activity = None
current_instance = None

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------------------------------------------------------------
# Generic Helpers
# ------------------------------------------------------------------------------
def getCurrentUTCTime() -> str:
    ret = ""
    
    swp = datetime.now()
    swp = swp.replace(tzinfo=timezone.utc)
    ret = swp.strftime('%Y-%m-%d %H:%M:%S.%f')
    
    return ret

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
    global server_process
    global server_running
    
    # make sure server is running
    if ((not server_running) or (server_process is None)):
        raise Exception("Server is not running!")
    
    # actually try sending message
    try:
        server_process.stdin.write(f"{message}\n".encode("utf-8")) #type: ignore
        await server_process.stdin.drain() #type: ignore
        logger.info(f"Sent to server: {message}")
    except Exception as e:
        await discord_channel.send(f"Error sending message: {str(e)}")
        logger.error(f"Error sending message: {e}")
        raise Exception({e})
        
# ------------------------------------------------------------------------------
# Minecraft server output helpers
# ------------------------------------------------------------------------------

async def handle_action():
    """Fires when a player does something, no matter what, on the server, that
       active interaction."""
    global last_player_activity
    last_player_activity = time.time()
    save_state()

async def activate_player(player):
    global active_players
    active_players.add(player)
    await handle_action()
    save_state()

async def deactivate_player(player):
    global active_players
    active_players.discard(player)
    save_state()

async def handle_chat(player, message, discord_channel):
    """Handle chat messages and in-game commands."""
    await handle_action()
    
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
    await activate_player(player)
    
    await discord_channel.send(f"**{player} joined the game**")
    
    # await apply_op_status()

async def handle_leave(line, player, discord_channel):
    """Handle player leave events."""
    await deactivate_player(player)
    await discord_channel.send(f"**{player} left the game**")

async def handle_system_item(line, action, data, discord_channel):
    pass


async def handle_death(line, name, cause, source, indirectSource, obj, discord_channel):
    """Handle death events with custom fields."""
    
    # resolve instance
    global current_instance
    mcInstance = MinecraftInstance. get_or_create(name = current_instance)[0]
    
    # resolve a user
    mcUser = minecraftNameToMinecraftUser(name)
    
    # set defaults past the break
    if cause == None:
        cause = "none"
    if source == None:
        source = "none"
    if indirectSource == None:
        indirectSource = "none"
    if obj == None:
        obj = "none"
    
    # fire up actual objects here    
    mcCause = MinecraftDeathCause.get_or_create(name = cause)[0]
    mcSource = MinecraftDeathSource.get_or_create(name = source)[0]
    mcIndirectSource = MinecraftDeathSource.get_or_create(name = indirectSource)[0]
    mcObject = MinecraftDeathObject.get_or_create(name = obj)[0]
    
    # log the death, yeah!
    MinecraftDeath.create(
        cause = mcCause,
        deathString = line,
        deathObject = mcObject,
        user = mcUser,
        source = mcSource,
        indirectSource = mcIndirectSource,
        instance = mcInstance,
        datetime = getCurrentUTCTime()
    )
    
    #TODO: add death taunting
    # await discord_channel.send(f"**{player} died: {cause}**")

async def handle_server_output(line, discord_channel):
    """Handle server output, parsing chat, advancements, items, deaths."""
    global active_players, last_player_activity
    logger.info(f"Server: {line}")

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
    ignored_patterns = [re.compile(p) for p in config.get("ignored_patterns", [])]

    # Custom death patterns from config
    custom_death_patterns = [(name, re.compile(p)) for name, p in config.get("death_patterns", {}).items()]

    with database.atomic():
        # Check ignored patterns first
        if any(p.search(line) for p in ignored_patterns):
            logger.debug(f"Ignored line: {line}")
            return

        # Process known patterns
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
            await handle_death(
                line,
                name=match.group("name"),
                cause=match.group("cause"),
                source=match.group("source"),
                indirectSource=match.group("indirectsource"),
                obj=match.group("details"),
                discord_channel=discord_channel
            )
        elif any(match := p.search(line) for _, p in custom_death_patterns):
            # Use first matching custom pattern
            await handle_death(
                line,
                name=match.group("name"),
                cause=match.group("cause"),
                source=match.group("source"),
                indirectSource=match.group("indirectsource"),
                obj=match.group("details"),
                discord_channel=discord_channel
            )
        elif match := system_item_pattern.search(line):
            action, data = match.groups()
            await handle_system_item(line, action, data, discord_channel)
        elif match := action_pattern.search(line):
            player = match.group(1)
            await handle_action()
        else:
            unrecognized_logger.debug(f"Unrecognized server output: {line}")



# ------------------------------------------------------------------------------
# Minecraft server binary helpers
# ------------------------------------------------------------------------------
async def check_idle_shutdown(discord_channel):
    """Check for idle server and shut down after timeout."""
    global last_player_activity
    global server_running
    
    while server_running:
        if (time.time() - last_player_activity) > IDLE_TIMEOUT: # type: ignore
            await discord_channel.send(f"No players active for {IDLE_TIMEOUT} seconds, shutting down...")
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
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            try:
                # Decode bytes to string, handle non-standard inputs
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace").strip()
                elif isinstance(line, dict):
                    logger.error(f"Received dict in stream: {line}")
                    continue
                elif not isinstance(line, str):
                    logger.error(f"Unexpected line type {type(line)}: {line}")
                    continue
                await callback(line)
            except Exception as e:
                logger.error(f"Error processing line '{line}': {e}")
    except Exception as e:
        logger.error(f"Error reading stream: {e}")

# TODO: Fix Logic
async def start_server(discord_channel, instance_name="default"):
    """Start the Minecraft server after running sync and mmm."""
    global server_process, server_running, last_player_activity, current_instance
    if server_running:
        await discord_channel.send("Server is already running!")
        return

    instance = INSTANCES.get(instance_name)
    server_dir = Path(instance["server_dir"])  # Instance-specific
    java_path = instance.get("java_path", "java")
    sync_script = instance.get("sync_script", "sync.py")
    mmm_script = instance.get("mmm", "mmm")
    server_jar = instance["jar"]
    server_args = instance.get("args", ["-Xmx4G", "-Xms2G", "-jar", server_jar, "nogui"])
    current_instance = instance_name

    # Ensure server_dir exists
    if not server_dir.exists():
        await discord_channel.send(f"Server directory {server_dir} does not exist!")
        logger.error(f"Server directory {server_dir} does not exist")
        return

    # TODO: enable below blocks, holy shit dude

    # if not await run_sync_script(sync_script):
    #    await discord_channel.send("Sync script failed, aborting server start.")
    #    logger.error("Aborting server start due to sync script failure")
    #    return

    # if not await run_mmm(mmm_script):
    #    await discord_channel.send("mmm script failed, aborting server start.")
    #    logger.error("Aborting server start due to mmm failure")
    #    return

    try:
        server_process = await asyncio.create_subprocess_exec(
            java_path,
            *server_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=server_dir
        )
        if server_process.returncode is not None:
            server_running = False
            server_process = None
            await discord_channel.send("Server failed to start (process died).")
            logger.error("Server process died immediately")
            return
        
        server_running = True
        last_player_activity = time.time()
        save_state()
        await discord_channel.send(f"Minecraft server started (instance: {instance_name})!")
        logger.info(f"Server started (instance: {instance_name})")

        asyncio.create_task(read_stream(server_process.stdout, lambda line: handle_server_output(line, discord_channel)))
        asyncio.create_task(read_stream(server_process.stderr, lambda line: handle_server_output(line, discord_channel)))
        asyncio.create_task(check_idle_shutdown(discord_channel))

        await server_process.wait()
        server_running = False
        clear_state()
        await discord_channel.send("Minecraft server stopped.")
        logger.info("Server stopped")

    except Exception as e:
        server_running = False
        server_process = None
        await discord_channel.send(f"Failed to start server: {str(e)}")
        logger.error(f"Failed to start server: {e}")

# TODO: Fix Logic
async def stop_server(discord_channel):
    """Stop the Minecraft server gracefully."""
    global server_process, server_running, current_instance
    if not server_running or server_process is None:
        await discord_channel.send("Server is not running!")
        return

    try:
        await inputToMinecraftConsole("stop", discord_channel)
        await discord_channel.send("Sent stop command to server...")
        logger.info("Sent stop command")
        try:
            return_code = await asyncio.wait_for(server_process.wait(), timeout=30)
            if return_code == 0:
                await discord_channel.send("Server stopped gracefully (exit code 0).")
                logger.info("Server stopped gracefully (exit code 0)")
            else:
                await discord_channel.send(f"Server stopped with error (exit code {return_code}).")
                logger.warning(f"Server stopped with error (exit code {return_code})")
        except asyncio.TimeoutError:
            server_process.terminate()
            try:
                await asyncio.wait_for(server_process.wait(), timeout=5)
                await discord_channel.send("Server terminated after timeout.")
                logger.warning("Server terminated after timeout")
            except asyncio.TimeoutError:
                server_process.kill()
                await discord_channel.send("Server forcefully killed.")
                logger.warning("Server forcefully killed")
    except Exception as e:
        await discord_channel.send(f"Error stopping server: {str(e)}")
        logger.error(f"Error stopping server: {e}")
    finally:
        server_running = False
        server_process = None
        current_instance = None
        clear_state()

# ------------------------------------------------------------------------------
# state helpers
# ------------------------------------------------------------------------------
def save_state():
    """Save bot state to state.json."""
    state = {
        "server_running": server_running,
        "current_instance": current_instance,
        "active_players": list(active_players),
        "last_player_activity": last_player_activity,
        "timestamp": getCurrentUTCTime()
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        logger.debug(f"Saved state to {STATE_FILE}")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

def load_state():
    """Load state.json, return None if missing."""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        return None
    except Exception as e:
        logger.error(f"Failed to load state: {e}")
        return None

def clear_state():
    """Clear state.json on graceful shutdown."""
    try:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            logger.info(f"Cleared state file {STATE_FILE}")
    except Exception as e:
        logger.error(f"Failed to clear state: {e}")

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
    global server_running
    global server_process
    global active_players
    global last_player_activity
    global current_instance
    
    
    # try to grab admin data
    admin_account = await(bot.fetch_user(DEFAULT_ADMIN_ID))
    admin_accountID = admin_account.id
    admin_name = admin_account.global_name
    admin_displayName = admin_account.display_name
    
    # try to access channel
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if (channel is None):
        channel = await bot.fetch_channel(DISCORD_CHANNEL_ID)
    
    if not channel:
        logger.error(f"Cannot access Discord channel {DISCORD_CHANNEL_ID}")
        sys.exit(1)
        
    # init and hook database
    try:
        initDB("mysql", DB_CONFIG)
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
            
    # check for clean shutdown
    state = load_state()
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
        server_running = False
        server_process = None
        active_players = set()
        last_player_activity = None
        current_instance = None
        clear_state()
        await channel.send("Detected crash (server was running). Cleaned up state.") # type: ignore
    else:
        logger.info("No crash detected, starting fresh")
        await channel.send("God has decided to let me live another day, and I'm about to make it everyone's problem.") # type: ignore
        
# TODO: Fix Logic
@bot.command()
@cooldown(1, 10, BucketType.user)
async def startserver(ctx, instance_name="[none given]"):
    """Start the server with specified instance."""
    if not hasPermissionDiscord(str(ctx.author.id), "bot:command:startserver"):
        await ctx.send("You don't have permission!")
        return
    if instance_name not in INSTANCES:
        await ctx.send(f"Unknown instance: {instance_name}. Available: {', '.join(INSTANCES.keys())}")
        return
    await start_server(ctx.channel, instance_name)

# TODO: Fix Logic
@bot.command()
@cooldown(1, 10, BucketType.user)
async def stopserver(ctx):
    """Stop the server."""
    if hasPermission(ctx.author.id, "bot.cmd.stopserver"):
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
    global DISCORD_TOKEN
    
    # Run the bot
    bot.run(DISCORD_TOKEN)
