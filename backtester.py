import logging
import pandas as pd
from strategy_logic import Strategy # Import the same strategy logic
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MockClient:
    """
    A mock client that simulates the broker. Instead of making API calls,
    it reads data from the historical data file for the current timestep.
    """
    def __init__(self):
        self.current_row = None

    def set_current_data(self, row):
        """Sets the market data for the current minute."""
        self.current_row = row

    def get_nifty_spot_price(self):
        """Returns the NIFTY spot price from the current data row."""
        return self.current_row['nifty_spot']

    def get_atm_strike_and_symbols(self, nifty_spot):
        """Returns the option symbols from the current data row."""
        # In a backtest, this is pre-calculated and part of the data
        return (self.current_row['atm_strike'],
                self.current_row['call_symbol'],
                self.current_row['put_symbol'])

    def get_ltp(self, trading_symbol, **kwargs):
        """Returns the LTP for a symbol from the current data row."""
        if trading_symbol == self.current_row['call_symbol']:
            return self.current_row['call_ltp']
        elif trading_symbol == self.current_row['put_symbol']:
            return self.current_row['put_ltp']
        return None

    def place_order(self, trading_symbol, transaction_type, quantity):
        """Simulates placing an order and returns the fill price."""
        # For simplicity, we assume the order is filled at the current LTP
        price = self.get_ltp(trading_symbol)
        logging.info(f"[SIMULATED ORDER] {transaction_type} {quantity} of {trading_symbol} at {price}")
        return price # Return the price for P&L calculation

class Backtester:
    """
    The main backtesting engine.
    """
    def __init__(self, data_path):
        self.data = pd.read_csv(data_path, parse_dates=['datetime'])
        self.mock_client = MockClient()
        # The strategy now uses the mock client
        self.strategy = Strategy(self.mock_client)
        self.pnl = 0.0
        self.trades = []

    def run(self):
        logging.info("--- Starting Backtest ---")

        # The main event loop: iterate through each row of the data file
        for index, row in self.data.iterrows():
            # Update the mock client with the data for this minute
            self.mock_client.set_current_data(row)

            # --- Simulate the passage of time and daily setup ---
            current_time = row['datetime'].time()

            # Simulate daily setup at 9:25 AM
            if current_time == pd.to_datetime("09:25:00").time():
                # In backtesting, we just need to set the symbols for the day
                self.strategy.atm_strike = row['atm_strike']
                self.strategy.call_symbol = row['call_symbol']
                self.strategy.put_symbol = row['put_symbol']
                logging.info(f"Backtest day setup for {row['datetime'].date()}")

            # Skip logic before 9:30 AM or after 3:00 PM
            if not (pd.to_datetime("09:30:00").time() <= current_time < pd.to_datetime("15:00:00").time()):
                continue

            # --- Run the actual strategy logic ---
            # We need to temporarily override the place_order method to capture P&L
            original_place_order = self.mock_client.place_order
            self.mock_client.place_order = self.handle_trade

            self.strategy.nifty_data = pd.DataFrame([row.rename({'nifty_vwap': 'VWAP_D'})]) # Mock the nifty_data df
            self.strategy.trade_logic()

            # Restore original method
            self.mock_client.place_order = original_place_order

            # Simulate squaring off at the end of the day
            if current_time == pd.to_datetime("14:59:00").time():
                self.square_off_positions()

        logging.info("--- Backtest Finished ---")
        self.print_results()

    def handle_trade(self, trading_symbol, transaction_type, quantity):
        """Wrapper around the mock order to calculate P&L."""
        price = self.mock_client.get_ltp(trading_symbol)
        if price is None: return

        trade_pnl = 0
        if transaction_type == 'S':
            trade_pnl = price * quantity
        elif transaction_type == 'B':
            trade_pnl = -price * quantity

        self.pnl += trade_pnl
        self.trades.append({
            "symbol": trading_symbol,
            "type": transaction_type,
            "price": price,
            "pnl": trade_pnl
        })
        logging.info(f"Trade P&L: {trade_pnl:.2f}, Cumulative P&L: {self.pnl:.2f}")

    def square_off_positions(self):
        # A simple square off logic for backtesting
        # This part can be made more sophisticated
        logging.info("Simulating end-of-day square off.")
        # In a real backtester, you'd track open positions and close them here.
        # For this straddle, we can assume all open legs are closed.
        # This is a simplification; a full implementation would track each leg.
        pass

    def print_results(self):
        logging.info("--- Backtest Results ---")
        logging.info(f"Total Trades: {len(self.trades)}")
        logging.info(f"Final P&L: {self.pnl * config.lot_size:.2f}") # Assuming 1 lot

if __name__ == "__main__":
    # The user needs to provide the path to their data file
    DATA_FILE_PATH = 'data.csv'

    backtester = Backtester(DATA_FILE_PATH)
    backtester.run()
