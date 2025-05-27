const express = require('express');
const router = express.Router();
const Trade = require('../models/Trade');
const { runJob } = require('../services/jobService'); // Assuming runJob is exported for manual trigger
const logger = require('../config/logger');

// GET /api/trades - Fetch trades with filtering and pagination
router.get('/', async (req, res) => {
  try {
    const { portfolioId, symbol, page = 1, pageSize = 100 } = req.query;
    
    let pageNum = parseInt(page, 10);
    let sizeNum = parseInt(pageSize, 10);

    if (isNaN(pageNum) || pageNum < 1) {
      logger.warn(`Invalid page number requested: ${page}. Defaulting to 1.`);
      pageNum = 1; // Default to page 1 if invalid
    }
    // Max page size 200, min 1
    if (isNaN(sizeNum) || sizeNum < 1) {
      logger.warn(`Invalid page size requested: ${pageSize}. Defaulting to 100.`);
      sizeNum = 100; // Default to 100 if invalid (less than 1)
    } else if (sizeNum > 200) {
      logger.warn(`Requested page size ${sizeNum} exceeds max of 200. Capping at 200.`);
      sizeNum = 200; // Cap at 200 if greater than max
    }

    const filterQuery = {};
    if (portfolioId) filterQuery.portfolioId = portfolioId;
    if (symbol) filterQuery.symbol = symbol;

    logger.info(`GET /api/trades request: query=${JSON.stringify(req.query)}, filter=${JSON.stringify(filterQuery)}, page=${pageNum}, pageSize=${sizeNum}`);

    const trades = await Trade.find(filterQuery)
      .sort({ time: -1 }) // Sort by time descending (newest first)
      .skip((pageNum - 1) * sizeNum)
      .limit(sizeNum)
      .lean(); // Use lean for performance

    const totalRecords = await Trade.countDocuments(filterQuery);
    const totalPages = Math.ceil(totalRecords / sizeNum);

    logger.info(`GET /api/trades response: Returning ${trades.length} trades. Total records: ${totalRecords}, Total pages: ${totalPages}`);

    res.json({
      data: trades,
      currentPage: pageNum,
      pageSize: sizeNum,
      totalRecords,
      totalPages,
    });
  } catch (error) {
    logger.error(`Error in GET /api/trades: ${error.message}`, { stack: error.stack, query: req.query });
    res.status(500).json({ message: 'Failed to retrieve trades.', error: error.message });
  }
});

// POST /api/trades/fetch - Manually trigger data fetch
router.post('/fetch', (req, res) => {
  logger.info('POST /api/trades/fetch request received. Triggering manual data fetch job.');
  try {
    // Do not await this, let it run in the background
    runJob().catch(err => {
        // Log errors from the job initiation or unhandled promise rejection from runJob itself
        logger.error(`Error during manually triggered runJob execution: ${err.message}`, { stack: err.stack });
    });
    res.status(202).json({ message: 'Data fetch job initiated. Processing will occur in the background.' });
  } catch (error) {
    // This catch is for immediate errors in trying to call runJob, not for errors within runJob's execution
    logger.error(`Error initiating manual data fetch job: ${error.message}`, { stack: error.stack });
    res.status(500).json({ message: 'Failed to initiate data fetch job.', error: error.message });
  }
});

module.exports = router;
