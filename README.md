# NIFTY ATM Straddle Trading Bot for Kotak Neo

This project provides a complete framework for running and backtesting a specific NIFTY ATM (At-The-Money) straddle strategy using the Kotak Neo API.

**DISCLAIMER: Trading in financial markets involves substantial risk. Use this software at your own risk. The author is not responsible for any financial losses you may incur. It is highly recommended to backtest strategies thoroughly and run bots in a simulated environment before using real money.**

## Project Structure

The project is now separated into distinct components for clarity and functionality:

-   `live_bot.py`: The main script to run the bot for **live trading**.
-   `backtester.py`: The script to run a **backtest** of the strategy on historical data.
-   `strategy_logic.py`: Contains the core `Strategy` class with the pure trading rules, used by both the live bot and the backtester.
-   `kotak_client.py`: Handles all communication with the Kotak Neo API.
-   `config.py`: For all your credentials and strategy parameters.
-   `data.csv`: A sample file showing the data format required by the backtester.
-   `requirements.txt`: Lists all necessary Python libraries.

## The Trading Strategy

The core logic follows these rules:
1.  **Entry Time**: 9:30 AM.
2.  **Instrument**: Sells an ATM straddle (1 Call, 1 Put) of the current weekly NIFTY options.
3.  **Entry Condition**: Enters a trade only if the combined premium of the straddle is **below** the NIFTY index's VWAP. If above, it waits for the premium to cross below VWAP.
4.  **Dynamic Exit**: If the premium moves **above** VWAP, it closes one leg (Call if market is up, Put if market is down).
5.  **Re-entry**: If the premium falls back **below** VWAP, it re-sells the closed leg (this happens only once).
6.  **Exit Time**: Squares off all open positions at 3:00 PM.

---

## Part 1: Backtesting Your Strategy

Before running the bot live, you should backtest the strategy.

### Step 1: Prepare Your Historical Data

This is the most critical and challenging step. The backtester requires a CSV file with 1-minute data. You must procure this data from a data vendor.

The CSV file **must** have the following columns:
-   `datetime`: Timestamp in `YYYY-MM-DD HH:MM:SS` format.
-   `nifty_spot`: The spot price of the NIFTY index.
-   `nifty_vwap`: The VWAP of the NIFTY index for that minute.
-   `atm_strike`: The At-The-Money strike price for that day.
-   `call_symbol`: The trading symbol of the ATM call option for that strike and expiry.
-   `call_ltp`: The premium (price) of that call option.
-   `put_symbol`: The trading symbol of the ATM put option.
-   `put_ltp`: The premium (price) of that put option.

A sample file `data.csv` is included in this project to show you the exact format.

### Step 2: Run the Backtester

Once you have your data file (e.g., you've named it `my_historical_data.csv`):
1.  Open `backtester.py` in a text editor.
2.  Change the `DATA_FILE_PATH` variable to point to your file:
    ```python
    DATA_FILE_PATH = 'my_historical_data.csv'
    ```
3.  Save the file.
4.  Open your Anaconda Prompt and navigate to the project folder.
5.  Run the backtester with the command:
    ```bash
    python backtester.py
    ```
The script will run through your data and print a final Profit/Loss summary.

---

## Part 2: Live Trading

Once you are confident in the strategy, you can run the bot live.

### Step 1: Prerequisites & Setup
- A Kotak Securities trading account with API access.
- Python 3.10+ and Anaconda installed.
- Open your Anaconda Prompt and navigate to the project folder.
- Install all required libraries:
  ```bash
  pip install -r requirements.txt
  ```
  *(Note: If you face installation issues, please refer to the troubleshooting steps in our previous conversations regarding installing dependencies on Windows).*

### Step 2: Configure Your Credentials
1.  Open the `config.py` file.
2.  Fill in your `consumer_key`, `consumer_secret`, `neo_fin_key`, `ucc`, `mobile_number`, and `password`.

### Step 3: Run the Live Bot
1.  In your Anaconda Prompt (in the project folder), run the command:
    ```bash
    python live_bot.py
    ```
2.  When prompted, enter the 6-digit TOTP from your authenticator app.
3.  The bot will log in and start monitoring the market. You can leave the window open to see its log messages.
