const axios = require('axios');
require('dotenv').config(); // Make sure env vars are loaded
const logger = require('../config/logger');

const BNS_UUID = process.env.BNS_UUID;
const API_ENDPOINT = 'https://www.binance.com/bapi/futures/v1/friendly/future/copy-trade/lead-portfolio/trade-history';

async function fetchTradeHistory(portfolioId, page = 1, pageSize = 100) {
  if (!BNS_UUID) {
    logger.error('BNS_UUID is not configured.');
    throw new Error('BNS_UUID is not configured.');
  }
  logger.info(`Fetching trade history for portfolioId: ${portfolioId}, pageNumber: ${page}, pageSize: ${pageSize}`);
  try {
    const payload = {
      portfolioId: String(portfolioId),
      pageNumber: Number(page), // Changed from page to pageNumber
      pageSize: Number(pageSize),
      tradeType: "ALL"
    };
    // The subtask for time-windowed fetching will add startTime and endTime to this payload.
    // For now, this is the correct structure based on the current subtask.

    const response = await axios.post(API_ENDPOINT, payload,
      { headers: { 'bns-uuid': BNS_UUID, 'Content-Type': 'application/json' } }
    );

    if (response.data && response.data.code === "000000") {
      logger.info(`Successfully fetched ${response.data.data.list.length} trades for portfolioId: ${portfolioId}, pageNumber: ${page}. Total items: ${response.data.data.total}`);
      return response.data.data; // Contains list and total
    } else {
      logger.error(`API error for portfolioId ${portfolioId}, pageNumber: ${page}: ${response.data.message || 'Unknown API error'}`, response.data);
      throw new Error(`Binance API error: ${response.data.message || 'Unknown error'}`);
    }
  } catch (error) {
    logger.error(`Failed to fetch trade history for portfolioId ${portfolioId}, pageNumber: ${page}: ${error.message}`, { stack: error.stack });
    if (error.response) {
      logger.error('Error response data:', error.response.data);
      logger.error('Error response status:', error.response.status);
    }
    throw error; // Re-throw to be handled by the caller
  }
}

async function fetchAllTrades(portfolioId) {
  let allTrades = [];
  let currentPage = 1;
  const pageSize = 100; // Max pageSize by API seems to be 100
  let totalPages = 1; 
  let retries = 0;
  const maxRetries = 3;

  logger.info(`Starting to fetch all trades for portfolioId: ${portfolioId}`);

  do {
    try {
      const data = await fetchTradeHistory(portfolioId, currentPage, pageSize);
      if (data && data.list) {
        allTrades = allTrades.concat(data.list);
        // Ensure total is a number and greater than 0 before calculating totalPages
        const totalTrades = Number(data.total);
        totalPages = totalTrades > 0 ? Math.ceil(totalTrades / pageSize) : 0;

        logger.info(`Fetched page ${currentPage}/${totalPages === 0 && totalTrades === 0 ? 1 : totalPages} for portfolioId ${portfolioId}. Total trades so far: ${allTrades.length}`);
        
        if (totalPages === 0) { // No trades to fetch or already fetched all
            break;
        }
        currentPage++;
        retries = 0; // Reset retries on success
      } else {
        // This case should ideally be caught by error handling in fetchTradeHistory
        logger.warn(`No data received for portfolioId ${portfolioId}, page ${currentPage}, but no explicit error thrown.`);
        // Consider a retry or break strategy here
        break; 
      }
    } catch (error) {
      logger.error(`Error fetching page ${currentPage} for portfolioId ${portfolioId}: ${error.message}. Attempt ${retries + 1}/${maxRetries}`);
      retries++;
      if (retries >= maxRetries) {
        logger.error(`Max retries reached for portfolioId ${portfolioId}, page ${currentPage}. Aborting for this portfolio.`);
        // Decide: throw error to stop all processing, or just return what's been collected.
        // For now, let's throw to indicate a significant issue.
        throw new Error(`Failed to fetch all trades for ${portfolioId} after ${maxRetries} retries on page ${currentPage}.`);
      }
      await new Promise(resolve => setTimeout(resolve, 2000 * retries)); // Wait longer after each retry
      continue; // Retry the current page
    }

    // Delay between successful page fetches
    if (currentPage <= totalPages) {
      await new Promise(resolve => setTimeout(resolve, 1000)); // 1-second delay
    }
  } while (currentPage <= totalPages && totalPages > 0); // Continue if there are more pages to fetch

  logger.info(`Successfully fetched all ${allTrades.length} trades for portfolioId: ${portfolioId} over ${totalPages === 0 && allTrades.length === 0 ? 1 : totalPages} pages.`);
  return allTrades;
}

module.exports = { fetchAllTrades, fetchTradeHistory }; // Export both if fetchTradeHistory might be useful externally or for testing
