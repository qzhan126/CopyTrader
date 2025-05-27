import os
import logging
import logging.handlers # For TimedRotatingFileHandler
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# --- Binance Configuration ---
BNS_UUID = os.getenv("BNS_UUID")
_portfolio_ids_str = os.getenv("PORTFOLIO_IDS", "")
PORTFOLIO_IDS = [pid.strip() for pid in _portfolio_ids_str.split(',') if pid.strip()]

# --- MongoDB Configuration ---
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "binance_copy_trades_python")
TRADE_COLLECTION_NAME = os.getenv("TRADE_COLLECTION_NAME", "trades")

# --- Job Configuration ---
FETCH_INTERVAL_MINUTES = int(os.getenv("FETCH_INTERVAL_MINUTES", "5"))
FETCH_WINDOW_MINUTES = int(os.getenv("FETCH_WINDOW_MINUTES", "10"))
INITIAL_JOB_DELAY_SECONDS = int(os.getenv("INITIAL_JOB_DELAY_SECONDS", "10"))

# --- Logging Configuration ---
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE_APP = os.getenv("LOG_FILE_APP", "logs/app.log")
LOG_FILE_ERROR = os.getenv("LOG_FILE_ERROR", "logs/error.log")

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
EFFECTIVE_LOG_LEVEL = LOG_LEVEL_MAP.get(LOG_LEVEL_STR, logging.INFO)

def setup_logging():
    # Ensure log directory exists
    # os.makedirs is not strictly needed here if the directory 'logs' is guaranteed to exist.
    # However, it's good practice if the log file paths were more dynamic.
    # For this project, 'logs/' is created at setup.
    log_app_dir = os.path.dirname(LOG_FILE_APP)
    if log_app_dir and not os.path.exists(log_app_dir):
        os.makedirs(log_app_dir, exist_ok=True)
    
    log_error_dir = os.path.dirname(LOG_FILE_ERROR)
    if log_error_dir and not os.path.exists(log_error_dir):
        os.makedirs(log_error_dir, exist_ok=True)

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(EFFECTIVE_LOG_LEVEL)
    
    # Clear any existing handlers to prevent duplicate logs if this function is called multiple times
    # (though it should only be called once when config.py is imported)
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s')

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    # console_handler.setLevel(EFFECTIVE_LOG_LEVEL) # Not strictly needed if root logger level is set and this handler doesn't override
    logger.addHandler(console_handler)

    # Application File Handler (Timed Rotating)
    app_file_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_FILE_APP, when="midnight", interval=1, backupCount=7, encoding='utf-8'
    )
    app_file_handler.setFormatter(formatter)
    logger.addHandler(app_file_handler)

    # Error File Handler
    error_file_handler = logging.FileHandler(LOG_FILE_ERROR, encoding='utf-8')
    error_file_handler.setFormatter(formatter)
    error_file_handler.setLevel(logging.ERROR) # Only logs ERROR and CRITICAL
    logger.addHandler(error_file_handler)

    # Mute other loggers if too verbose
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("schedule").setLevel(logging.WARNING)
    # Pymongo can be very verbose at DEBUG level with connection pool messages
    logging.getLogger("pymongo.serverSelection").setLevel(logging.INFO)
    logging.getLogger("pymongo.connection").setLevel(logging.INFO)
    logging.getLogger("pymongo.pool").setLevel(logging.INFO)


    logging.info("Logging setup complete. Application starting...")
    logging.debug(f"BNS_UUID set: {'Yes' if BNS_UUID else 'No'}") # Avoid logging full UUID
    logging.debug(f"PORTFOLIO_IDS: {PORTFOLIO_IDS}")
    # Avoid logging credentials if they are part of MONGODB_URI
    mongodb_uri_display = MONGODB_URI
    if '@' in mongodb_uri_display:
        parts = mongodb_uri_display.split('@')
        if len(parts) > 1: # Ensure there's something after @
            mongodb_uri_display = f"mongodb://<credentials_hidden>@{parts[-1]}"
    logging.debug(f"MONGODB_URI: {mongodb_uri_display}")
    logging.debug(f"DB_NAME: {DB_NAME}")
    logging.debug(f"TRADE_COLLECTION_NAME: {TRADE_COLLECTION_NAME}")
    logging.debug(f"FETCH_INTERVAL_MINUTES: {FETCH_INTERVAL_MINUTES}")
    logging.debug(f"FETCH_WINDOW_MINUTES: {FETCH_WINDOW_MINUTES}")
    logging.debug(f"INITIAL_JOB_DELAY_SECONDS: {INITIAL_JOB_DELAY_SECONDS}")
    logging.debug(f"EFFECTIVE_LOG_LEVEL: {logging.getLevelName(EFFECTIVE_LOG_LEVEL)}")


# Call setup_logging() when this module is imported to configure logging application-wide
setup_logging()

# Example of how to use the logger in other modules (for documentation purposes):
# import logging
# logger = logging.getLogger(__name__) # Get a logger specific to the module
# logger.info("This is a test message from another module.")
