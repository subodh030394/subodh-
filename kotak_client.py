"""
This module provides a client to interact with the Kotak Neo API.
It simplifies the process of logging in, fetching data, and placing orders.
"""

import logging
import os
from datetime import datetime
import pandas as pd
from neo_api_client import NeoAPI
import config

# Setup logging
logging.basicConfig(level=logging.INFO)

class KotakClient:
    """
    A wrapper for the Kotak Neo API client.
    """
    def __init__(self):
        """
        Initializes the KotakClient, but does not log in.
        """
        self.client = None
        self.logged_in = False

    def login(self):
        """
        Logs into the Kotak Neo API using credentials from the config file.
        """
        logging.info("Logging in...")
        # Note: The user will need to handle the TOTP generation themselves.
        # This script will prompt for it when run.
        try:
            self.client = NeoAPI(
                consumer_key=config.consumer_key,
                consumer_secret=config.consumer_secret,
                environment='prod', # Use 'uat' for testing if available
                neo_fin_key=config.neo_fin_key
            )

            # The login flow requires TOTP, which needs to be entered manually.
            totp = input("Enter the TOTP from your authenticator app: ")
            self.client.totp_login(
                mobile_number=config.mobile_number,
                ucc=config.ucc,
                totp=totp
            )

            # The second step is to validate with the trading password/MPIN
            self.client.totp_validate(config.password)

            self.logged_in = True
            logging.info("Login successful.")
        except Exception as e:
            logging.error(f"Failed to log in: {e}")
            self.logged_in = False
            raise

    def get_nifty_spot_price(self):
        """
        Fetches the current spot price of the NIFTY 50 index.
        """
        logging.info("Fetching NIFTY spot price...")
        try:
            # The instrument token for NIFTY 50 index is '26000' in nse_cm segment
            # We will use this to get the LTP.
            instrument_token = "26000"
            exchange_segment = "nse_cm"

            response = self.client.quotes(instrument_tokens=[{"instrument_token": instrument_token, "exchange_segment": exchange_segment}], quote_type='ltp')

            if response and response.get('data') and response['data'][0].get('ltp'):
                ltp = float(response['data'][0]['ltp'])
                logging.info(f"NIFTY 50 spot price: {ltp}")
                return ltp
            else:
                logging.error(f"Could not fetch NIFTY spot price. Response: {response}")
                return None
        except Exception as e:
            logging.error(f"Error fetching NIFTY spot price: {e}")
            return None

    def get_atm_strike_and_symbols(self, nifty_spot):
        """
        Finds the ATM strike and the corresponding weekly option symbols.
        """
        logging.info("Finding ATM strike and option symbols...")
        try:
            # Download scrip master file if it doesn't exist or is old
            scrip_file = "nse_fo_scrips.csv"
            if not os.path.exists(scrip_file):
                logging.info("Downloading scrip master file for nse_fo...")
                self.client.scrip_master(exchange_segment="nse_fo")
                logging.info("Scrip master downloaded.")

            # Load the scrip master into pandas
            df = pd.read_csv(scrip_file)

            # Filter for NIFTY options
            df = df[df['pSymbol'] == 'NIFTY']

            # Convert expiry date to datetime objects
            df['pExpiryDt'] = pd.to_datetime(df['pExpiryDt'])

            # Find the nearest weekly expiry (typically a Thursday)
            today = datetime.now()
            # Find all future expiries
            future_expiries = df[df['pExpiryDt'] >= today]
            # Get the closest expiry date
            nearest_expiry = future_expiries['pExpiryDt'].min()

            logging.info(f"Nearest expiry date found: {nearest_expiry.date()}")

            # Filter for the nearest expiry
            df = df[df['pExpiryDt'] == nearest_expiry]

            # Calculate the ATM strike
            atm_strike = round(nifty_spot / 50) * 50
            logging.info(f"Calculated ATM strike: {atm_strike}")

            # Find the call and put options for the ATM strike
            atm_call = df[(df['pStrike'] == atm_strike) & (df['pOptType'] == 'CE')]
            atm_put = df[(df['pStrike'] == atm_strike) & (df['pOptType'] == 'PE')]

            if atm_call.empty or atm_put.empty:
                logging.error("Could not find ATM call/put for the calculated strike.")
                return None, None, None

            call_symbol = atm_call.iloc[0]['dSym']
            put_symbol = atm_put.iloc[0]['dSym']

            logging.info(f"Found Call Symbol: {call_symbol}")
            logging.info(f"Found Put Symbol: {put_symbol}")

            return atm_strike, call_symbol, put_symbol

        except Exception as e:
            logging.error(f"Error finding ATM symbols: {e}")
            return None, None, None

    def get_ltp(self, trading_symbol, exchange_segment='nse_fo'):
        """
        Gets the Last Traded Price for a given instrument symbol.
        """
        try:
            # First, we need to find the instrument token for the symbol
            scrip_info = self.client.search_scrip(exchange_segment=exchange_segment, symbol=trading_symbol)

            if not scrip_info or not scrip_info.get('data'):
                logging.error(f"Could not find scrip details for {trading_symbol}")
                return None

            instrument_token = scrip_info['data'][0]['instrument_token']

            # Now fetch the quote using the token
            response = self.client.quotes(instrument_tokens=[{"instrument_token": instrument_token, "exchange_segment": exchange_segment}], quote_type='ltp')

            if response and response.get('data') and response['data'][0].get('ltp'):
                return float(response['data'][0]['ltp'])
            else:
                logging.warning(f"Could not fetch LTP for {trading_symbol}. Response: {response}")
                return None
        except Exception as e:
            logging.error(f"Error fetching LTP for {trading_symbol}: {e}")
            return None

    def place_order(self, trading_symbol, transaction_type, quantity, exchange_segment='nse_fo'):
        """
        Places a market order.
        """
        logging.info(f"Placing order: {transaction_type} {quantity} of {trading_symbol}")
        try:
            response = self.client.place_order(
                exchange_segment=exchange_segment,
                product='MIS',  # Intraday
                order_type='MKT', # Market order
                quantity=str(quantity),
                trading_symbol=trading_symbol,
                transaction_type=transaction_type, # 'B' for Buy, 'S' for Sell
                validity='DAY'
            )
            if response and response.get('data') and response['data'].get('nOrdNo'):
                order_id = response['data']['nOrdNo']
                logging.info(f"Order placed successfully. Order ID: {order_id}")
                return order_id
            else:
                logging.error(f"Failed to place order. Response: {response}")
                return None
        except Exception as e:
            logging.error(f"Exception placing order for {trading_symbol}: {e}")
            return None

    def get_positions(self):
        """
        Retrieves the current open positions.
        """
        try:
            return self.client.positions()
        except Exception as e:
            logging.error(f"Failed to get positions: {e}")
            return None

    def close_all_positions(self):
        """
        Squares off all open MIS positions.
        """
        logging.info("Closing all open MIS positions...")
        try:
            positions = self.get_positions()
            if positions and positions.get('data'):
                for pos in positions['data']:
                    if pos.get('product') == 'MIS' and int(pos.get('net_quantity', 0)) != 0:
                        symbol = pos['trading_symbol']
                        quantity = abs(int(pos['net_quantity']))
                        # If net quantity is positive, we sell to close. If negative, we buy.
                        transaction_type = 'S' if int(pos['net_quantity']) > 0 else 'B'
                        logging.info(f"Closing position for {symbol}...")
                        self.place_order(
                            trading_symbol=symbol,
                            transaction_type=transaction_type,
                            quantity=quantity
                        )
            logging.info("All positions closed.")
        except Exception as e:
            logging.error(f"Failed during closing of positions: {e}")


if __name__ == '__main__':
    # This is for testing the login functionality directly
    try:
        client = KotakClient()
        client.login()
        if client.logged_in:
            print("Successfully connected to Kotak Neo API.")
            # You can test other functions here, e.g., client.client.positions()
            print("Positions:", client.client.positions())
    except Exception as e:
        print(f"An error occurred during testing: {e}")
