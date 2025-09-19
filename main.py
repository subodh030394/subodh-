# Kotak Neo Algo Trading Bot

import time
import datetime
import pandas as pd
import yfinance as yf
from neo_api_client import NeoAPI, BaseUrl
import schedule
import logging

# --- Start of User Configuration ---
# IMPORTANT: Do not commit this file with your credentials filled in.
# Keep this information secure and do not share it.

# 1. Kotak Neo API Credentials
CONSUMER_KEY = "your_consumer_key"
CONSUMER_SECRET = "your_consumer_secret"
NEO_FIN_KEY = "your_neo_fin_key"

# 2. User Account Details
UCC = "your_ucc"
MOBILE_NUMBER = "your_10_digit_mobile_number"
MPIN = "your_4_digit_mpin"

# 3. Strategy Parameters
INDEX_SYMBOL = "^NSEBANK"
TRADING_SYMBOL_PREFIX = "BANKNIFTY"
STRIKE_DIFFERENCE = 100
PRODUCT_TYPE = "MIS"
LOT_SIZE = 15 # Bank Nifty lot size
NUM_LOTS = 1
QUANTITY = LOT_SIZE * NUM_LOTS
STOP_LOSS_AMOUNT = -750.0

# 4. Bot Timings
ENTRY_TIME = "09:16" # Start collecting data after the 9:15 candle opens
TRADING_START_TIME = "09:30" # Start executing trading logic
EXIT_TIME = "15:00"

# --- End of User Configuration ---

# --- Global Variables ---
client = None
bot_state = {}
price_data = pd.DataFrame(columns=['timestamp', 'combined_premium'])

def reset_bot_state():
    """Initializes or resets the bot's state for the day."""
    global bot_state, price_data
    bot_state = {
        "straddle_selected": False,
        "initial_entry_taken": False,
        "is_trading_window_open": False,
        "premium_crossed_above_twap": False,

        "call_instrument": None,
        "put_instrument": None,

        "call_leg_open": False,
        "put_leg_open": False,

        "call_entry_price": 0.0,
        "put_entry_price": 0.0,

        "call_re_entry_used": False,
        "put_re_entry_used": False,

        "entry_index_ltp": None,
    }
    price_data = pd.DataFrame(columns=['timestamp', 'combined_premium'])
    logging.info("Bot state has been reset for the day.")

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
        base_url = BaseUrl(UCC).get_base_url()
        client = NeoAPI(consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET, environment='prod', base_url=base_url)
        totp = input("Enter the TOTP from your authenticator app: ")
        client.totp_login(mobile_number=MOBILE_NUMBER, ucc=UCC, totp=totp)
        logging.info("TOTP Login successful.")
        client.totp_validate(mpin=MPIN)
        logging.info("Session validated with MPIN. Login complete.")
        return True
    except Exception as e:
        logging.error(f"Failed to login to Kotak Neo API: {e}")
        return False

# --- Data and Instrument Functions ---

def get_index_ltp(symbol):
    """Fetches the Last Traded Price of the index from yfinance."""
    try:
        data = yf.Ticker(symbol).history(period="1d", interval="1m")
        ltp = data['Close'].iloc[-1]
        return ltp
    except Exception as e:
        logging.error(f"Could not fetch LTP for {symbol}: {e}")
        return None

def get_atm_strike(ltp):
    """Calculates the At-The-Money (ATM) strike price."""
    return round(ltp / STRIKE_DIFFERENCE) * STRIKE_DIFFERENCE

def get_weekly_expiry_date():
    """Calculates the nearest weekly expiry date (Thursday)."""
    today = datetime.date.today()
    days_ahead = (3 - today.weekday() + 7) % 7
    return today + datetime.timedelta(days=days_ahead)

def get_option_instrument(strike_price, option_type):
    """Finds the instrument token and trading symbol for a given option."""
    try:
        expiry_str = get_weekly_expiry_date().strftime('%d%b%y').upper()
        search_result = client.search_scrip(exchange_segment="nse_fo", symbol=TRADING_SYMBOL_PREFIX, expiry=expiry_str, option_type=option_type, strike_price=str(strike_price))
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
        instruments = []
        if call_instrument:
            instruments.append({"instrument_token": call_instrument['token'], "exchange_segment": "nse_fo"})
        if put_instrument:
            instruments.append({"instrument_token": put_instrument['token'], "exchange_segment": "nse_fo"})

        quote_response = client.quotes(instrument_tokens=instruments, quote_type="ltp")

        call_premium = None
        put_premium = None

        if quote_response and quote_response.get('data'):
            if call_instrument:
                call_premium = next((float(item.get('last_traded_price', 0)) for item in quote_response['data'] if item.get('instrument_token') == call_instrument['token']), None)
            if put_instrument:
                put_premium = next((float(item.get('last_traded_price', 0)) for item in quote_response['data'] if item.get('instrument_token') == put_instrument['token']), None)
            return call_premium, put_premium

        logging.error("Could not fetch premiums from quote response.")
        return None, None
    except Exception as e:
        logging.error(f"Error fetching option premiums: {e}")
        return None, None

# --- Core Strategy Logic ---

def initial_setup():
    """Runs once at the start of the session to determine the ATM straddle."""
    logging.info("--- Running Initial Setup for 9:16 AM ---")
    ltp = get_index_ltp(INDEX_SYMBOL)
    if ltp is None:
        logging.error("Could not get LTP to determine ATM strike. Setup failed.")
        return
    atm_strike = get_atm_strike(ltp)
    logging.info(f"ATM Strike determined to be: {atm_strike}")
    bot_state['call_instrument'] = get_option_instrument(atm_strike, 'CE')
    bot_state['put_instrument'] = get_option_instrument(atm_strike, 'P')
    if not bot_state['call_instrument'] or not bot_state['put_instrument']:
        logging.error("Could not find instruments for one or both options. Setup failed.")
        return
    bot_state['straddle_selected'] = True
    logging.info(f"Straddle selected: {bot_state['call_instrument']['symbol']} and {bot_state['put_instrument']['symbol']}")
    return schedule.CancelJob

def update_and_calculate_twap():
    """
    Fetches premiums and calculates the TWAP for the straddle.
    Note: TWAP (Time-Weighted Average Price) is used as a practical proxy for VWAP
    (Volume-Weighted Average Price) because per-minute volume data for a combined,
    synthetic instrument like a straddle is not readily available.
    """
    if not bot_state.get('straddle_selected'):
        return None, None, None, None
    call_premium, put_premium = get_option_premiums(bot_state['call_instrument'], bot_state['put_instrument'])
    if call_premium is None or put_premium is None:
        return None, None, None, None
    combined_premium = call_premium + put_premium
    global price_data
    new_row = pd.DataFrame({'timestamp': [datetime.datetime.now()], 'combined_premium': [combined_premium]})
    price_data = pd.concat([price_data, new_row], ignore_index=True)
    premium_twap = price_data['combined_premium'].mean()
    logging.info(f"Premiums C:{call_premium:.2f}, P:{put_premium:.2f} | Combined:{combined_premium:.2f} | TWAP:{premium_twap:.2f}")
    return call_premium, put_premium, combined_premium, premium_twap

def place_order(trading_symbol, transaction_type):
    """Places a market order."""
    try:
        order_response = client.place_order(exchange_segment="nse_fo", product=PRODUCT_TYPE, price="0", order_type="MKT", quantity=str(QUANTITY), validity="DAY", trading_symbol=trading_symbol, transaction_type=transaction_type, amo="NO")
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

def check_for_entry(call_premium, put_premium, combined_premium, premium_twap):
    """
    Checks and executes the entry logic based on Rules 3, 4, 12, 13.
    Note: The "on candle close" basis (Rule 13) is implemented by checking the state
    every minute. On a 1-minute timeframe, this is a robust and practical proxy.
    """
    if not bot_state['premium_crossed_above_twap']:
        if combined_premium > premium_twap:
            bot_state['premium_crossed_above_twap'] = True
            logging.info("Condition met: Premium crossed above TWAP. Now monitoring for an entry signal.")
        else:
            logging.info("Condition not met: Premium is still below TWAP. Waiting for it to cross above before entry.")
        return

    if combined_premium < premium_twap:
        logging.info(f"ENTRY SIGNAL: Premium ({combined_premium:.2f}) < TWAP ({premium_twap:.2f}).")
        entry_ltp = get_index_ltp(INDEX_SYMBOL)
        if entry_ltp is None:
            logging.error("Could not get index LTP at entry. Cannot proceed with entry.")
            return
        logging.info("Attempting to sell ATM straddle...")
        call_order_id = place_order(bot_state['call_instrument']['symbol'], 'S')
        put_order_id = place_order(bot_state['put_instrument']['symbol'], 'S')
        if call_order_id and put_order_id:
            logging.info("Successfully sold straddle.")
            bot_state.update({"initial_entry_taken": True, "call_leg_open": True, "put_leg_open": True,
                              "call_entry_price": call_premium, "put_entry_price": put_premium,
                              "entry_index_ltp": entry_ltp})
        else:
            logging.error("Failed to place one or both sell orders for straddle entry.")

def calculate_legs_pnl(current_call_premium, current_put_premium):
    """Calculates the P&L for each open leg based on entry price."""
    pnl = {"call": 0.0, "put": 0.0, "total": 0.0}
    if bot_state['call_leg_open']:
        # For a short position, P&L = (entry_price - current_price) * quantity
        pnl["call"] = (bot_state['call_entry_price'] - current_call_premium) * QUANTITY
    if bot_state['put_leg_open']:
        pnl["put"] = (bot_state['put_entry_price'] - current_put_premium) * QUANTITY
    pnl["total"] = pnl["call"] + pnl["put"]
    return pnl

def manage_open_positions(call_premium, put_premium, combined_premium, premium_twap):
    """Manages open positions based on the user's rules."""
    pnl = calculate_legs_pnl(call_premium, put_premium)
    logging.info(f"P&L Check: Call P&L: {pnl['call']:.2f}, Put P&L: {pnl['put']:.2f}, Total P&L: {pnl['total']:.2f}")

    # Stop-Loss Logic (Rules 5, 6, 14)
    if combined_premium > premium_twap:
        if pnl['total'] > STOP_LOSS_AMOUNT:
            logging.info(f"Premium > TWAP, but loss ({pnl['total']:.2f}) is within threshold of {STOP_LOSS_AMOUNT}.")
            return

        logging.warning(f"STOP LOSS triggered. Premium > TWAP and P&L ({pnl['total']:.2f}) has breached {STOP_LOSS_AMOUNT}.")

        # Determine market direction to decide which leg to close (Rules 5 & 6)
        current_ltp = get_index_ltp(INDEX_SYMBOL)
        entry_ltp = bot_state.get('entry_index_ltp')

        if current_ltp is None or entry_ltp is None:
            logging.error("Cannot determine market direction. Skipping leg closing.")
            return

        # Rule 5: If market is moving up, close the call option
        if current_ltp > entry_ltp and bot_state['call_leg_open']:
            logging.info("Market is up. Closing CALL leg as per Rule 5.")
            place_order(bot_state['call_instrument']['symbol'], 'B')
            bot_state['call_leg_open'] = False

        # Rule 6: If market is moving down, close the put option
        elif current_ltp <= entry_ltp and bot_state['put_leg_open']:
            logging.info("Market is down. Closing PUT leg as per Rule 6.")
            place_order(bot_state['put_instrument']['symbol'], 'B')
            bot_state['put_leg_open'] = False

    # Re-entry Logic (Rule 7)
    elif combined_premium < premium_twap:
        if not bot_state['call_leg_open'] and not bot_state['call_re_entry_used']:
            logging.info("RE-ENTRY signal for CALL leg. Premium has gone back below TWAP.")
            new_call_price, _ = get_option_premiums(bot_state['call_instrument'], None)
            if new_call_price:
                place_order(bot_state['call_instrument']['symbol'], 'S')
                bot_state.update({"call_leg_open": True, "call_re_entry_used": True, "call_entry_price": new_call_price})

        if not bot_state['put_leg_open'] and not bot_state['put_re_entry_used']:
            logging.info("RE-ENTRY signal for PUT leg. Premium has gone back below TWAP.")
            _, new_put_price = get_option_premiums(None, bot_state['put_instrument'])
            if new_put_price:
                place_order(bot_state['put_instrument']['symbol'], 'S')
                bot_state.update({"put_leg_open": True, "put_re_entry_used": True, "put_entry_price": new_put_price})

def run_strategy():
    """The main function that executes the trading strategy logic."""
    current_time = datetime.datetime.now().strftime("%H:%M")
    logging.info(f"--- Running Strategy Check at {current_time} ---")

    if not bot_state.get('straddle_selected'):
        logging.info("Straddle not selected yet. Waiting for 9:16 AM setup.")
        return

    call_premium, put_premium, combined_premium, premium_twap = update_and_calculate_twap()
    if combined_premium is None:
        return

    if not bot_state['is_trading_window_open'] and current_time >= TRADING_START_TIME:
        logging.info(f"--- TRADING WINDOW IS NOW OPEN ({TRADING_START_TIME}) ---")
        bot_state['is_trading_window_open'] = True

    if not bot_state['is_trading_window_open']:
        logging.info("Data collection phase (pre-9:30 AM). No trading will be executed.")
        return

    if bot_state.get('initial_entry_taken'):
        manage_open_positions(call_premium, put_premium, combined_premium, premium_twap)
    else:
        check_for_entry(call_premium, put_premium, combined_premium, premium_twap)

def square_off_positions():
    """Squares off any open positions and logs out."""
    logging.info("--- Initiating Square Off ---")
    if bot_state.get('call_leg_open'):
        logging.info(f"Squaring off {bot_state['call_instrument']['symbol']}...")
        place_order(bot_state['call_instrument']['symbol'], 'B')
    if bot_state.get('put_leg_open'):
        logging.info(f"Squaring off {bot_state['put_instrument']['symbol']}...")
        place_order(bot_state['put_instrument']['symbol'], 'B')

    logging.info("Waiting a moment for square-off orders to execute...")
    time.sleep(5)

    try:
        if client:
            client.logout()
            logging.info("Successfully logged out.")
    except Exception as e:
        logging.error(f"Error during logout: {e}")
    logging.info("Trading bot has finished its tasks for the day.")
    return schedule.CancelJob

if __name__ == "__main__":
    setup_logging()
    logging.info("--- Starting Trading Bot ---")
    if datetime.date.today().weekday() < 5:
        if login_to_kotak():
            logging.info("Successfully logged into Kotak Neo.")
            reset_bot_state()
            schedule.every().day.at("09:16").do(initial_setup)
            schedule.every(1).minutes.do(run_strategy)
            schedule.every().day.at(EXIT_TIME).do(square_off_positions)
            logging.info(f"Bot is now running. Data collection starts at {ENTRY_TIME}. Trading starts at {TRADING_START_TIME}. Exit is at {EXIT_TIME}.")
            while True:
                if datetime.datetime.now().strftime("%H:%M") >= ENTRY_TIME:
                    schedule.run_pending()
                if not schedule.jobs:
                    break
                time.sleep(1)
        else:
            logging.error("Could not start trading bot due to login failure.")
    else:
        logging.info("Today is a weekend. The bot will not run.")
    logging.info("--- Trading Bot Shut Down ---")
