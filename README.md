# Binance Copy Trading History Monitor

## Description

This application monitors the trade history of specified Binance copy trading portfolios. It fetches trade data from the Binance API, processes it, stores it in a MongoDB database to prevent duplicates, and provides a REST API to query the stored trades. The data fetching can be triggered manually or run as a scheduled job.

## Features

-   **Data Fetching:** Regularly fetches new trade data from Binance's copy trading API.
-   **Deduplication:** Ensures that each trade is stored only once in the database (based on original trade ID and portfolio ID).
-   **MongoDB Storage:** Stores trade data persistently in a MongoDB database.
-   **REST API:** Provides API endpoints to query stored trades with filtering and pagination, and to manually trigger data fetching.
-   **Scheduled Jobs:** Automatically fetches data at regular intervals (e.g., every 5 minutes).
-   **Logging:** Comprehensive logging for application events, errors, and API requests.

## Prerequisites

-   [Node.js](https://nodejs.org/) (v14.x or later recommended)
-   npm (usually comes with Node.js) or yarn
-   [MongoDB](https://www.mongodb.com/try/download/community) (ensure a MongoDB server is running and accessible)

## Setup and Configuration

1.  **Clone the Repository (if applicable) or Download Files:**
    ```bash
    # If it's a git repository:
    # git clone <repository_url>
    # cd <repository_name>
    ```
    If you downloaded the files, ensure they are in a project directory.

2.  **Install Dependencies:**
    Navigate to the project directory in your terminal and run:
    ```bash
    npm install
    ```

3.  **Set Up Environment Variables:**
    Create a `.env` file in the root of your project directory by copying the example file:
    ```bash
    cp .env.example .env
    ```
    Now, edit the `.env` file and provide the necessary values:

    *   `BNS_UUID`: Your Binance session UUID. This is required to authenticate with the Binance API for fetching copy trading data.
        *   **How to obtain `BNS_UUID`**:
            1.  Log in to your Binance account in your web browser.
            2.  Open your browser's developer tools (usually by pressing F12).
            3.  Go to the "Network" tab within the developer tools.
            4.  Navigate to the Copy Trading section on the Binance website.
            5.  Look for requests made to the Binance API as you interact with the page (e.g., requests to endpoints like `/bapi/futures/v1/friendly/future/copy-trade/lead-portfolio/trade-history`).
            6.  Select one of these requests. In the request details, look for the "Request Headers" section. The `bns-uuid` will be listed there. Copy its value.
    *   `MONGODB_URI`: The connection string for your MongoDB database.
        *   Example: `mongodb://localhost:27017/binance_copy_trades`
    *   `PORT`: The port on which the application server will listen.
        *   Default: `3000`
    *   `PORTFOLIO_IDS`: A comma-separated list of Binance copy trading portfolio IDs you want to monitor.
        *   Example: `your_portfolio_id_1,your_portfolio_id_2`

## Running the Application

1.  **Start the Server:**
    Once dependencies are installed and the `.env` file is configured, you can start the application using:
    ```bash
    npm start
    ```
    This command relies on the `start` script defined in `package.json`.

    Alternatively, you can run:
    ```bash
    node app.js
    ```

## API Endpoints

The API is available under the `/api` prefix.

*   **`GET /api/trades`**
    *   Fetches stored trades from the database.
    *   **Query Parameters:**
        *   `page` (optional, default: 1): For pagination.
        *   `pageSize` (optional, default: 100, max: 200): Number of trades per page.
        *   `portfolioId` (optional): Filter trades by a specific portfolio ID.
        *   `symbol` (optional): Filter trades by a specific trading symbol (e.g., `BTCUSDT`).
    *   Returns a JSON object with `data`, `currentPage`, `pageSize`, `totalRecords`, and `totalPages`.

*   **`POST /api/trades/fetch`**
    *   Manually triggers the background job to fetch trade data from the Binance API for all configured portfolio IDs.
    *   Returns a `202 Accepted` status with a message indicating the job has been initiated.

## Project Structure

```
.
├── config/         # Configuration files (database, logger)
├── data/           # (Potentially for future use, e.g., CSV exports - ignored by git)
├── logs/           # Log files (error.log, combined.log - ignored by git)
├── models/         # Mongoose models (e.g., Trade.js)
├── node_modules/   # NPM packages (ignored by git)
├── routes/         # API route definitions (e.g., tradeRoutes.js)
├── services/       # Business logic (Binance API interaction, job scheduling, trade processing)
├── .env            # Environment variables (ignored by git - MUST BE CREATED)
├── .env.example    # Example environment variables
├── .gitignore      # Specifies intentionally untracked files that Git should ignore
├── app.js          # Main application entry point
├── package.json    # Project metadata and dependencies
├── package-lock.json # Records exact versions of dependencies
└── README.md       # This file
```

## Logging

-   Logs are stored in the `logs/` directory:
    -   `error.log`: Contains only error-level logs.
    -   `combined.log`: Contains all logs (info, warn, error).
-   Logs are also output to the console, with colorization for different log levels in development.

---
This README provides a comprehensive guide to understanding, setting up, and running the Binance Copy Trading History Monitor.
