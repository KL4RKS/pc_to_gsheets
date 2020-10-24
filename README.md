# Overview
This script imports data from Personal Capital (personalcapital.com) and exports various components to a Google Sheet. The use case is if you want to regularly take your financial data to a spreadsheet and run additional analytics.

Right now it's hard coded with names of sheets that I'm using. Be sure to change these to your own where indicated. 

Here's an example of what the schema of the Google Sheet should look like:

https://docs.google.com/spreadsheets/d/1DI5oupu-RlZCCzAR023vCgoXkoo_BYU8DmtGTGvExBk/edit#gid=1923416251


# Setup

## Set up environment variables
```
$ export PEW_EMAIL="<your_personal_capital_email>"
$ export PEW_PASSWORD="<your_personal_capital_password>"
```

## Authorize GSheets access
Follow instructions here:
https://developers.google.com/sheets/api/quickstart/python?authuser=1

## Install packages
Preferably in a virtualenv:
```
$ pip install personalcapital
$ pip install requests
$ pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

## Run `main.py`

Expected outcome: 
- The `SUMMARY_SHEET_NAME` sheet in Google Sheets will either have the bottom row overwritten with current data, or a new row created if it's not the current month. e.g. if it's currently October and the last row is September, we create a new row.
- The `TRANSACTIONS_SHEET_NAME` sheet in Google Sheets will be completely overwritten with up-to-date values