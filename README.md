# Hyperliquid Spot Balance Tracker

This script fetches your Hyperliquid spot account total equity every hour and imports it to a Google Sheet with timestamp and balance information.

## Setup Instructions

### 1. Install Required Dependencies

```bash
pip install requests schedule gspread oauth2client
```

### 2. Set Up Google Sheets API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Google Sheets API and Google Drive API
4. Create a service account and download the JSON credentials file
5. Rename the downloaded file to `credentials.json` and place it in the same directory as this script
6. Create a new Google Sheet and share it with the email address from your service account (with Editor permissions)
7. Copy the Google Sheet ID from the URL (the long string between `/d/` and `/edit` in the URL)

### 3. Configure the Script

Edit the `config.json` file and update:
- `wallet_address`: Your Hyperliquid wallet address
- `google_sheet_id`: The ID of your Google Sheet

### 4. Run the Script

```bash
python hyperliquid_balance_tracker.py
```

The script will:
- Immediately fetch your current balance and add it to the sheet
- Continue running and update the sheet every hour

## Google Sheet Format

The script will automatically add rows to your Google Sheet with:
- Column A: Timestamp (YYYY-MM-DD HH:MM:SS)
- Column B: Total Equity Value

You may want to add headers to your sheet manually before running the script.
