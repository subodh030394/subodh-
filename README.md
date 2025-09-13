# Kotak Neo Algorithmic Trading Bot

This Python script is an algorithmic trading bot that works with the Kotak Neo trading platform. It implements a specific options selling strategy based on VWAP and combined option premiums, designed for beginners in algorithmic trading.

**DISCLAIMER: Trading in the stock market involves significant risk. This is an educational tool and not financial advice. You are solely responsible for any financial losses you may incur by using this script. Always test thoroughly in a simulated or paper trading environment before using real money.**

## Strategy Implemented

*   **Entry Time:** The bot will only look for entry signals after 9:30 AM.
*   **Exit Time:** The bot will automatically square off any open positions at 3:00 PM sharp.
*   **Instruments:** The bot trades weekly ATM (At-The-Money) Call and Put options for a configured index (e.g., Nifty 50).
*   **Entry Condition:**
    1.  It calculates the **combined premium** of the ATM call and put options.
    2.  It calculates the **VWAP** (Volume-Weighted Average Price) of the underlying index using 1-minute data.
    3.  It creates a short strangle (sells both the call and the put) **only if the index's VWAP is less than or equal to the combined premium**.
*   **Execution:** If the condition is met, it places the trades and stops looking for new entries for the day. If the condition is not met, it checks again every minute.

## Setup Instructions

### 1. Prerequisites
*   A Kotak Neo account.
*   You must apply for and get approval for the Kotak Neo Trade API. You can do this from the Kotak Securities website.
*   Python 3.10+ installed on your system.
*   An authenticator app (like Google Authenticator or Authy) installed on your smartphone.

### 2. Register for TOTP
Before you can log in via the API, you must register for Time-based One-Time Password (TOTP) generation.
*   Visit the [Kotak Trade API page](https://www.kotaksecurities.com/platform/kotak-neo-trade-api/) and find the option to "Register for TOTP".
*   Follow the on-screen instructions, which will involve verifying your mobile number and scanning a QR code with your authenticator app.
*   Once complete, your app will generate a new 6-digit code every 30 seconds. You will need this code every time you start the bot.

### 3. Installation
*   Download the `main.py` and `requirements.txt` files to a folder on your computer.
*   Open a terminal or command prompt, navigate to that folder, and install the required Python libraries by running:
    ```bash
    pip install -r requirements.txt
    ```

### 4. Configuration
*   Open the `main.py` file in a text editor.
*   Carefully fill in your credentials and parameters in the "User Configuration" section at the top of the file.
    *   `CONSUMER_KEY`, `CONSUMER_SECRET`, `NEO_FIN_KEY`: You will get these from the Kotak Neo developer portal after your API access is approved.
    *   `UCC`: Your Unique Client Code.
    *   `MOBILE_NUMBER`: Your 10-digit mobile number registered with Kotak.
    *   `MPIN`: The 4-digit MPIN you use to log in to the Kotak Neo platform.
    *   `INDEX_SYMBOL`: The Yahoo Finance symbol for the index (e.g., `^NSEI` for Nifty 50).
    *   `TRADING_SYMBOL_PREFIX`: The prefix used in the F&O market (e.g., `NIFTY`, `BANKNIFTY`).
    *   `QUANTITY`: The lot size of the instrument you are trading.

### 5. Running the Bot
*   Open a terminal or command prompt and navigate to the folder where you saved the files.
*   Run the bot with the following command:
    ```bash
    python main.py
    ```
*   The script will start, and you will be prompted to **enter the TOTP** from your authenticator app.
*   Enter the current 6-digit code and press Enter.
*   If the login is successful, the bot will start monitoring the market according to the schedule. You can see its activity printed in the terminal and saved in the `trading_bot.log` file.
*   To stop the bot, you can press `Ctrl+C` in the terminal.
