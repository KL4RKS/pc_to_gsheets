###########################
# 
# Personal Capital to Google Sheets
# Ben Hummel, 2020
# 
###########################

from __future__ import print_function
from personalcapital import PersonalCapital, RequireTwoFactorException, TwoFactorVerificationModeEnum
from datetime import date, datetime, timedelta
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import logging
import os
import pickle
import json
import getpass


# Edit these before running #############

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# For info on these variables: 
# https://developers.google.com/sheets/api/guides/concepts
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
SUMMARY_SHEET_NAME = os.getenv('SUMMARY_SHEET_NAME') # 'wall_chart'
TRANSACTIONS_SHEET_NAME = os.getenv('TRANSACTIONS_SHEET_NAME') # 'transactions'
ACCOUNTS_SHEET_NAME = os.getenv('ACCOUNTS_SHEET_NAME') # 'accounts'
SESSION_FILENAME = 'pc.pickle'

TRANSACTIONS_START_DATE = '2013-04-01' # YYYY-MM-DD
# TRANSACTIONS_END_DATE = (datetime.now() - (timedelta(days=1))).strftime('%Y-%m-%d')
TRANSACTIONS_END_DATE = datetime.now().strftime('%Y-%m-%d')

#########################################

def get_email():
	email = os.getenv('PEW_EMAIL')
	if not email:
		print('You can set the environment variables for PEW_EMAIL and PEW_PASSWORD so the prompts don\'t come up every time')
		return input('Enter email:')
	return email

def get_password():
	password = os.getenv('PEW_PASSWORD')
	if not password:
		return getpass.getpass('Enter password:')
	return password

def convert_datetime(timestamp,format):
	if isinstance(timestamp, (int, float)):
		if len(str(timestamp)) == 13:
			timestamp = timestamp/1000

		if len(str(round(timestamp))) == 10:
			# Convert to a datetime object
			dt_object = datetime.utcfromtimestamp(timestamp)

			# Format the datetime object as yyyy-mm-dd
			if format == 'timestamp':
				formatted_datetime = dt_object.strftime('%Y-%m-%d %H:%M:%S')
			else:
				formatted_datetime = dt_object.strftime('%Y-%m-%d')

			return(formatted_datetime)
	return(timestamp)
	
def import_pc_data():
	email, password = get_email(), get_password()
	pc = PersonalCapital()
	try:
		pc.load_session(SESSION_FILENAME)
	except:
		print('Unable to load session. Session file not found: ' + SESSION_FILENAME)

	try:
		pc.login(email, password)
	except RequireTwoFactorException:
		pc.two_factor_challenge(TwoFactorVerificationModeEnum.SMS)
		pc.two_factor_authenticate(TwoFactorVerificationModeEnum.SMS, input('Enter 2-factor code: '))
		pc.authenticate_password(password)

	accounts_response = pc.fetch('/newaccount/getAccounts')
	
	transactions_response = pc.fetch('/transaction/getUserTransactions', {
		'sort_cols': 'transactionTime',
		'sort_rev': 'true',
		'page': '0',
		'rows_per_page': '100',
		'startDate': TRANSACTIONS_START_DATE,
		'endDate': TRANSACTIONS_END_DATE,
		'component': 'DATAGRID'
	})
	pc.save_session(SESSION_FILENAME)
	accounts = accounts_response.json()['spData']
	total_accounts = len(accounts['accounts']) # count number of accounts
	print(f'Number of accounts: {total_accounts}')
	networth = accounts['networth']
	print(f'Networth: {networth}')

	transactions = transactions_response.json()['spData']
	total_transactions = len(transactions['transactions'])
	print(f'Number of transactions between {TRANSACTIONS_START_DATE} and {TRANSACTIONS_END_DATE}: {total_transactions}')

	with open('accounts.json', 'w') as data_file:
		data_file.write(json.dumps(accounts))
	with open('transactions.json', 'w') as data_file:
		data_file.write(json.dumps(transactions))

	summary = {}

	for key in accounts.keys():
		if key == 'networth' or key == 'investmentAccountsTotal':
			summary[key] = accounts[key]

	transactions_output = []  # a list of dicts
	for this_transaction in transactions['transactions']:
		this_transaction_filtered = {
			'transactionId': this_transaction.get('userTransactionId', ''),
			'date': this_transaction.get('transactionDate', ''),
			'account': this_transaction.get('accountName', ''),
			'description': this_transaction.get('description', ''),
			'category': this_transaction.get('categoryId', ''),
			'categoryDesc': this_transaction.get('categoryName', ''),
			'tags': '',
			'amount': this_transaction.get('amount', ''),  # always a positive int
			'isIncome': this_transaction.get('isIncome', ''),
			'isSpending': this_transaction.get('isSpending', ''),
			'isCredit': this_transaction.get('isCredit', ''),  # to determine whether `amount` should be positive or negative
			'status': this_transaction.get('status', ''),
		}
		transactions_output.append(this_transaction_filtered)

	accounts_output = []  # a list of dicts
	for this_account in accounts['accounts']:
		this_account_filtered = {
			'accountId': this_account.get('userAccountId'),
			'originalFirmName': this_account.get('originalFirmName'), 
			'firmName': this_account.get('firmName'),
			'originalName': this_account.get('originalName'),
			'accountName': this_account.get('name'),
			'productType': this_account.get('productType'),
			'balance': this_account.get('balance'), # always a positive int
			'createdDate': convert_datetime(this_account.get('createdDate'),'date'), # needs conversion
			'lastRefreshed': convert_datetime(this_account.get('lastRefreshed'),'timestamp'), # needs conversion
			'oldestTransactionDate': this_account.get('oldestTransactionDate'),
			'closedDate': this_account.get('closedDate'),
			'isAsset': this_account.get('isAsset'),
			'isLiability': this_account.get('isLiability'),
		}
		accounts_output.append(this_account_filtered)

	out = [summary, transactions_output, accounts_output]
	return out

def reshape_transactions(transactions):
	# returns a list of lists, where each sub-list is just the transaction values
	eventual_output = []
	for i in transactions:
		this_transaction_list = []
		for key in i.keys():
			this_transaction_list.append(i[key])
		eventual_output.append(this_transaction_list)
	return eventual_output

def main():
	# Check Google credentials
	google_creds = None
	if os.path.exists('token.pickle'):
		with open('token.pickle', 'rb') as token:
			google_creds = pickle.load(token)
	if not google_creds or not google_creds.valid:
		if google_creds and google_creds.expired and google_creds.refresh_token:
			google_creds.refresh(Request())
		else:
			flow = InstalledAppFlow.from_client_secrets_file(
				'credentials.json', SCOPES)
			google_creds = flow.run_local_server(port=0)
		with open('token.pickle', 'wb') as token:
			pickle.dump(google_creds, token)
	service = build('sheets', 'v4', credentials=google_creds)


	# download PC data
	pc_data = import_pc_data()
	summary_data = pc_data[0]
	transaction_data = pc_data[1]
	account_data = pc_data[2]
	
	networth = summary_data['networth']
	investments = summary_data['investmentAccountsTotal']

	# reshape transaction data
	eventual_output = reshape_transactions(transaction_data)

	# reshape account data
	eventual_output_accounts = reshape_transactions(account_data)

	# read sheet to make sure we have data
	sheet = service.spreadsheets()
	range = SUMMARY_SHEET_NAME + '!A:C'
	result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
								range=range).execute()
	values = result.get('values', [])

	max_row = len(values)
	print(f'{max_row} rows retrieved from Summary sheet.')

	current_date = datetime.now()
	current_month = current_date.strftime("%B") # e.g. "August"
	current_year = str(current_date.strftime("%Y")) # e.g. "2020"

	def checkForThisMonthRow(values):
		max_date_in_spreadsheet = values[max_row-1][0]
		max_month_in_spreadsheet = max_date_in_spreadsheet.split(' ')[0]
		print(f"here's the max date we have:  {max_date_in_spreadsheet}")
		
		is_current_month_already_present = current_month == max_month_in_spreadsheet
		return is_current_month_already_present

	if checkForThisMonthRow(values):
		# select the last row
		print("we already have a row for this month, so we'll just overwrite the values")
		summary_sheet_range =  SUMMARY_SHEET_NAME + '!A' + str(max_row) + ':C' + str(max_row)

	else:
		# insert a new row at the bottom for the current month
		print("we need to insert a new row for this month")

		summary_sheet_range = SUMMARY_SHEET_NAME + '!A' + str(max_row+1) + ':C' + str(max_row+1)


	if not values:
		print('No data retreived from Personal Capital.')
	else:
		# upload summary data
		print("Uploading summary data...")
		summary_body = {
			"values": [
				[
					current_month + ' ' + current_year,
					networth,
					investments
				]
			],
			"majorDimension": "ROWS"
		}
		result = service.spreadsheets().values().update(
			spreadsheetId=SPREADSHEET_ID, range=summary_sheet_range,
			valueInputOption='USER_ENTERED', body=summary_body).execute()
		print(result)


		# upload transactions data
		transactions_range = '!A2:L'
		transactions_sheet_range = TRANSACTIONS_SHEET_NAME + transactions_range

		print("uploading transactions...")
		transactions_body = {
			"values": eventual_output,
			"majorDimension": "ROWS"
		}
		result = service.spreadsheets().values().update(
			spreadsheetId=SPREADSHEET_ID, range=transactions_sheet_range,
			valueInputOption='USER_ENTERED', body=transactions_body).execute()
		print(result)

		# upload accounts data
		accounts_range = '!A2:M'
		accounts_sheet_range = ACCOUNTS_SHEET_NAME + accounts_range

		print("uploading accounts...")
		accounts_body = {
			"values": eventual_output_accounts,
			"majorDimension": "ROWS"
		}
		result = service.spreadsheets().values().update(
			spreadsheetId=SPREADSHEET_ID, range=accounts_sheet_range,
			valueInputOption='USER_ENTERED', body=accounts_body).execute()
		print(result)
		
		output = ""
		if result:
			output = "Success!"
		else:
			output = "Not sure if that worked."
		return output 

if __name__ == '__main__':
	main()