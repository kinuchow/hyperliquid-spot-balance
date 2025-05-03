#!/usr/bin/env python3
"""
Hyperliquid Spot Balance Tracker
This script fetches the total equity from a Hyperliquid spot account and logs it to a Google Sheet.
"""

import os
import time
import json
import requests
import datetime
import schedule
import gspread
import logging
from oauth2client.service_account import ServiceAccountCredentials

# Import Hyperliquid SDK
from hyperliquid.info import Info
from hyperliquid.utils import constants

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Hyperliquid API endpoints
INFO_API_URL = "https://api.hyperliquid.xyz/info"
EXCHANGE_API_URL = "https://api.hyperliquid.xyz/exchange"

# Initialize Hyperliquid Info client
info_client = Info(constants.MAINNET_API_URL)

# Function to get spot meta data (token information)
def get_spot_meta():
    """
    Fetch the spot metadata including token information.
    
    Returns:
        dict: The spot metadata including token information
    """
    try:
        payload = {
            "type": "spotMeta"
        }
        
        response = requests.post(INFO_API_URL, json=payload)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        return response.json()
    except Exception as e:
        print(f"Error fetching spot metadata: {e}")
        return None

# Function to get token price using the SDK
def get_token_price(symbol):
    """
    Get the current market price for a token using the Hyperliquid SDK.
    
    Args:
        symbol (str): The trading symbol (e.g., "FEUSD/USDC")
        
    Returns:
        float: Current market price
    """
    try:
        # Try to get the price from the order book
        order_book = info_client.l2_snapshot(symbol)
        
        if order_book and isinstance(order_book, dict) and "levels" in order_book:
            levels = order_book["levels"]
            
            if isinstance(levels, list) and len(levels) >= 2:
                # In the list format, first element is bids, second is asks
                bids_data = levels[0]
                asks_data = levels[1]
                
                if bids_data and asks_data:
                    best_bid = float(bids_data[0]["px"])
                    best_ask = float(asks_data[0]["px"])
                    price = (best_bid + best_ask) / 2
                    logger.info(f"Got price for {symbol}: {price}")
                    return price
        
        # If we couldn't get the price from the order book, try allMids
        payload = {"type": "allMids"}
        response = requests.post(INFO_API_URL, json=payload)
        response.raise_for_status()
        
        prices = response.json()
        token_name = symbol.split('/')[0]  # Extract token name from symbol
        
        if token_name in prices:
            price = float(prices[token_name])
            logger.info(f"Got price for {token_name} from allMids: {price}")
            return price
            
        # For stablecoins, default to 1:1 with USDC
        if token_name in ["FEUSD", "USDXL"]:
            logger.info(f"Using default price of 1.0 for stablecoin {token_name}")
            return 1.0
            
        logger.warning(f"Could not find price for {symbol}")
        return None
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        return None

# Function to get token details by token ID
def get_token_details(token_id):
    """
    Fetch details for a specific token by its ID.
    
    Args:
        token_id (str): The token ID in hexadecimal format
        
    Returns:
        dict: Token details including price information
    """
    try:
        payload = {
            "type": "tokenDetails",
            "tokenId": token_id
        }
        
        response = requests.post(INFO_API_URL, json=payload)
        response.raise_for_status()
        
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching token details for {token_id}: {e}")
        return None

# Function to get token prices
def get_token_prices():
    """
    Fetch the current prices of all tokens using the allMids endpoint.
    
    Returns:
        dict: A dictionary mapping token names to their prices in USDC
    """
    try:
        # Get general token prices
        payload = {
            "type": "allMids"
        }
        
        response = requests.post(INFO_API_URL, json=payload)
        response.raise_for_status()
        
        # The response is directly a dictionary of token prices
        prices = response.json()
        
        # Convert string prices to float
        for token, price in prices.items():
            prices[token] = float(price)
        
        # For stablecoins, if we don't have a price, assume 1:1 with USDC
        if "FEUSD" not in prices:
            prices["FEUSD"] = 1.0
            logger.info("Using default price of 1.0 for FEUSD")
        
        if "USDXL" not in prices:
            prices["USDXL"] = 1.0
            logger.info("Using default price of 1.0 for USDXL")
            
        logger.info(f"All token prices: {prices}")
        return prices
    except Exception as e:
        logger.error(f"Error fetching token prices: {e}")
        return {}

# Function to get account equity
def get_hyperliquid_balance(wallet_address):
    """
    Fetch the total equity for a Hyperliquid spot account.
    
    Args:
        wallet_address (str): The wallet address of the Hyperliquid account
        
    Returns:
        float: The total equity value
    """
    try:
        # Get token balances
        balance_payload = {
            "type": "spotClearinghouseState",
            "user": wallet_address
        }
        
        balance_response = requests.post(INFO_API_URL, json=balance_payload)
        balance_response.raise_for_status()
        
        balance_data = balance_response.json()
        logger.info(f"Balance API Response: {balance_data}")
        
        # Get token prices
        prices = get_token_prices()
        logger.info(f"Token Prices: {prices}")
        
        # Calculate total equity
        total_equity = 0.0
        token_values = []
        
        if "balances" in balance_data:
            for balance in balance_data["balances"]:
                token_name = balance["coin"]
                token_amount = float(balance["total"])
                
                if token_name == "USDC":
                    # USDC is the base currency, so its value is 1:1
                    token_value = token_amount
                else:
                    # Try to get price using SDK first for non-USDC tokens
                    token_symbol = f"{token_name}/USDC"
                    sdk_price = get_token_price(token_symbol)
                    
                    if sdk_price is not None:
                        token_value = token_amount * sdk_price
                    elif token_name in prices:
                        # Fall back to allMids endpoint
                        token_value = token_amount * prices[token_name]
                    elif token_name in ["FEUSD", "USDXL"]:
                        # Assume 1:1 for stablecoins if no price available
                        token_value = token_amount
                        logger.info(f"Assuming 1:1 value for stablecoin {token_name}")
                    else:
                        # If we can't find the price, log and skip
                        logger.warning(f"Could not find price for {token_name}")
                        token_value = 0
                
                total_equity += token_value
                token_values.append({"token": token_name, "amount": token_amount, "value": token_value})
                logger.info(f"Token: {token_name}, Amount: {token_amount}, Value in USDC: {token_value}")
            
            # Print a summary of all token values
            logger.info("\nToken Value Summary:")
            for tv in token_values:
                logger.info(f"{tv['token']}: {tv['value']:.2f} USDC")
            logger.info(f"Total Equity: {total_equity:.2f} USDC\n")
            
            return total_equity
        else:
            logger.error(f"No balances found in API response: {balance_data}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching Hyperliquid balance: {e}")
        return None

# Function to update Google Sheet
def update_google_sheet(sheet_id, balance):
    """
    Update a Google Sheet with the current timestamp and balance.
    
    Args:
        sheet_id (str): The ID of the Google Sheet
        balance (float): The account balance to record
    """
    try:
        # Set up the credentials for Google Sheets API
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(credentials)
        
        # Open the spreadsheet and select the first sheet
        sheet = client.open_by_key(sheet_id).sheet1
        
        # Get current timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Append the new row with timestamp and balance
        sheet.append_row([timestamp, balance])
        
        print(f"Successfully updated Google Sheet at {timestamp} with balance: {balance}")
        return True
        
    except Exception as e:
        print(f"Error updating Google Sheet: {e}")
        return False

# Main function to run the job
def run_job():
    """Execute the main job to fetch balance and update Google Sheet."""
    # Load configuration
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            
        wallet_address = config["wallet_address"]
        sheet_id = config["google_sheet_id"]
        
        # Get the balance
        balance = get_hyperliquid_balance(wallet_address)
        
        if balance is not None:
            # Update the Google Sheet
            update_google_sheet(sheet_id, balance)
        else:
            print("Failed to get balance, skipping Google Sheet update.")
            
    except Exception as e:
        print(f"Error in job execution: {e}")

# Schedule the job to run every hour
def start_scheduler():
    """Start the scheduler to run the job hourly."""
    schedule.every(1).hour.do(run_job)
    
    # Run once immediately upon starting
    run_job()
    
    print("Scheduler started. Will fetch Hyperliquid balance and update Google Sheet hourly.")
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(5)  # Check every minute for pending tasks

if __name__ == "__main__":
    start_scheduler()
