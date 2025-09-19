import logging
import time
from datetime import datetime
import schedule
from kotak_client import KotakClient
from strategy_logic import Strategy # Import the class from the new file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info("--- Starting Live Trading Bot ---")
    try:
        client = KotakClient()
        client.login()
        if not client.logged_in: return

        strategy = Strategy(client)
        schedule.every().day.at("09:25").do(strategy.setup_for_day)
        schedule.every().day.at("15:00").do(client.close_all_positions)

        # Schedule the trading logic to run every minute during market hours
        for minute in range(30, 60): schedule.every().day.at(f"09:{minute}").do(strategy.trade_logic)
        for hour in range(10, 15):
            for minute in range(0, 60): schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(strategy.trade_logic)

        logging.info("Scheduler setup complete. Waiting for market hours.")

        # Run setup immediately if it's already past the setup time
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
