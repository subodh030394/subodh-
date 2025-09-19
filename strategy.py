"""
Main script for the NIFTY ATM Straddle trading strategy.

This script will:
1. Initialize the Kotak Neo API client.
2. Wait until the market opens at 9:30 AM.
3. Determine the ATM strike for NIFTY.
4. Check the entry condition (combined premium vs. VWAP).
5. Place the sell order for the straddle if conditions are met.
6. Monitor the position and apply exit/re-entry rules.
7. Exit all positions at 3:00 PM.
"""

import logging
import time
from datetime import datetime
import schedule
from kotak_client import KotakClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import yfinance as yf
import pandas_ta as ta
import pandas as pd
import config

class Strategy:
    """
    Encapsulates the entire trading strategy, state, and logic.
    """
    def __init__(self, client):
        self.client = client
        self.nifty_data = pd.DataFrame()

        # State variables
        self.atm_strike = None
        self.call_symbol = None
        self.put_symbol = None
        self.entry_spot_price = None

        self.position_entered = False
        self.call_leg_closed = False
        self.put_leg_closed = False
        self.re_entry_done = False

    def fetch_nifty_data(self):
        """Fetches 1-minute historical data for NIFTY 50 for the current day."""
        logging.info("Fetching NIFTY 50 1-minute data...")
        try:
            # ^NSEI is the ticker for NIFTY 50 index in yfinance
            self.nifty_data = yf.download(tickers="^NSEI", period="1d", interval="1m")
            if self.nifty_data.empty:
                logging.error("Failed to download NIFTY data. yfinance returned empty dataframe.")
                return False
            # Calculate VWAP using pandas-ta
            self.nifty_data.ta.vwap(append=True)
            logging.info("Successfully fetched NIFTY data and calculated VWAP.")
            return True
        except Exception as e:
            logging.error(f"Exception while fetching NIFTY data: {e}")
            return False

    def setup_for_day(self):
        """Gets the strategy ready at the start of the day."""
        logging.info("Performing daily setup...")

        # 1. Fetch historical data to calculate VWAP
        if not self.fetch_nifty_data():
            logging.error("Could not fetch NIFTY data. Aborting setup.")
            return

        # 2. Get the current NIFTY spot price to determine ATM strike
        spot_price = self.client.get_nifty_spot_price()
        if not spot_price:
            logging.error("Could not get NIFTY spot price. Aborting setup.")
            return

        # 3. Find the ATM strike and option symbols
        self.atm_strike, self.call_symbol, self.put_symbol = self.client.get_atm_strike_and_symbols(spot_price)
        if not self.atm_strike:
            logging.error("Could not determine ATM symbols. Aborting setup.")
            return

        logging.info("Daily setup complete. Ready to trade.")

    def trade_logic(self):
        """The main logic function that runs every minute."""
        logging.info("--- Running Trade Logic ---")

        # Get the latest NIFTY data and VWAP
        if self.nifty_data.empty:
            logging.warning("NIFTY data is not available. Skipping logic.")
            return

        last_vwap = self.nifty_data['VWAP_D'].iloc[-1]
        logging.info(f"Latest NIFTY VWAP: {last_vwap:.2f}")

        # Get current premiums for our ATM options
        call_ltp = self.client.get_ltp(self.call_symbol)
        put_ltp = self.client.get_ltp(self.put_symbol)

        if call_ltp is None or put_ltp is None:
            logging.error("Could not fetch option premiums. Skipping logic.")
            return

        combined_premium = call_ltp + put_ltp
        logging.info(f"Combined Premium: {combined_premium:.2f} (Call: {call_ltp}, Put: {put_ltp})")

        # --- RULE IMPLEMENTATION ---

        # Rule 3 & 4: Entry Logic
        if not self.position_entered:
            if combined_premium < last_vwap:
                logging.info("ENTRY CONDITION MET: Combined premium is below VWAP.")
                logging.info("Selling ATM straddle...")

                self.client.place_order(self.call_symbol, 'S', config.lot_size)
                self.client.place_order(self.put_symbol, 'S', config.lot_size)

                self.position_entered = True
                self.entry_spot_price = self.client.get_nifty_spot_price() # Store for direction check
                logging.info(f"Straddle sold. Entry spot price recorded: {self.entry_spot_price}")
            else:
                logging.info("Entry condition not met. Combined premium is at or above VWAP.")
            return # End logic for this minute

        # If we are in a position, check exit/re-entry rules
        if self.position_entered:
            # Rule 5 & 6: Leg Closing Logic
            if combined_premium > last_vwap and not self.call_leg_closed and not self.put_leg_closed:
                logging.info("CONDITION MET: Combined premium is above VWAP. Closing one leg.")
                current_spot = self.client.get_nifty_spot_price()
                if not current_spot:
                    logging.error("Cannot determine market direction, skipping leg closing.")
                    return

                # Determine market direction
                if current_spot > self.entry_spot_price:
                    logging.info("Market is moving up. Closing CALL leg.")
                    self.client.place_order(self.call_symbol, 'B', config.lot_size)
                    self.call_leg_closed = True
                else:
                    logging.info("Market is moving down. Closing PUT leg.")
                    self.client.place_order(self.put_symbol, 'B', config.lot_size)
                    self.put_leg_closed = True
                return

            # Rule 7: Re-entry Logic
            if combined_premium < last_vwap and (self.call_leg_closed or self.put_leg_closed) and not self.re_entry_done:
                logging.info("CONDITION MET: Combined premium is back below VWAP. Re-entering closed leg.")
                if self.call_leg_closed:
                    logging.info("Re-selling CALL leg.")
                    self.client.place_order(self.call_symbol, 'S', config.lot_size)
                elif self.put_leg_closed:
                    logging.info("Re-selling PUT leg.")
                    self.client.place_order(self.put_symbol, 'S', config.lot_size)

                self.re_entry_done = True # Mark re-entry as used
                return

        logging.info("--- End of Trade Logic ---")


def main():
    """Main function to setup and run the bot."""
    logging.info("--- Starting Trading Bot ---")

    try:
        client = KotakClient()
        client.login()
        if not client.logged_in:
            logging.critical("LOGIN FAILED. BOT CANNOT START.")
            return

        strategy = Strategy(client)

        # Schedule the setup task
        schedule.every().day.at("09:25").do(strategy.setup_for_day)

        # Schedule the main trading logic
        # Rule 1: Entry at 9:30. So we start checking from 9:30.
        for minute in range(30, 60):
            schedule.every().day.at(f"09:{minute}").do(strategy.trade_logic)

        for hour in range(10, 15): # 10 AM to 2 PM
            for minute in range(0, 60):
                schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(strategy.trade_logic)

        # Rule 10: Exit at 3:00 PM
        schedule.every().day.at("15:00").do(client.close_all_positions)

        logging.info("Scheduler setup complete. Waiting for scheduled tasks.")

        # Run initial setup immediately for testing if it's past 9:25 AM
        now = datetime.now().time()
        if now.hour >= 9 and now.minute > 25:
             strategy.setup_for_day()

        while True:
            schedule.run_pending()
            time.sleep(1)

    except Exception as e:
        logging.critical(f"A critical error occurred in the main loop: {e}")

if __name__ == "__main__":
    main()
