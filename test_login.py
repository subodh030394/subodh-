import logging
from kotak_client import KotakClient
import config

# Set up logging to show detailed messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_login():
    """
    A simple script to isolate and test the login functionality.
    """
    logging.info("--- Starting Login Test ---")
    logging.info("This script will attempt to log into the Kotak Neo API.")

    # Remind the user to check their config
    if "YOUR_CONSUMER_KEY" in config.consumer_key:
        logging.warning("Your config.py file seems to have default values.")
        logging.warning("Please fill it with your actual credentials before running.")
        return

    try:
        client = KotakClient()
        client.login()

        if client.logged_in:
            logging.info("--- LOGIN SUCCESSFUL! ---")
            logging.info("Successfully connected to the Kotak Neo API.")
            # Let's try one simple API call to be sure
            positions = client.get_positions()
            logging.info(f"API call 'get_positions' response: {positions}")

    except Exception as e:
        logging.critical("--- LOGIN FAILED ---")
        logging.critical(f"An error occurred during the login process.")
        logging.critical(f"Error Type: {type(e)}")
        logging.critical(f"Error Details: {repr(e)}")
        # If the exception has arguments, print them too
        if hasattr(e, 'args'):
            logging.critical(f"Error Arguments: {e.args}")

if __name__ == "__main__":
    test_login()
