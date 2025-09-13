# Kotak Neo Algo Trading Bot

import time
import datetime
import pandas as pd
import yfinance as yf
from neo_api_client import NeoAPI
import schedule
import logging

# --- Start of User Configuration ---

# 1. Kotak Neo API Credentials
# IMPORTANT: Fill in your actual credentials below.
# You can get these from the Kotak Securities developer portal.
# Keep this information secure and do not share it.
CONSUMER_KEY = "your_consumer_key"
CONSUMER_SECRET = "your_consumer_secret"
NEO_FIN_KEY = "your_neo_fin_key"  # Received via email upon API registration

# 2. User Account Details
# IMPORTANT: Fill in your account details for login.
UCC = "your_ucc"  # Your Unique Client Code (UCC)
MOBILE_NUMBER = "your_10_digit_mobile_number" # Your registered 10-digit mobile number
MPIN = "your_4_digit_mpin"  # Your MPIN for the Kotak Neo platform
PASSWORD = "your_password" # Your password for the Kotak Neo platform

# 3. Strategy Parameters
# Define the underlying index and trading parameters.
INDEX_SYMBOL = "^NSEI"  # Yahoo Finance ticker for the index (e.g., ^NSEI for Nifty 50, ^BSESN for Sensex)
TRADING_SYMBOL_PREFIX = "NIFTY" # The prefix for the trading symbol (e.g., NIFTY, BANKNIFTY)
STRIKE_DIFFERENCE = 50  # The difference between strike prices (e.g., 50 for Nifty, 100 for Bank Nifty)
PRODUCT_TYPE = "NRML"  # Product type: NRML (Normal), MIS (Intraday)
QUANTITY = 50  # The quantity to trade (e.g., one lot size)

# 4. Bot Timings
# Define the trading window for the bot.
ENTRY_TIME = "09:30"
EXIT_TIME = "15:00"

# --- End of User Configuration ---

# --- Global Variables ---
client = None
open_positions = []

# --- Main Logic ---

def setup_logging():
    """Sets up the logging configuration."""
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.FileHandler("trading_bot.log"),
                                  logging.StreamHandler()])

def login_to_kotak():
    """Handles the login process for the Kotak Neo API."""
    global client
    try:
        client = NeoAPI(consumer_key=CONSUMER_KEY,
                        consumer_secret=CONSUMER_SECRET,
                        environment='prod') # Use 'uat' for testing if available

        # Step 1: TOTP Login
        totp = input("Enter the TOTP from your authenticator app: ")
        client.totp_login(mobile_number=MOBILE_NUMBER, ucc=UCC, totp=totp)
        logging.info("TOTP Login successful.")

        # Step 2: Validate session with MPIN
        client.totp_validate(mpin=MPIN)
        logging.info("Session validated with MPIN. Login complete.")
        return True

    except Exception as e:
        logging.error(f"Failed to login to Kotak Neo API: {e}")
        return False

# --- Trading Strategy Functions ---

def get_index_ltp(symbol):
    """Fetches the Last Traded Price of the index from yfinance."""
    try:
        ticker = yf.Ticker(symbol)
        # Use "1d" period and "1m" interval to get the most recent data point
        data = ticker.history(period="1d", interval="1m")
        ltp = data['Close'].iloc[-1]
        logging.info(f"LTP for {symbol} is {ltp:.2f}")
        return ltp
    except Exception as e:
        logging.error(f"Could not fetch LTP for {symbol}: {e}")
        return None

def get_atm_strike(ltp):
    """Calculates the At-The-Money (ATM) strike price."""
    return round(ltp / STRIKE_DIFFERENCE) * STRIKE_DIFFERENCE

def get_weekly_expiry_date():
    """
    Calculates the nearest weekly expiry date (Thursday).
    If today is Thursday and before market close, it's today.
    If today is after Thursday, it's next Thursday.
    """
    today = datetime.date.today()
    # Thursday is weekday 3 (0=Monday, 1=Tuesday, ..., 6=Sunday)
    days_ahead = (3 - today.weekday() + 7) % 7
    expiry_date = today + datetime.timedelta(days=days_ahead)
    return expiry_date

def get_option_instrument(strike_price, option_type):
    """
    Finds the instrument token and trading symbol for a given option.

    Args:
        strike_price (int): The strike price of the option.
        option_type (str): 'CE' for Call Option, 'P' for Put Option.

    Returns:
        dict: A dictionary containing 'token' and 'symbol', or None.
    """
    try:
        expiry_date = get_weekly_expiry_date()
        # Format for search_scrip: DDMMMYY, e.g., 26SEP24
        expiry_str = expiry_date.strftime('%d%b%y').upper()

        search_result = client.search_scrip(
            exchange_segment="nse_fo",
            symbol=TRADING_SYMBOL_PREFIX,
            expiry=expiry_str,
            option_type=option_type,
            strike_price=str(strike_price)
        )

        if search_result and search_result['data']:
            instrument = search_result['data'][0]
            logging.info(f"Found instrument for {strike_price} {option_type}: {instrument['tsym']}")
            return {'token': instrument['token'], 'symbol': instrument['tsym']}
        else:
            logging.warning(f"Could not find instrument for {strike_price} {option_type} with expiry {expiry_str}")
            return None
    except Exception as e:
        logging.error(f"Error searching for instrument {strike_price} {option_type}: {e}")
        return None

def get_option_premiums(call_instrument, put_instrument):
    """Fetches the premiums (LTP) for the given call and put options."""
    try:
        instruments_to_fetch = [
            {"instrument_token": call_instrument['token'], "exchange_segment": "nse_fo"},
            {"instrument_token": put_instrument['token'], "exchange_segment": "nse_fo"}
        ]

        quote_response = client.quotes(instrument_tokens=instruments_to_fetch, quote_type="ltp")

        if quote_response and quote_response.get('data'):
            call_premium = None
            put_premium = None
            for item in quote_response['data']:
                if item.get('instrument_token') == call_instrument['token']:
                    call_premium = float(item.get('last_traded_price', 0))
                if item.get('instrument_token') == put_instrument['token']:
                    put_premium = float(item.get('last_traded_price', 0))

            if call_premium is not None and put_premium is not None:
                logging.info(f"Premiums: Call={call_premium}, Put={put_premium}")
                return call_premium, put_premium

        logging.error("Could not fetch premiums from quote response.")
        return None, None

    except Exception as e:
        logging.error(f"Error fetching option premiums: {e}")
        return None, None

def place_order(trading_symbol, transaction_type):
    """Places a sell order."""
    try:
        order_response = client.place_order(
            exchange_segment="nse_fo",
            product=PRODUCT_TYPE,
            price="0", # Market order
            order_type="MKT",
            quantity=str(QUANTITY),
            validity="DAY",
            trading_symbol=trading_symbol,
            transaction_type=transaction_type, # 'S' for sell, 'B' for buy
            amo="NO"
        )
        if order_response and order_response.get('data', {}).get('order_id'):
            order_id = order_response['data']['order_id']
            logging.info(f"Successfully placed {transaction_type} order for {trading_symbol}. Order ID: {order_id}")
            return order_id
        else:
            logging.error(f"Failed to place {transaction_type} order for {trading_symbol}. Response: {order_response}")
            return None
    except Exception as e:
        logging.error(f"Exception placing {transaction_type} order for {trading_symbol}: {e}")
        return None

def run_strategy():
    """The main function that executes the trading strategy logic."""
    # Only run if we haven't entered a position yet
    if open_positions:
        logging.info("Positions are already open. Skipping entry check.")
        return

    logging.info("--- Running Strategy Check ---")

    # Get Index LTP and calculate ATM strike
    ltp = get_index_ltp(INDEX_SYMBOL)
    if ltp is None:
        return

    atm_strike = get_atm_strike(ltp)
    logging.info(f"ATM Strike determined to be: {atm_strike}")

    # Get instruments for ATM call and put
    call_instrument = get_option_instrument(atm_strike, 'CE')
    put_instrument = get_option_instrument(atm_strike, 'P')

    if not call_instrument or not put_instrument:
        logging.error("Could not find instruments for one or both options. Halting strategy check.")
        return

    # Get premiums
    call_premium, put_premium = get_option_premiums(call_instrument, put_instrument)
    if call_premium is None or put_premium is None:
        logging.error("Could not fetch premiums. Halting strategy check.")
        return

    combined_premium = call_premium + put_premium
    logging.info(f"Combined Premium: {combined_premium:.2f}")

    # Get VWAP
    vwap = calculate_vwap(INDEX_SYMBOL)
    if vwap is None:
        logging.error("Could not calculate VWAP. Halting strategy check.")
        return

    # Check entry condition
    if vwap <= combined_premium:
        logging.info("Entry condition met: VWAP <= Combined Premium.")
        logging.info(f"Attempting to sell ATM strangle: {call_instrument['symbol']} and {put_instrument['symbol']}")

        # Place sell orders
        call_order_id = place_order(call_instrument['symbol'], 'S')
        put_order_id = place_order(put_instrument['symbol'], 'S')

        if call_order_id and put_order_id:
            global open_positions
            open_positions = [call_instrument, put_instrument]
            logging.info("Successfully sold strangle. Now monitoring for exit time.")
            # Stop trying to enter more positions for today
            schedule.clear('entry-job')
        else:
            logging.error("Failed to place one or both sell orders.")
    else:
        logging.info(f"Entry condition not met: VWAP ({vwap:.2f}) > Combined Premium ({combined_premium:.2f})")

def square_off_positions():
    """Squares off any open positions and logs out."""
    global open_positions
    logging.info("--- Initiating Square Off ---")
    if not open_positions:
        logging.info("No open positions to square off.")
    else:
        for position in open_positions:
            logging.info(f"Squaring off {position['symbol']}...")
            place_order(position['symbol'], 'B') # 'B' for Buy to square off

    try:
        if client:
            client.logout()
            logging.info("Successfully logged out.")
    except Exception as e:
        logging.error(f"Error during logout: {e}")

    logging.info("Trading bot has finished its tasks for the day.")
    # Stop the schedule loop
    return schedule.CancelJob


def calculate_vwap(symbol):
    """
    Calculates the Volume Weighted Average Price (VWAP) for a given symbol.

    Args:
        symbol (str): The stock symbol (ticker) for which to calculate VWAP.
                      For yfinance, use tickers like '^NSEI' for Nifty 50.

    Returns:
        float: The calculated VWAP, or None if calculation fails.
    """
    try:
        # Download intraday data for the current day (period="1d") with a 1-minute interval
        data = yf.download(tickers=symbol, period="1d", interval="1m", progress=False)

        if data.empty:
            logging.warning(f"No data returned for {symbol}. It might be a holiday or pre-market.")
            return None

        # Calculate typical price and the cumulative values for VWAP
        data['TypicalPrice'] = (data['High'] + data['Low'] + data['Close']) / 3
        data['CumulativeVolume'] = data['Volume'].cumsum()
        data['CumulativePV'] = (data['TypicalPrice'] * data['Volume']).cumsum()

        # Calculate VWAP
        vwap = data['CumulativePV'].iloc[-1] / data['CumulativeVolume'].iloc[-1]

        logging.info(f"Calculated VWAP for {symbol}: {vwap:.2f}")
        return vwap

    except Exception as e:
        logging.error(f"Failed to calculate VWAP for {symbol}: {e}")
        return None

if __name__ == "__main__":
    setup_logging()
    logging.info("--- Starting Trading Bot ---")

    # Check if it's a trading day (Monday to Friday)
    if datetime.date.today().weekday() >= 5:
        logging.info("Today is a weekend. The bot will not run.")
    else:
        if login_to_kotak():
            logging.info("Successfully logged into Kotak Neo.")

            # --- Schedule Jobs ---
            # Schedule the entry strategy to run every minute after the ENTRY_TIME.
            schedule.every(1).minutes.do(run_strategy).tag('entry-job')
            # Schedule the exit strategy to run once at EXIT_TIME.
            schedule.every().day.at(EXIT_TIME).do(square_off_positions)

            logging.info(f"Bot is now running. Entry checks will start after {ENTRY_TIME}. Exit is scheduled for {EXIT_TIME}.")

            # --- Main Loop ---
            while True:
                # Get the current time in HH:MM format
                current_time = datetime.datetime.now().strftime("%H:%M")

                # Only start running jobs after the entry time
                if current_time >= ENTRY_TIME:
                    schedule.run_pending()

                # If the exit job has run and cancelled all jobs, break the loop
                if not schedule.jobs:
                    break

                time.sleep(1) # Sleep for a second to prevent high CPU usage
        else:
            logging.error("Could not start trading bot due to login failure.")

    logging.info("--- Trading Bot Shut Down ---")
