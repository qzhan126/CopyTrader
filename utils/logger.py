import logging
import logging.handlers
import os

def setup_logging(log_level=logging.INFO):
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(log_level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Combined Log File Handler (Rotating)
    fh_combined_path = os.path.join("logs", "combined.log")
    fh_combined = logging.handlers.RotatingFileHandler(
        fh_combined_path, maxBytes=10*1024*1024, backupCount=5  # 10MB per file, 5 backups
    )
    fh_combined.setLevel(log_level)
    fh_combined.setFormatter(formatter)
    logger.addHandler(fh_combined)

    # Error Log File Handler (Rotating)
    fh_error_path = os.path.join("logs", "error.log")
    fh_error = logging.handlers.RotatingFileHandler(
        fh_error_path, maxBytes=5*1024*1024, backupCount=5  # 5MB per file, 5 backups
    )
    fh_error.setLevel(logging.ERROR) # Log only ERROR and CRITICAL messages to this file
    fh_error.setFormatter(formatter)
    logger.addHandler(fh_error)

# Example usage (optional, for testing)
# if __name__ == '__main__':
#     setup_logging(logging.DEBUG)
#     logging.debug("This is a debug message.")
#     logging.info("This is an info message.")
#     logging.warning("This is a warning message.")
#     logging.error("This is an error message.")
#     logging.critical("This is a critical message.")
#     # To test logger from another module:
#     # test_logger = logging.getLogger(__name__)
#     # test_logger.info("Message from test_logger")
