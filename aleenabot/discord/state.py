import json
import logging
import sys
import time
import yaml

from .helpers import BotLogger
from .helpers import getCurrentUTCTime

from typing import cast
from pathlib import Path


class State():
    def __init__(self):
        # gonna do some dumb stuff here to make the type checker happy
        self.db_config = {}
        self.discord_token = cast(str, None)
        self.discord_channel_id = cast(int, None)
        self.default_admin_id = cast(int, None)
        self.idle_timeout = cast(int, None)
        self.instances = {}
        self.items_per_page = cast(int, None)
        self.state_file_path = Path(__file__).parent / ".." / "bot_state.json"
        self.scheduled_messages = []
        self.config = {}
        
        self.server_process = None
        self.server_running = False
        self.active_players = set()
        self.last_player_activity = None
        self.current_instance = None
    
        BotLogger()
        self.logger = logging.getLogger(__name__)
        
        self.logger.debug("Initialized instance")
    
    def loadFromConfig(self, path:Path) -> None:
        """loads in config from a yaml file

        Args:
            path (Path): _path to a yaml file to try loading for config_
        """
        
        self.logger.debug(f"Attempting to set values from {path}" )
        
        # load
        try:
            with open(path, "r") as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"failed to load configuration: {e}")
            sys.exit(1)
            
        # set config
        self.discord_token = self.config["discord_token"]
        self.discord_channel_id = self.config["discord_channel_id"]
        self.default_admin_id = self.config["default_admin_id"]
        self.idle_timeout = self.config.get("idle_timeout", 300)
        self.db_config = self.config["database"]
        self.instances = self.config["instances"]
        self.items_per_page = self.config.get("items_per_page", 5)
        self.scheduled_messages = self.config.get("scheduled_messages", [])
    
    async def handle_action(self):
        """Fires when a player does something, no matter what, on the server, that
        active interaction."""
        self.last_player_activity = time.time()
        self.save()
        
    async def activate_player(self, player):
        self.active_players.add(player)
        await self.handle_action()
        
    async def deactivate_player(self, player):
        self.active_players.discard(player)
        self.save()
        
    def save(self):
        """Save bot state to state.json."""
        state = {
            "server_running": self.server_running,
            "current_instance": self.current_instance,
            "active_players": list(self.active_players),
            "last_player_activity": self.last_player_activity,
            "timestamp": getCurrentUTCTime()
        }
        try:
            with open(self.state_file_path, "w") as f:
                json.dump(state, f, indent=2)
                self.logger.debug(f"Saved state to {self.state_file_path}")
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
            

    def load(self):
        """Load state.json, return None if missing."""
        try:
            if self.state_file_path.exists():
                with open(self.state_file_path, "r") as f:
                    return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"Failed to load state: {e}")
            return None

    def clear(self):
        """Clear state.json on graceful shutdown."""
        try:
            if self.state_file_path.exists():
                self.state_file_path.unlink()
                self.logger.info(f"Cleared state file {self.state_file_path}")
        except Exception as e:
            self.logger.error(f"Failed to clear state: {e}")