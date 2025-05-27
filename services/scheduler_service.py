import schedule
import time
import threading
import logging
import sys
import os

# Robust import handling for Config and services
# This allows the script to be run directly for testing,
# and also for app.py to import it.
try:
    from config import Config
    from services.binance_service import fetch_trade_history
    from services.trade_service import process_and_store_trades
except ImportError:
    # Adjust sys.path if running standalone for testing.
    # This assumes services/scheduler_service.py is one level down from project root.
    # (e.g., project_root/services/scheduler_service.py)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_dir)
    if project_root_dir not in sys.path:
        sys.path.insert(0, project_root_dir)
    from config import Config
    from services.binance_service import fetch_trade_history
    from services.trade_service import process_and_store_trades


logger = logging.getLogger(__name__)

def job():
    logger.info("Scheduled job: Fetching and processing trades - STARTING.")
    
    bns_uuid = Config.BNS_UUID
    portfolio_ids = Config.PORTFOLIO_IDS

    if not bns_uuid:
        logger.error("BNS_UUID not configured in .env. Scheduled job cannot proceed.")
        return

    if not portfolio_ids:
        logger.warning("No PORTFOLIO_IDS configured in .env. Nothing to process in scheduled job.")
        return

    logger.info(f"Processing for Portfolio IDs: {', '.join(portfolio_ids)}")

    for portfolio_id in portfolio_ids:
        logger.info(f"Scheduler processing portfolio_id: {portfolio_id}")
        try:
            raw_trades = fetch_trade_history(portfolio_id, bns_uuid)

            if raw_trades is None: 
                logger.warning(f"Failed to fetch trades for portfolio_id: {portfolio_id}. Skipping for this cycle.")
                continue 
            
            if not raw_trades: 
                logger.info(f"No raw trades fetched from API for portfolio_id: {portfolio_id}. Nothing to process.")
                continue

            logger.info(f"Fetched {len(raw_trades)} raw trade(s) for {portfolio_id}. Proceeding to process and store.")
            newly_stored_trades = process_and_store_trades(portfolio_id, raw_trades)
            
            if newly_stored_trades:
                logger.info(f"Successfully stored {len(newly_stored_trades)} new trade(s) for portfolio_id: {portfolio_id}.")
            else:
                logger.info(f"No new trades were ultimately stored for portfolio_id: {portfolio_id} after processing.")
        except Exception as e:
            logger.error(f"An unexpected error occurred in job() while processing portfolio_id {portfolio_id}: {e}", exc_info=True)
    logger.info("Scheduled job: Fetching and processing trades - COMPLETED.")

_cease_continuous_run = threading.Event()
_scheduler_thread = None
_scheduler_initialized = False

def _run_continuously_loop(interval_seconds=1):
    # Docstring for this internal helper function.
    # This loop is responsible for checking schedule.run_pending().
    logger.info(f"Scheduler loop thread ({threading.current_thread().name}) started, checking for jobs every {interval_seconds}s.")
    while not _cease_continuous_run.is_set():
        schedule.run_pending()
        time.sleep(interval_seconds)
    logger.info(f"Scheduler loop thread ({threading.current_thread().name}) terminated.")

def start_scheduler():
    global _scheduler_initialized, _scheduler_thread, _cease_continuous_run

    if _scheduler_initialized:
        logger.warning("Scheduler already initialized and running.")
        return

    logger.info("Initializing scheduler...")
    _cease_continuous_run.clear() 

    logger.info("Scheduling initial data fetch (will run in a background thread).")
    initial_job_thread = threading.Thread(target=job, name="InitialTradeFetchJob")
    initial_job_thread.daemon = True 
    initial_job_thread.start()

    schedule.every(5).minutes.do(job) 
    logger.info(f"Job scheduled to run every 5 minutes. Next run details: {schedule.next_run()}")

    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        _scheduler_thread = threading.Thread(target=_run_continuously_loop, args=(1,), name="SchedulerRunLoop")
        _scheduler_thread.daemon = True 
        _scheduler_thread.start()
        _scheduler_initialized = True
        logger.info("Scheduler started, and background thread for continuous execution is running.")
    else:
        logger.info("Scheduler continuous run thread already active.")

def stop_scheduler(): 
    global _scheduler_initialized, _scheduler_thread
    if not _scheduler_initialized:
        logger.info("Scheduler not running.")
        return
    
    logger.info("Attempting to stop scheduler...")
    _cease_continuous_run.set()
    schedule.clear() 

    if _scheduler_thread and _scheduler_thread.is_alive():
        logger.info("Waiting for scheduler loop thread to finish...")
        _scheduler_thread.join(timeout=5) 
        if _scheduler_thread.is_alive():
            logger.warning("Scheduler loop thread did not terminate gracefully.")
    
    _scheduler_initialized = False
    _scheduler_thread = None 
    logger.info("Scheduler stopped and jobs cleared.")

# Example usage for testing (if __name__ == '__main__')
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s')
    
    # This is to make sure that the config and services can be imported correctly
    # when running this script directly from the services directory.
    # Ensure .env is loaded from project root if it exists.
    try:
        from dotenv import load_dotenv
        current_dir_for_main = os.path.dirname(os.path.abspath(__file__))
        project_root_for_main = os.path.dirname(current_dir_for_main)
        dotenv_path_for_main = os.path.join(project_root_for_main, '.env')
        if os.path.exists(dotenv_path_for_main):
            load_dotenv(dotenv_path=dotenv_path_for_main)
            logger.info(f".env loaded from {dotenv_path_for_main}")
        else:
            logger.warning(f".env file not found at {dotenv_path_for_main}. Some configs might be missing.")
    except ImportError:
        logger.warning("python-dotenv not found, .env file will not be loaded automatically in this test.")

    logger.info("Starting scheduler test from __main__...")
    start_scheduler()
   
    logger.info(f"Configured Portfolio IDs: {Config.PORTFOLIO_IDS if hasattr(Config, 'PORTFOLIO_IDS') else 'Not available'}")
    logger.info(f"Configured BNS_UUID: {'Set' if hasattr(Config, 'BNS_UUID') and Config.BNS_UUID else 'Not set'}")

    try:
        while True:
            time.sleep(60) 
            logger.info(f"Scheduler status: {'Initialized' if _scheduler_initialized else 'Not Initialized'}. Next run: {schedule.next_run(job) if schedule.jobs else 'No jobs scheduled'}")
    except KeyboardInterrupt:
        logger.info("Scheduler test stopped by user (KeyboardInterrupt).")
    finally:
        stop_scheduler()
        logger.info("Scheduler cleanup finished.")
