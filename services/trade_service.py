import logging
import datetime as dt # Alias for datetime module
import json
import os
from models.trade import Trade
from mongoengine.errors import NotUniqueError, MongoEngineException, OperationError

# Helper function for base/quote asset
def get_assets_from_symbol(symbol: str) -> tuple[str, str]:
    known_quote_assets = ["USDT", "BUSD", "USDC", "BTC", "ETH", "BNB"]
    for quote in known_quote_assets:
        if symbol.endswith(quote):
            base = symbol[:-len(quote)]
            return base, base # quantityAsset is the base asset
    # Fallback (very basic)
    if len(symbol) > 3 and symbol[-3:].isalpha() and symbol[-3:].isupper(): # e.g. PEPEUSDT -> PEPE
         return symbol[:-3], symbol[:-3]
    elif len(symbol) > 4 and symbol[-4:].isalpha() and symbol[-4:].isupper(): # e.g. SOMEBTC -> SOME
         return symbol[:-4], symbol[:-4] # For things like SOMEBTC
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not robustly determine base/quote for symbol: {symbol}. Using fallback logic.")
    # Default fallback if no known quote asset is found
    return symbol, symbol # Should ideally not happen with well-formed symbols

def process_and_store_trades(portfolio_id: str, raw_trades: list) -> list[Trade]:
    logger = logging.getLogger(__name__)
    
    if not raw_trades:
        logger.info(f"No raw trades provided for portfolio_id: {portfolio_id}. Nothing to process.")
        return []

    try:
        os.makedirs("data", exist_ok=True)
    except OSError as e:
        logger.error(f"Could not create data directory: {e}")
        # Depending on policy, might want to return or raise here

    # A. Data Transformation & Initial Filtering
    potential_new_trades_transformed: list[Trade] = []
    for raw_trade in raw_trades:
        try:
            base_asset, quantity_asset = get_assets_from_symbol(raw_trade['symbol'])

            trade_type = ""
            side = raw_trade.get('side', '').upper()
            position_side = raw_trade.get('positionSide', '').upper()

            if side == "BUY" and position_side == "LONG":
                trade_type = "开多"  # Open Long
            elif side == "SELL" and position_side == "LONG":
                trade_type = "平多"  # Close Long
            elif side == "SELL" and position_side == "SHORT":
                trade_type = "开空"  # Open Short
            elif side == "BUY" and position_side == "SHORT":
                trade_type = "平空"  # Close Short
            else:
                logger.warning(f"Could not determine tradeType for trade {raw_trade.get('id')} with side {side} and positionSide {position_side}")
                # Decide if this trade should be skipped or handled with a default tradeType
                # continue # Option: skip this trade

            trade_data = {
                "portfolioId": portfolio_id,
                "originalTradeId": str(raw_trade['id']),
                "time": dt.datetime.fromtimestamp(int(raw_trade['time']) / 1000),
                "symbol": raw_trade['symbol'],
                "side": side,
                "price": float(raw_trade['price']),
                "fee": float(raw_trade['fee']),
                "feeAsset": raw_trade['feeAsset'],
                "quantity": float(raw_trade['qty']), # This is amount of base asset
                "quantityAsset": quantity_asset, # Base asset of the symbol
                "realizedProfit": float(raw_trade['pnl']),
                "realizedProfitAsset": raw_trade['pnlAsset'],
                "baseAsset": base_asset,
                "qty": float(raw_trade['qty']), # Store original API 'qty'
                "positionSide": position_side,
                "tradeType": trade_type,
                "activeBuy": raw_trade.get('activeBuy') # Optional, might be None
            }
            potential_new_trades_transformed.append(Trade(**trade_data))
        except KeyError as e:
            logger.error(f"Missing key {e} in raw_trade: {raw_trade}. Skipping this trade.")
            continue
        except ValueError as e:
            logger.error(f"Value error processing raw_trade: {raw_trade} - {e}. Skipping this trade.")
            continue
        except Exception as e:
            logger.error(f"Unexpected error transforming raw_trade {raw_trade.get('id')}: {e}", exc_info=True)
            continue
            
    logger.info(f"Portfolio {portfolio_id}: Transformed {len(potential_new_trades_transformed)} trades from raw input.")
    if not potential_new_trades_transformed:
        return []

    # B. Preliminary De-duplication (Against DB)
    truly_new_trades_after_db_check: list[Trade] = []
    ids_to_check = [t.originalTradeId for t in potential_new_trades_transformed]
    
    try:
        existing_trade_ids = set(Trade.objects(portfolioId=portfolio_id, originalTradeId__in=ids_to_check).scalar('originalTradeId'))
        logger.debug(f"Portfolio {portfolio_id}: Found {len(existing_trade_ids)} existing trades in DB for the current batch.")
    except MongoEngineException as e:
        logger.error(f"Portfolio {portfolio_id}: DB error checking existing trades: {e}. Proceeding without DB check (risk of duplicates).")
        # Fallback: assume all are new, or handle more gracefully (e.g. return, or try later)
        existing_trade_ids = set() # Or, could choose to not proceed: return [] 

    for trade in potential_new_trades_transformed:
        if trade.originalTradeId not in existing_trade_ids:
            truly_new_trades_after_db_check.append(trade)
            
    logger.info(f"Portfolio {portfolio_id}: {len(truly_new_trades_after_db_check)} trades remaining after preliminary DB de-duplication.")
    if not truly_new_trades_after_db_check:
        return []

    # C. 10-Minute Window De-duplication
    truly_new_trades_after_db_check.sort(key=lambda t: t.time) # Sort by time

    grouped_trades = {}
    for trade in truly_new_trades_after_db_check:
        key = (trade.symbol, trade.side, trade.positionSide)
        if key not in grouped_trades:
            grouped_trades[key] = []
        grouped_trades[key].append(trade)

    final_trades_to_save: list[Trade] = []
    for symbol_side_group, trades_in_group in grouped_trades.items():
        if not trades_in_group:
            continue
        
        # Trades are already sorted by time overall, and thus within each group too.
        # No need to sort again unless the grouping somehow disordered them.
        # trades_in_group.sort(key=lambda t: t.time) # Defensive sort
        
        last_kept_trade_time = None
        for trade in trades_in_group:
            if last_kept_trade_time is None or (trade.time - last_kept_trade_time).total_seconds() >= 600:
                final_trades_to_save.append(trade)
                last_kept_trade_time = trade.time
            else:
                logger.debug(f"Portfolio {portfolio_id}: Trade {trade.originalTradeId} ({trade.symbol} {trade.side} at {trade.time}) "
                             f"skipped due to 10-min window with last kept at {last_kept_trade_time}.")

    logger.info(f"Portfolio {portfolio_id}: {len(final_trades_to_save)} trades remaining after 10-minute window de-duplication.")

    if not final_trades_to_save:
        return []

    # D. Data Storage
    # Save to MongoDB
    saved_trades_db_count = 0
    if final_trades_to_save: # Ensure there's something to save
        try:
            # Using bulk insert. MongoEngine's default bulk insert should handle individual errors if any,
            # but NotUniqueError for the whole batch might still occur if not pre-checked.
            # The previous check `originalTradeId__in` helps, but a race condition is theoretically possible.
            # `load_bulk=False` makes MongoEngine create objects for each inserted doc, which might be memory intensive
            # for very large lists, but gives back full objects.
            # If we only care about success/failure, `Trade.insert(final_trades_to_save)` might be slightly more performant.
            # However, the prompt asks to return list[Trade] that were saved.
            # `Trade.objects.insert` returns the saved objects (or their pks).
            
            # Let's insert one by one to handle NotUniqueError more gracefully if it arises at this stage
            # despite previous checks (e.g. due to concurrent processing for same portfolioId)
            successfully_saved_to_db = []
            for trade_to_save in final_trades_to_save:
                try:
                    trade_to_save.save() # This will trigger the custom save method in Trade model for updatedAt
                    successfully_saved_to_db.append(trade_to_save)
                    saved_trades_db_count += 1
                except NotUniqueError:
                    logger.warning(f"Portfolio {portfolio_id}: Trade {trade_to_save.originalTradeId} already exists in DB (NotUniqueError on save). Skipping.")
                except MongoEngineException as e: # Other DB errors during save of a single trade
                    logger.error(f"Portfolio {portfolio_id}: DB error saving trade {trade_to_save.originalTradeId}: {e}. Skipping this trade.")
            
            final_trades_to_save = successfully_saved_to_db # Update to only those successfully saved
            if saved_trades_db_count > 0:
                 logger.info(f"Portfolio {portfolio_id}: Successfully saved {saved_trades_db_count} new trades to MongoDB.")
            else:
                 logger.info(f"Portfolio {portfolio_id}: No new trades were ultimately saved to MongoDB in this batch.")

        except OperationError as e: # For bulk operations if we were using them
            logger.error(f"Portfolio {portfolio_id}: MongoDB bulk insert operation error: {e}")
            # Decide how to handle partial success or what to return
            # For now, if bulk fails, assume nothing was saved from this batch for JSON.
            # Since we switched to one-by-one, this specific catch might be less relevant.
        except MongoEngineException as e:
            logger.error(f"Portfolio {portfolio_id}: A MongoDB error occurred during batch save: {e}")
            # As above, decide on handling.

    if not final_trades_to_save: # If all saves failed or list became empty
        logger.info(f"Portfolio {portfolio_id}: No trades to save to JSON file.")
        return [] # Return empty list as nothing was effectively saved

    # Save to JSON file
    trades_for_json = []
    for trade_obj in final_trades_to_save: # Use the list of successfully saved trades
        trade_dict = trade_obj.to_mongo().to_dict() # Convert MongoEngine doc to dict
        
        # Convert datetime objects to ISO format strings
        if 'time' in trade_dict and isinstance(trade_dict['time'], dt.datetime):
            trade_dict['time'] = trade_dict['time'].isoformat()
        if 'createdAt' in trade_dict and isinstance(trade_dict['createdAt'], dt.datetime):
            trade_dict['createdAt'] = trade_dict['createdAt'].isoformat()
        if 'updatedAt' in trade_dict and isinstance(trade_dict['updatedAt'], dt.datetime):
            trade_dict['updatedAt'] = trade_dict['updatedAt'].isoformat()
        
        # Remove _id or convert to str if needed
        if '_id' in trade_dict:
            trade_dict['_id'] = str(trade_dict['_id']) # Keep it as string
            # trade_dict.pop('_id', None) # Or remove

        trades_for_json.append(trade_dict)

    if trades_for_json:
        try:
            timestamp_str = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join("data", f"trades_{portfolio_id}_{timestamp_str}.json")
            with open(filename, 'w') as f:
                json.dump(trades_for_json, f, indent=4)
            logger.info(f"Portfolio {portfolio_id}: Successfully saved {len(trades_for_json)} trades to JSON file: {filename}")
        except IOError as e:
            logger.error(f"Portfolio {portfolio_id}: Error writing trades to JSON file: {e}")
        except Exception as e:
            logger.error(f"Portfolio {portfolio_id}: Unexpected error during JSON serialization or file writing: {e}", exc_info=True)

    return final_trades_to_save # Return the list of Trade objects that were successfully saved to DB

# Example usage (for testing by worker, ensure .env, config, logger, models are set up)
# if __name__ == '__main__':
#     # This requires a running MongoDB instance and proper setup.
#     # Setup logging
#     import sys
#     sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add project root to path
#     from utils.logger import setup_logging
#     from config import Config
#     import mongoengine as me

#     setup_logging(logging.DEBUG)
#     main_logger = logging.getLogger(__name__)

#     # Connect to MongoDB (use settings from Config)
#     try:
#         if not Config.MONGODB_SETTINGS_HOST:
#             raise ValueError("MONGODB_SETTINGS_HOST not configured.")
#         me.connect(host=Config.MONGODB_SETTINGS_HOST, alias='default')
#         main_logger.info(f"Connected to MongoDB at {Config.MONGODB_SETTINGS_HOST}")
#     except ValueError as e:
#         main_logger.error(f"MongoDB configuration error: {e}")
#         sys.exit(1)
#     except MongoEngineException as e:
#         main_logger.error(f"Could not connect to MongoDB: {e}")
#         sys.exit(1)

#     # Sample raw trade data (replace with actual fetched data for real testing)
#     sample_portfolio_id = Config.PORTFOLIO_IDS[0] if Config.PORTFOLIO_IDS else "test_portfolio_001"
#     current_time_ms = int(dt.datetime.now().timestamp() * 1000)
    
#     # Create a series of raw trades for testing different scenarios
#     raw_trades_data = [
#         # Trade 1: Unique
#         {"id": f"test001_{current_time_ms}", "time": current_time_ms, "symbol": "BTCUSDT", "side": "BUY", "price": "50000", "fee": "1", "feeAsset": "USDT", "qty": "0.001", "pnl": "0", "pnlAsset": "USDT", "positionSide": "LONG", "activeBuy": False},
#         # Trade 2: Same symbol, side, positionSide as Trade 1, but 1 minute later (should be kept if Trade 1 is new)
#         {"id": f"test002_{current_time_ms + 60000}", "time": current_time_ms + 60000, "symbol": "BTCUSDT", "side": "BUY", "price": "50010", "fee": "1", "feeAsset": "USDT", "qty": "0.002", "pnl": "0", "pnlAsset": "USDT", "positionSide": "LONG"},
#         # Trade 3: Same as Trade 2, but 11 minutes after Trade 2 (should be kept)
#         {"id": f"test003_{current_time_ms + 60000 + 11*60000}", "time": current_time_ms + 60000 + 11*60000, "symbol": "BTCUSDT", "side": "BUY", "price": "50020", "fee": "1", "feeAsset": "USDT", "qty": "0.003", "pnl": "0", "pnlAsset": "USDT", "positionSide": "LONG"},
#         # Trade 4: Different symbol
#         {"id": f"test004_{current_time_ms + 120000}", "time": current_time_ms + 120000, "symbol": "ETHUSDT", "side": "SELL", "price": "3000", "fee": "0.5", "feeAsset": "USDT", "qty": "0.01", "pnl": "10", "pnlAsset": "USDT", "positionSide": "SHORT"},
#         # Trade 5: To simulate an already existing trade (assuming test001 gets saved first)
#         # For this to test existing, you'd run once, then uncomment and modify ID slightly for next run if needed
#         # {"id": f"test001_{current_time_ms}", "time": current_time_ms, "symbol": "BTCUSDT", "side": "BUY", "price": "50000", "fee": "1", "feeAsset": "USDT", "qty": "0.001", "pnl": "0", "pnlAsset": "USDT", "positionSide": "LONG"},
#     ]

#     main_logger.info(f"Processing {len(raw_trades_data)} sample trades for portfolio {sample_portfolio_id}...")
#     processed_trades = process_and_store_trades(sample_portfolio_id, raw_trades_data)

#     if processed_trades:
#         main_logger.info(f"Successfully processed and initiated save for {len(processed_trades)} trades:")
#         for trade in processed_trades:
#             main_logger.info(f"  - {trade.originalTradeId}: {trade.symbol} {trade.side} {trade.quantity} @ {trade.price} on {trade.time.isoformat()}")
#     else:
#         main_logger.info("No trades were processed or saved in this run.")

#     # Clean up (optional): Delete created sample trades if you want a clean slate for next test run
#     # if processed_trades:
#     #     ids_to_delete = [t.originalTradeId for t in processed_trades]
#     #     Trade.objects(portfolioId=sample_portfolio_id, originalTradeId__in=ids_to_delete).delete()
#     #     main_logger.info(f"Cleaned up {len(ids_to_delete)} sample trades from DB.")

#     me.disconnect()
#     main_logger.info("Disconnected from MongoDB.")
