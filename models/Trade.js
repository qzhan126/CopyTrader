const mongoose = require('mongoose');

const tradeSchema = new mongoose.Schema({
  portfolioId: { type: String, required: true },
  originalTradeId: { type: String, required: true }, // id from Binance API
  time: { type: Date, required: true },
  symbol: { type: String, required: true },
  side: { type: String, required: true }, // e.g., "BUY", "SELL"
  price: { type: Number, required: true },
  fee: { type: Number, required: true },
  feeAsset: { type: String, required: true },
  quantity: { type: Number, required: true }, // 'qty' from API, renamed for clarity
  quantityAsset: { type: String, required: true },
  realizedProfit: { type: Number, required: true },
  realizedProfitAsset: { type: String, required: true }, // 'pnlAsset' from API
  baseAsset: { type: String, required: true },
  qty: { type: Number, required: true }, // Original 'qty' from API
  positionSide: { type: String, required: true }, // e.g., "LONG", "SHORT"
  activeBuy: { type: Boolean }, // Optional, from API
  tradeType: { type: String, required: true }, // e.g., "开多", "平多", "开空", "平空"
}, { timestamps: true });

// Indexes
// Compound unique index to prevent duplicate entries for the same trade and portfolio
tradeSchema.index({ originalTradeId: 1, portfolioId: 1 }, { unique: true });

// Indexes for query optimization
tradeSchema.index({ time: -1 }); // Sort by time, newest first
tradeSchema.index({ symbol: 1 });
tradeSchema.index({ portfolioId: 1 });
tradeSchema.index({ positionSide: 1 });

const Trade = mongoose.model('Trade', tradeSchema);

module.exports = Trade;
