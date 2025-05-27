# Python Binance Copy Trading History Monitor

## Description

This Python application monitors the trade history of specified Binance copy trading portfolios. It fetches trade data directly from the Binance API using a Python script, processes it, stores it in a MongoDB database to prevent duplicates, and saves JSON backups of newly fetched trades.

## Features

-   **Data Fetching:** Regularly fetches new trade data from Binance's copy trading API.
-   **Multi-stage Deduplication:** Ensures that each trade is stored only once in the database (based on original trade ID and portfolio ID).
-   **MongoDB Storage:** Stores trade data persistently in a MongoDB database.
-   **Scheduled Data Collection:** Automatically fetches data at regular, configurable intervals.
-   **JSON File Output:** Saves backups of newly processed trades for each portfolio in the `data/` directory.
-   **Configurable:** Most operational parameters (API keys, database URIs, fetch intervals) are configurable via a `.env` file.
-   **Logging:** Comprehensive logging for application events, errors, and API requests.

## Prerequisites

-   Python 3.7+
-   `pip` (Python package installer)
-   A running MongoDB instance (local or remote)

## Setup and Configuration

1.  **Clone the Repository or Download Files:**
    ```bash
    # If it's a git repository:
    # git clone <repository_url>
    # cd <repository_name>
    ```
    If you downloaded the files, ensure they are in a project directory.

2.  **Create and Activate a Virtual Environment (Recommended):**
    Navigate to the project directory in your terminal.
    ```bash
    python -m venv venv
    ```
    Activate the virtual environment:
    *   On Linux/macOS:
        ```bash
        source venv/bin/activate
        ```
    *   On Windows:
        ```bash
        venv\Scripts\activate
        ```

3.  **Install Dependencies:**
    With your virtual environment activated, install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Up Environment Variables:**
    Create a `.env` file in the root of your project directory by copying the example file:
    ```bash
    cp .env.example .env
    ```
    Now, edit the `.env` file and provide the necessary values:

    *   `BNS_UUID`: **(Required)** Your Binance session UUID. This is needed to authenticate with the Binance API.
        *   **How to obtain `BNS_UUID`**: To get your `BNS_UUID`, log in to your Binance account, open your browser's developer tools (usually by pressing F12), go to the Network tab, and then navigate to the Copy Trading section on the Binance website. Look for requests to the Binance API (e.g., requests to `/bapi/futures/...`). The `bns-uuid` will be present in the request headers of these API calls. Copy its value.
    *   `PORTFOLIO_IDS`: **(Required)** A comma-separated list of Binance copy trading portfolio IDs you want to monitor (e.g., `your_portfolio_id_1,your_portfolio_id_2`).
    *   `MONGODB_URI`: **(Required)** The connection string for your MongoDB database (e.g., `mongodb://localhost:27017/`).
    *   `DB_NAME`: The name of the database to use in MongoDB (e.g., `binance_copy_trades_python`).
    *   `TRADE_COLLECTION_NAME`: The name of the collection to store trades within the database (e.g., `trades`).
    *   `FETCH_INTERVAL_MINUTES`: The interval (in minutes) at which the script will fetch new data (e.g., `5`).
    *   `FETCH_WINDOW_MINUTES`: The duration (in minutes) of the time window for fetching trades. For example, if set to `10`, the script will fetch trades from the last 10 minutes (e.g., `10`).
    *   `INITIAL_JOB_DELAY_SECONDS`: The delay (in seconds) before the first data fetching job runs after the application starts (e.g., `10`).
    *   `LOG_LEVEL`: The logging level for the application (e.g., `INFO`, `DEBUG`, `WARNING`, `ERROR`).
    *   `LOG_FILE_APP`: The path to the main application log file (e.g., `logs/app.log`).
    *   `LOG_FILE_ERROR`: The path to the error log file, which will only contain error messages (e.g., `logs/error.log`).

## Running the Application

1.  **Start the Script:**
    Ensure your virtual environment is activated and your `.env` file is correctly configured. Then, run:
    ```bash
    python main.py
    ```
    This is a long-running script. It will initialize and then periodically fetch data based on the configured schedule. You will see log output in the console and in the log files.

2.  **Stopping the Script:**
    To stop the script, press `Ctrl+C` in the terminal where it is running.

## Project Structure

```
.
├── data/                   # Directory for storing JSON backups of fetched trades
├── logs/                   # Directory for log files (app.log, error.log)
├── venv/                   # Python virtual environment (if created, ignored by git)
├── .env                    # Environment variables (ignored by git - MUST BE CREATED)
├── .env.example            # Example environment variables
├── .gitignore              # Specifies intentionally untracked files for Git
├── binance_client.py       # Handles communication with the Binance API
├── config.py               # Loads configuration from .env and sets up logging
├── database.py             # Manages MongoDB connection and database operations
├── data_processor.py       # Processes and transforms trade data, handles deduplication
├── main.py                 # Main application entry point, initializes and starts the scheduler
├── requirements.txt        # Lists Python dependencies for the project
├── scheduler_service.py    # Manages the scheduling of data fetching jobs
└── README.md               # This file
```

## Logging

-   Logs are output to the console.
-   Logs are also saved to files within the `logs/` directory:
    -   `app.log` (or as configured by `LOG_FILE_APP`): Contains general application logs based on the `LOG_LEVEL`.
    -   `error.log` (or as configured by `LOG_FILE_ERROR`): Contains only error-level logs.
-   The verbosity of logs can be controlled by setting the `LOG_LEVEL` in the `.env` file.

## Data Output

-   **MongoDB:** All successfully processed and deduplicated trades are stored in the MongoDB database, as configured by `MONGODB_URI`, `DB_NAME`, and `TRADE_COLLECTION_NAME`.
-   **JSON Backups:** For each portfolio, any newly fetched and processed trades during a job run are saved as a JSON file in the `data/` directory. These files are named with the portfolio ID and a timestamp (e.g., `data/your_portfolio_id_1_YYYYMMDD_HHMMSS.json`). This provides a file-based backup of new trades.

---
This README provides a guide to setting up, configuring, and running the Python Binance Copy Trading History Monitor.
