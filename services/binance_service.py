import requests
import logging
import time # Potentially for rate limiting

BINANCE_API_URL = "https://www.binance.com/bapi/futures/v1/friendly/future/copy-trade/lead-portfolio/trade-history"
DEFAULT_PAGE_SIZE = 100

def fetch_trade_history(portfolio_id: str, bns_uuid: str, page_size: int = DEFAULT_PAGE_SIZE) -> list | None:
    logger = logging.getLogger(__name__)
    all_trades = []
    page_no = 1
    
    # Log partial bns_uuid for privacy/security
    bns_uuid_display = bns_uuid[:10] + "..." if bns_uuid and len(bns_uuid) > 10 else "INVALID_BNS_UUID"
    logger.info(f"Starting to fetch trade history for portfolioId: {portfolio_id} with bns_uuid: {bns_uuid_display}")

    while True:
        payload = {
            "portfolioId": portfolio_id,
            "pageNo": page_no,
            "pageSize": page_size
        }
        headers = {
            "bns-uuid": bns_uuid,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            logger.debug(f"Fetching page {page_no} for portfolioId {portfolio_id} with payload: {payload}")
            response = requests.post(BINANCE_API_URL, headers=headers, json=payload, timeout=10) # 10 seconds timeout

            # Check for HTTP errors first (4xx or 5xx)
            if response.status_code != 200:
                logger.error(f"HTTP error {response.status_code} while fetching trades for portfolioId {portfolio_id} (page {page_no}): {response.text}")
                return None # Indicate failure

            data = response.json()

            if data.get("code") != "000000":
                logger.error(f"Binance API error for portfolioId {portfolio_id}: Code {data.get('code')}, Message: {data.get('message')}")
                return None # Indicate failure due to API error code

            current_page_trades = data.get("data", {}).get("list", [])
            if not current_page_trades:
                logger.info(f"No more trades found for portfolioId {portfolio_id} on page {page_no}. This might be the end of data or an empty page.")
                break # No more data on this page, assume end of records for this portfolio

            all_trades.extend(current_page_trades)
            total_records_api = data.get("data", {}).get("total", 0)
            
            logger.debug(f"Fetched {len(current_page_trades)} trades on page {page_no} for portfolioId {portfolio_id}. Total fetched so far: {len(all_trades)} out of {total_records_api} (API reported).")

            # Check if all records have been fetched
            if len(all_trades) >= total_records_api or len(current_page_trades) < page_size:
                logger.info(f"Completed fetching all trades for portfolioId {portfolio_id}. Total fetched: {len(all_trades)} (API reported {total_records_api}).")
                break 
            
            page_no += 1
            # time.sleep(0.5) # Optional: brief pause to be polite to the API; uncomment if rate limiting is an issue

        except requests.exceptions.Timeout:
            logger.error(f"Timeout occurred while fetching trades for portfolioId {portfolio_id} (page {page_no}).")
            return None # Indicate failure
        except requests.exceptions.RequestException as e: # Catches other requests-related errors (network, etc.)
            logger.error(f"RequestException fetching trades for portfolioId {portfolio_id} (page {page_no}): {e}")
            return None # Indicate failure
        except Exception as e: # Catch any other unexpected error during processing (e.g., JSON parsing if not valid JSON)
            logger.error(f"An unexpected error occurred during trade fetching for portfolioId {portfolio_id} (page {page_no}): {e}", exc_info=True)
            return None


    logger.info(f"Successfully fetched a total of {len(all_trades)} trades for portfolio ID {portfolio_id}.")
    return all_trades

# Example usage (optional, for testing by worker, ensure .env is set up)
# if __name__ == '__main__':
#     # This requires a valid BNS_UUID and PORTFOLIO_ID in .env or passed directly
#     # Ensure utils.logger and config are available.
#     from dotenv import load_dotenv
#     import os
#     # Assuming this script is in services/ and utils/ is a sibling directory
#     import sys
#     sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#     from utils.logger import setup_logging # Import your setup_logging function
    
#     load_dotenv() # Load .env file from project root

#     # Setup logging for the test
#     setup_logging(logging.DEBUG) 
#     test_logger = logging.getLogger(__name__) # Get logger for this module

#     BNS_UUID_TEST = os.getenv("BNS_UUID")
#     PORTFOLIO_IDS_STR = os.getenv("PORTFOLIO_IDS")
    
#     if not BNS_UUID_TEST:
#         test_logger.error("BNS_UUID not found in environment variables.")
#     if not PORTFOLIO_IDS_STR:
#         test_logger.error("PORTFOLIO_IDS not found in environment variables.")

#     if BNS_UUID_TEST and PORTFOLIO_IDS_STR:
#         PORTFOLIO_ID_TEST = PORTFOLIO_IDS_STR.split(',')[0].strip() # Get the first portfolio ID
#         if PORTFOLIO_ID_TEST:
#             test_logger.info(f"Attempting to fetch trades for PORTFOLIO_ID: {PORTFOLIO_ID_TEST} with BNS_UUID starting with: {BNS_UUID_TEST[:10]}")
#             trades_result = fetch_trade_history(PORTFOLIO_ID_TEST, BNS_UUID_TEST, page_size=10) # Small page size for testing
#             if trades_result is not None:
#                 test_logger.info(f"Fetched {len(trades_result)} trades successfully.")
#                 # You can uncomment the following to print some trade details:
#                 # for i, trade in enumerate(trades_result[:3]): # Print first 3 trades
#                 #     test_logger.info(f"Trade {i+1}: {trade.get('symbol')}, Qty: {trade.get('qty')}, Price: {trade.get('price')}, Time: {trade.get('time')}")
#             else:
#                 test_logger.error(f"Failed to fetch trades for {PORTFOLIO_ID_TEST}.")
#         else:
#             test_logger.error("No portfolio ID found after splitting PORTFOLIO_IDS.")
#     else:
#         test_logger.warning("BNS_UUID or PORTFOLIO_IDS not configured in .env for testing.")
