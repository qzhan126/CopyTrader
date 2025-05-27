const schedule = require('node-schedule');
require('dotenv').config(); // Ensure env vars are available
const logger = require('../config/logger');
const { fetchAllTrades } = require('./binanceService');
const { processAndSaveTrades } = require('./tradeService'); // Assuming placeholder or actual implementation

const PORTFOLIO_IDS_STRING = process.env.PORTFOLIO_IDS;

async function runJob() {
  logger.info('[Job] Starting scheduled job run: Fetch Binance Copy Trading History');

  if (!PORTFOLIO_IDS_STRING) {
    logger.error('[Job] PORTFOLIO_IDS environment variable is not set. Job cannot run.');
    return;
  }

  const portfolioIds = PORTFOLIO_IDS_STRING.split(',').map(id => id.trim()).filter(id => id);

  if (portfolioIds.length === 0) {
    logger.warn('[Job] No portfolio IDs configured after parsing. Job will not process any portfolios.');
    return;
  }

  logger.info(`[Job] Processing for portfolio IDs: ${portfolioIds.join(', ')}`);

  for (const portfolioId of portfolioIds) {
    logger.info(`[Job] Starting processing for portfolio: ${portfolioId}`);
    try {
      const rawTrades = await fetchAllTrades(portfolioId);
      if (rawTrades && rawTrades.length > 0) {
        logger.info(`[Job] Fetched ${rawTrades.length} raw trades for portfolio: ${portfolioId}`);
        const processingStats = await processAndSaveTrades(rawTrades, portfolioId);
        logger.info(`[Job] Processing complete for portfolio: ${portfolioId}. Stats: ${JSON.stringify(processingStats)}`);
      } else {
        logger.info(`[Job] No new trades fetched for portfolio: ${portfolioId}.`);
      }
    } catch (error) {
      logger.error(`[Job] Error processing portfolio ${portfolioId}: ${error.message}`, { stack: error.stack, portfolioId });
      // Continue to the next portfolioId
    }
  }
  logger.info('[Job] Scheduled job run finished.');
}

function startScheduledJob() {
  const cronSchedule = '*/5 * * * *'; // Every 5 minutes
  schedule.scheduleJob(cronSchedule, runJob);
  logger.info(`[Job] Scheduled job to run every 5 minutes with cron schedule: ${cronSchedule}`);

  // Initial run shortly after startup
  const initialDelayMs = 10 * 1000; // 10 seconds
  logger.info(`[Job] Scheduling initial job run in ${initialDelayMs / 1000} seconds.`);
  setTimeout(() => {
    logger.info('[Job] Triggering initial job run.');
    runJob().catch(error => { // Catch errors from the initial run as well
      logger.error(`[Job] Error during initial job run: ${error.message}`, { stack: error.stack });
    });
  }, initialDelayMs);
}

module.exports = { startScheduledJob, runJob }; // Export runJob for manual trigger if needed by POST /api/fetch
