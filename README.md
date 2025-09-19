# NIFTY ATM Straddle Trading Bot for Kotak Neo

This project is a Python-based algorithmic trading bot that implements a specific NIFTY ATM (At-The-Money) straddle strategy using the Kotak Neo trading API.

**DISCLAIMER: This is trading software. Trading in financial markets involves substantial risk. Use this software at your own risk. The author is not responsible for any financial losses you may incur. It is highly recommended to test this bot thoroughly in a simulated or paper trading environment before using it with real money.**

## Trading Strategy Rules

The bot follows these rules:
1.  **Entry Time**: 9:30 AM, based on the 15-minute candle close.
2.  **Instrument**: Sells an ATM straddle (1 Call, 1 Put) of the current weekly NIFTY options.
3.  **Entry Condition**: The bot will only enter a trade if the combined premium of the ATM call and put is **below** the NIFTY index's VWAP (Volume Weighted Average Price). If it's above VWAP at 9:30 AM, it will wait and enter the first time the premium crosses below the VWAP on a 1-minute timeframe.
4.  **Dynamic Exit (Hedging)**:
    *   If the combined premium moves **above** the VWAP line, the bot will close one leg of the straddle to run with the market trend.
    *   If the market is moving up, the Call option is closed.
    *   If the market is moving down, the Put option is closed.
5.  **Re-entry**: If the combined premium falls back **below** the VWAP line after one leg has been closed, the bot will re-sell the closed leg. This re-entry is attempted only once.
6.  **Order Type**: Uses Intraday (MIS) Market orders.
7.  **Exit Time**: All open positions are squared off at 3:00 PM.

## How to Set Up and Run the Bot

### Step 1: Prerequisites
- A Kotak Securities trading account.
- API access for your account. You can apply for this on the [Kotak Securities Trade API website](https://www.kotaksecurities.com/platform/kotak-neo-trade-api/).
- Python 3.10 or higher installed on your system.
- A TOTP (Time-based One-Time Password) authenticator app (like Google Authenticator) configured for your Kotak account.

### Step 2: Get Your API Credentials
Once your API access is approved, you will receive your `consumer_key`, `consumer_secret`, and `neo_fin_key`.

### Step 3: Clone and Install Dependencies
1.  Open a terminal or command prompt.
2.  Install the required Python libraries by running:
    ```bash
    pip install -r requirements.txt
    ```

### Step 4: Configure Your Credentials
1.  Open the `config.py` file in a text editor.
2.  Fill in your details for the following variables:
    - `consumer_key`
    - `consumer_secret`
    - `neo_fin_key`
    - `ucc` (Your Unique Client Code)
    - `mobile_number` (Your registered mobile number)
    - `password` (Your trading account password or MPIN)

### Step 5: Run the Bot
1.  Navigate to the project directory in your terminal.
2.  Run the main strategy script:
    ```bash
    python strategy.py
    ```
3.  When prompted, enter the 6-digit TOTP from your authenticator app into the terminal and press Enter.
4.  The bot will log in and start monitoring the market according to the strategy. You can observe its actions through the log messages printed in the terminal.

## Important Notes
- **Session Management**: The login session is valid for one trading day. You will need to restart the script and re-enter the TOTP each day.
- **Error Handling**: The bot includes basic error handling, but it may not cover all possible market scenarios or API issues. Monitor the bot's operation closely.
- **Customization**: You can tweak trading parameters like `lot_size` in the `config.py` file.
