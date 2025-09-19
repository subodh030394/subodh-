import logging
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import config
from datetime import datetime

class Strategy:
    def __init__(self, client):
        self.client = client
        self.nifty_data = pd.DataFrame()
        self.atm_strike = None
        self.call_symbol = None
        self.put_symbol = None
        self.entry_spot_price = None
        self.position_entered = False
        self.call_leg_closed = False
        self.put_leg_closed = False
        self.re_entry_done = False

    def fetch_nifty_data(self):
        logging.info("Fetching NIFTY 50 1-minute data...")
        try:
            self.nifty_data = yf.download(tickers="^NSEI", period="1d", interval="1m")
            if self.nifty_data.empty:
                raise ValueError("yfinance returned empty dataframe for NIFTY.")
            self.nifty_data.ta.vwap(append=True)
            logging.info("Successfully fetched NIFTY data and calculated VWAP.")
            return True
        except Exception as e:
            logging.error(f"Exception while fetching NIFTY data: {e}")
            return False

    def setup_for_day(self):
        logging.info("Performing daily setup...")
        if not self.fetch_nifty_data(): return
        spot_price = self.client.get_nifty_spot_price()
        if not spot_price: return
        self.atm_strike, self.call_symbol, self.put_symbol = self.client.get_atm_strike_and_symbols(spot_price)
        if not self.atm_strike: return
        logging.info("Daily setup complete. Ready to trade.")

    def trade_logic(self):
        logging.info("--- Running Trade Logic ---")
        if self.nifty_data.empty or self.call_symbol is None:
            logging.warning("Strategy not ready. Skipping logic.")
            return

        last_vwap = self.nifty_data['VWAP_D'].iloc[-1]
        call_ltp = self.client.get_ltp(self.call_symbol)
        put_ltp = self.client.get_ltp(self.put_symbol)
        if call_ltp is None or put_ltp is None: return

        combined_premium = call_ltp + put_ltp
        logging.info(f"VWAP: {last_vwap:.2f}, Premium: {combined_premium:.2f}")

        if not self.position_entered:
            if combined_premium < last_vwap:
                logging.info("ENTRY: Premium < VWAP. Selling straddle.")
                self.client.place_order(self.call_symbol, 'S', config.lot_size)
                self.client.place_order(self.put_symbol, 'S', config.lot_size)
                self.position_entered = True
                self.entry_spot_price = self.client.get_nifty_spot_price()
            return

        current_spot = self.client.get_nifty_spot_price()
        if not current_spot: return

        if combined_premium > last_vwap and not self.call_leg_closed and not self.put_leg_closed:
            if current_spot > self.entry_spot_price:
                logging.info("EXIT: Premium > VWAP, market up. Closing CALL.")
                self.client.place_order(self.call_symbol, 'B', config.lot_size)
                self.call_leg_closed = True
            else:
                logging.info("EXIT: Premium > VWAP, market down. Closing PUT.")
                self.client.place_order(self.put_symbol, 'B', config.lot_size)
                self.put_leg_closed = True
        elif combined_premium < last_vwap and (self.call_leg_closed or self.put_leg_closed) and not self.re_entry_done:
            if self.call_leg_closed:
                logging.info("RE-ENTRY: Premium < VWAP. Re-selling CALL.")
                self.client.place_order(self.call_symbol, 'S', config.lot_size)
            else: # put_leg_closed
                logging.info("RE-ENTRY: Premium < VWAP. Re-selling PUT.")
                self.client.place_order(self.put_symbol, 'S', config.lot_size)
            self.re_entry_done = True
