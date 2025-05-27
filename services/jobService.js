const schedule = require('node-schedule');
require('dotenv').config(); // Ensure env vars are available
const logger = require('../config/logger');
const { fetchAllTrades } = require('./binanceService');
const { processAndSaveTrades } = require('./tradeService');

const PORTFOLIO_IDS_STRING = process.env.PORTFOLIO_IDS;
const FETCH_WINDOW_MINUTES = parseInt(process.env.FETCH_WINDOW_MINUTES, 10) || 10; // Default 10 minutes

async function runJob() {
  logger.info(`[Job] Starting scheduled job run: Fetch Binance Copy Trading History (Window: ${FETCH_WINDOW_MINUTES} mins)`);

  if (!PORTFOLIO_IDS_STRING) {
    logger.error('[Job] PORTFOLIO_IDS environment variable is not set. Job cannot run.');
    return;
  }

  const portfolioIds = PORTFOLIO_IDS_STRING.split(',').map(id => id.trim()).filter(id => id);

  if (portfolioIds.length === 0) {
    logger.warn('[Job] No portfolio IDs configured after parsing. Job will not process any portfolios.');
    return;
  }

  // Define the time window for this job run
  const endTime = Date.now();
  const startTime = endTime - (FETCH_WINDOW_MINUTES * 60 * 1000);

  logger.info(`[Job] Processing for portfolio IDs: ${portfolioIds.join(', ')} for time window: ${new Date(startTime).toISOString()} to ${new Date(endTime).toISOString()}`);

  for (const portfolioId of portfolioIds) {
    logger.info(`[Job] Starting fetch for portfolio: ${portfolioId} for time window ${new Date(startTime).toISOString()} to ${new Date(endTime).toISOString()}`);
    try {
      // Pass startTime and endTime to fetchAllTrades
      const rawTrades = await fetchAllTrades(portfolioId, startTime, endTime);
      
      if (rawTrades && rawTrades.length > 0) {
        logger.info(`[Job] Fetched ${rawTrades.length} raw trades for portfolio: ${portfolioId} from the time window.`);
        const processingStats = await processAndSaveTrades(rawTrades, portfolioId);
        logger.info(`[Job] Processing complete for portfolio: ${portfolioId}. Stats: ${JSON.stringify(processingStats)}`);
      } else {
        logger.info(`[Job] No new trades fetched for portfolio: ${portfolioId} in the time window.`);
      }
    } catch (error) {
      logger.error(`[Job] Error processing portfolio ${portfolioId} for the time window: ${error.message}`, { stack: error.stack, portfolioId, startTime, endTime });
      // Continue to the next portfolioId
    }
  }
  logger.info('[Job] Scheduled job run finished.');
}

function startScheduledJob() {
  const cronSchedule = process.env.JOB_CRON_SCHEDULE || '*/5 * * * *'; // Default every 5 mins
  schedule.scheduleJob(cronSchedule, runJob);
  logger.info(`[Job] Scheduled job to run with cron: ${cronSchedule}. Fetch window: ${FETCH_WINDOW_MINUTES} minutes.`);

  // Initial run shortly after startup
  const initialDelayMs = parseInt(process.env.INITIAL_JOB_DELAY_MS, 10) || 10000; // 10 seconds
  logger.info(`[Job] Scheduling initial job run in ${initialDelayMs / 1000} seconds.`);
  setTimeout(() => {
    logger.info('[Job] Triggering initial job run.');
    runJob().catch(error => { // Catch errors from the initial run as well
      logger.error(`[Job] Error during initial job run: ${error.message}`, { stack: error.stack });
    });
  }, initialDelayMs);
}

module.exports = { startScheduledJob, runJob }; // Export runJob for manual trigger if needed by POST /api/fetch
