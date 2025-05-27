import mongoengine as me
import datetime

class Trade(me.Document):
    portfolioId = me.StringField(required=True)
    originalTradeId = me.StringField(required=True) # From API 'id'
    time = me.DateTimeField(required=True)
    symbol = me.StringField(required=True)
    side = me.StringField(required=True)  # "BUY", "SELL"
    price = me.FloatField(required=True)
    fee = me.FloatField(required=True)
    feeAsset = me.StringField(required=True)
    quantity = me.FloatField(required=True) # Amount of base asset (This is `qty` from API)
    quantityAsset = me.StringField(required=True) # Base asset of the symbol
    realizedProfit = me.FloatField(required=True)
    realizedProfitAsset = me.StringField(required=True) # From API 'pnlAsset'
    baseAsset = me.StringField(required=True)
    qty = me.FloatField(required=True) # Original API 'qty', kept for reference
    positionSide = me.StringField(required=True)  # "LONG", "SHORT"
    activeBuy = me.BooleanField() # Optional
    tradeType = me.StringField(required=True) # "开多", "平多", "开空", "平空"

    createdAt = me.DateTimeField(default=datetime.datetime.utcnow)
    updatedAt = me.DateTimeField(default=datetime.datetime.utcnow)

    meta = {
        'indexes': [
            {'fields': ('originalTradeId', 'portfolioId'), 'unique': True},
            '-time', # Index on time, descending for faster latest queries
            'symbol',
            'portfolioId',
        ],
        'ordering': ['-time'] # Default sort order for queries
    }

    def save(self, *args, **kwargs):
        # self.updatedAt is already automatically updated by default=datetime.datetime.utcnow on existing docs
        # if not self.createdAt: # This is handled by default=datetime.datetime.utcnow on creation
        #     self.createdAt = datetime.datetime.utcnow()
        self.updatedAt = datetime.datetime.utcnow() # Explicitly update on every save
        return super(Trade, self).save(*args, **kwargs)

    def __str__(self):
        return f"Trade(ID: {self.originalTradeId}, Portfolio: {self.portfolioId}, Symbol: {self.symbol}, Side: {self.side}, Price: {self.price}, Time: {self.time})"

# Example of how to connect (usually in app.py or a dedicated db setup file, not here)
# if __name__ == '__main__':
#     # This block is for testing purposes only and should not be run in production directly
#     # It requires a running MongoDB instance.
#     print("Attempting to connect to MongoDB for testing Trade model...")
#     try:
#         # Example: connect to a test database
#         me.connect(host="mongodb://localhost:27017/test_trades_db_main", alias="default")
#         print("MongoDB connected for testing.")

#         # Example usage:
#         print("Creating a sample trade...")
#         current_time = datetime.datetime.utcnow()
#         new_trade_data = {
#             "portfolioId": "testPID_unique_001",
#             "originalTradeId": f"origTestID_unique_{current_time.strftime('%Y%m%d%H%M%S%f')}",
#             "time": current_time,
#             "symbol": "BTCUSDT",
#             "side": "BUY",
#             "price": 50000.0,
#             "fee": 1.0,
#             "feeAsset": "USDT",
#             "quantity": 0.001,
#             "quantityAsset": "BTC",
#             "realizedProfit": 0.0,
#             "realizedProfitAsset": "USDT",
#             "baseAsset": "BTC", # Assuming BTC is the base asset for BTCUSDT
#             "qty": 0.001,
#             "positionSide": "LONG",
#             "tradeType": "开多" # "Open Long"
#         }
#         new_trade = Trade(**new_trade_data)
        
#         try:
#             new_trade.save()
#             print(f"Trade saved with ID: {new_trade.id}, originalTradeId: {new_trade.originalTradeId}")

#             # Test unique constraint by trying to save the same trade again
#             # print("Attempting to save the same trade again to test unique constraint...")
#             # duplicate_trade = Trade(**new_trade_data)
#             # duplicate_trade.save() # This should raise NotUniqueError

#         except me.errors.NotUniqueError as e:
#             print(f"Successfully caught NotUniqueError as expected: {e}")
#         except me.errors.ValidationError as e:
#             print(f"ValidationError: {e.to_dict()}")
#         except Exception as e:
#             print(f"An unexpected error occurred during trade save: {e}")

#         # Example of querying
#         # print("Querying for the trade...")
#         # retrieved_trade = Trade.objects(originalTradeId=new_trade_data["originalTradeId"]).first()
#         # if retrieved_trade:
#         #     print(f"Retrieved trade: {retrieved_trade}")
#         # else:
#         #     print("Trade not found by originalTradeId.")

#     except me.errors.MongoEngineConnectionError as e:
#         print(f"Could not connect to MongoDB: {e}")
#     except Exception as e:
#         print(f"An error occurred in the test block: {e}")
#     finally:
#         # Disconnect after tests if a connection was made
#         # me.disconnect(alias="default") # me.disconnect() should also work
#         # print("MongoDB disconnected.")
#         pass
