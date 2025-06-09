import logging
import logging.handlers

from datetime import datetime
from datetime import timezone
from typing import cast

class BotLogger():
    """A wrapper for the bot's logging facilities. A very kludgy not-singleton"""
    
    inited:bool = False
    logger:logging.Logger = cast(logging.Logger, None)
    unrecognized_logger:logging.Logger = cast(logging.Logger, None)
    
    def __init__(self):
        if (not BotLogger.inited):
            # Set up logging with rotation
            handler = logging.handlers.RotatingFileHandler("aleena.log", maxBytes=10*1024*1024, backupCount=5)
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
            
            logger.info("Initialized logging")
            
            BotLogger.unrecognized_logger = unrecognized_logger
            BotLogger.inited = True
            
        self.unrecognized_logger = BotLogger.unrecognized_logger
        
def getCurrentUTCTime() -> str:
    ret = ""
    
    swp = datetime.now()
    swp = swp.replace(tzinfo=timezone.utc)
    ret = swp.strftime('%Y-%m-%d %H:%M:%S.%f')
    
    return ret