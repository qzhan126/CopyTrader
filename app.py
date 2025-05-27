import logging
import os
import threading # For manual fetch
from flask import Flask, request, jsonify
from mongoengine import connect as me_connect # Renamed to avoid conflict if 'connect' is used elsewhere
from mongoengine.errors import MongoEngineException

# Project-specific imports
from config import Config
from utils.logger import setup_logging
from models.trade import Trade # Assuming models.trade contains the Trade model definition
from services.scheduler_service import start_scheduler, job as scheduled_job # Import job for manual trigger
# Note: fetch_trade_history and process_and_store_trades are used by scheduled_job, so not directly needed here.

# --- Initial Setup ---
setup_logging() # Configure logging as the very first step
app = Flask(__name__)
# If you had Flask-specific configurations in Config (e.g., SECRET_KEY), you could use:
# app.config.from_object(Config)
logger = logging.getLogger(__name__) # Get a logger for this module

# --- MongoDB Connection ---
try:
    logger.info(f"Attempting to connect to MongoDB host: {Config.MONGODB_SETTINGS_HOST}")
    if not Config.MONGODB_SETTINGS_HOST:
        logger.critical("MongoDB host not configured (MONGODB_SETTINGS_HOST is empty). Cannot connect.")
        # Optionally raise an error or exit if DB is essential for startup
    else:
        me_connect(host=Config.MONGODB_SETTINGS_HOST)
        logger.info("Successfully connected to MongoDB.")
except MongoEngineException as e:
    logger.critical(f"Failed to connect to MongoDB during initial setup: {e}", exc_info=True)
    # The application will continue to run, but database operations will fail.
except Exception as e: # Catch any other unexpected error during connection
    logger.critical(f"An unexpected error occurred during MongoDB connection: {e}", exc_info=True)


# --- API Endpoints ---
@app.route('/api/trades', methods=['GET'])
def get_trades():
    logger.info(f"GET /api/trades - Request Args: {request.args}")
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('pageSize', 100)) # Default to 100 as per common practice
        portfolio_id_filter = request.args.get('portfolioId')
        symbol_filter = request.args.get('symbol')

        # Validate page and page_size
        if page < 1: page = 1
        if page_size < 1: page_size = 1
        if page_size > 500: # Max page size limit
            logger.warning(f"Requested pageSize {page_size} exceeds max limit of 500. Clamping to 500.")
            page_size = 500 

        query_filters = {}
        if portfolio_id_filter:
            query_filters['portfolioId'] = portfolio_id_filter
        if symbol_filter:
            # Assuming symbols are stored in uppercase in the DB for consistent filtering
            query_filters['symbol'] = symbol_filter.upper() 
            # For case-insensitive, one might use: query_filters['symbol__iexact'] = symbol_filter

        # Build the query using filters
        trades_query = Trade.objects(**query_filters)
        
        # Get total records matching the query
        total_records = trades_query.count()
        
        # Apply ordering, skip, and limit for pagination
        # Assumes Trade model has 'ordering = ["-time"]' in meta, or explicitly set here:
        trades_page_qs = trades_query.order_by('-time').skip((page - 1) * page_size).limit(page_size)
        
        trades_list = []
        for trade in trades_page_qs:
            trade_dict = trade.to_mongo().to_dict() # Convert MongoEngine doc to dict
            
            # Ensure datetime objects are converted to ISO strings for JSON serialization
            for field_name in ['time', 'createdAt', 'updatedAt']:
                if field_name in trade_dict and hasattr(trade_dict[field_name], 'isoformat'):
                    trade_dict[field_name] = trade_dict[field_name].isoformat()
            
            # Convert ObjectId (_id) to string
            if '_id' in trade_dict:
                trade_dict['_id'] = str(trade_dict['_id'])
            
            trades_list.append(trade_dict)

        total_pages = (total_records + page_size - 1) // page_size if total_records > 0 else 0
        # Ensure total_pages is at least 1 if there are records but fewer than page_size
        if total_pages == 0 and total_records > 0:
            total_pages = 1
        
        logger.debug(f"Returning {len(trades_list)} trades for page {page} of {total_pages} (Total records: {total_records})")
        return jsonify({
            "data": trades_list,
            "page": page,
            "pageSize": page_size,
            "totalRecords": total_records,
            "totalPages": total_pages
        }), 200

    except ValueError as e: # Handles errors from int(request.args.get(...))
        logger.warning(f"Invalid query parameters for /api/trades: {e}", exc_info=True)
        return jsonify({"error": "Invalid query parameter format. 'page' and 'pageSize' must be integers."}), 400
    except MongoEngineException as e:
        logger.error(f"Database error occurred while fetching trades: {e}", exc_info=True)
        return jsonify({"error": "A database error occurred."}), 500
    except Exception as e: # Catch-all for any other unexpected errors
        logger.error(f"An unexpected error occurred in /api/trades: {e}", exc_info=True)
        return jsonify({"error": "An unexpected server error occurred."}), 500

@app.route('/api/fetch', methods=['POST'])
def manual_fetch_trades_endpoint(): # Renamed to avoid conflict with any variable named 'manual_fetch_trades'
    logger.info("POST /api/fetch - Manual data fetch trigger received.")
    
    if not Config.BNS_UUID or not Config.PORTFOLIO_IDS:
        logger.warning("Manual fetch cannot proceed: BNS_UUID or PORTFOLIO_IDS not configured in environment.")
        return jsonify({"message": "Server configuration incomplete: BNS_UUID or PORTFOLIO_IDS missing."}), 400 # Use 400 for client-actionable config error

    # The 'scheduled_job' function (aliased from scheduler_service.job) already contains
    # the logic to iterate through all portfolio_ids and process them.
    logger.info("Initiating manual data fetch job in a background thread.")
    manual_fetch_thread = threading.Thread(target=scheduled_job, name="ManualFetchAllPortfoliosJob")
    manual_fetch_thread.daemon = True # Allows the main application to exit even if this thread is running
    manual_fetch_thread.start()
    
    return jsonify({"message": "Manual data fetch for all configured portfolios has been initiated."}), 202


# --- Start Scheduler ---
# This part of the code runs when the module is first loaded.
# If using a WSGI server like Gunicorn with multiple workers, each worker might execute this.
# The start_scheduler() function itself should be idempotent (safe to call multiple times)
# by using its internal _scheduler_initialized flag.
logger.info("Attempting to initialize and start the background scheduler...")
start_scheduler()


# --- Main Block for Development Server (Flask's built-in server) ---
if __name__ == '__main__':
    # This block is executed when the script is run directly (e.g., `python app.py`)
    # It's primarily for development. For production, a WSGI server like Gunicorn is used.
    
    # Determine port: Use FLASK_RUN_PORT from env if set, else Config.PORT, else default to 5000
    flask_port_str = os.getenv('FLASK_RUN_PORT', str(Config.PORT) if Config.PORT else "5000")
    try:
        flask_port = int(flask_port_str)
    except ValueError:
        logger.warning(f"Invalid FLASK_RUN_PORT '{flask_port_str}', defaulting to 5000.")
        flask_port = 5000

    # Determine debug mode: Use FLASK_DEBUG from env. Default to False if not set or invalid.
    flask_debug_str = os.getenv('FLASK_DEBUG', 'False').lower()
    flask_debug = flask_debug_str == 'true'

    logger.info(f"Starting Flask development server on host 0.0.0.0, port {flask_port}, debug mode: {flask_debug}")
    
    # use_reloader=True is default if debug=True. Set explicitly if needed.
    # The reloader can sometimes cause issues with schedulers or background threads starting twice.
    # The internal flag in start_scheduler() is designed to prevent multiple actual job scheduling.
    app.run(host='0.0.0.0', port=flask_port, debug=flask_debug, use_reloader=flask_debug) # Match reloader to debug state
```
