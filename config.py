#
# Configuration file for the trading bot
#
# Please fill in your details below.
# Keep this file secure and do not share it.
#

# Kotak Neo API Credentials
# You can get these from the Kotak Securities developer portal
consumer_key = "YOUR_CONSUMER_KEY"
consumer_secret = "YOUR_CONSUMER_SECRET"
neo_fin_key = "YOUR_NEO_FIN_KEY"

# Your Kotak Securities Account Details
ucc = "YOUR_UCC"
mobile_number = "YOUR_MOBILE_NUMBER"
password = "YOUR_LOGIN_PASSWORD" # Or MPIN
lot_size = 15 # Nifty lot size
# Trading Parameters
instrument_name = "NIFTY"
exchange = "NSE"
strike_distance = 100 # Distance from ATM to consider for strikes
weekly_expiry_day = "THURSDAY" # Expiry day for weekly options
exit_time = "15:00" # 3:00 PM
# Add any other configuration variables you need here
