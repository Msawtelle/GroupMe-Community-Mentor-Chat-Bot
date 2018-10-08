# IMPORTS
import os
import datetime
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from flask import Flask, request
from google.oauth2 import service_account
import googleapiclient.discovery
from dateutil import relativedelta

app = Flask(__name__)


possible_text = ['!events', '!events this week']
weekday_dictionary = {0:'Monday',
                      1:'Tuesday',
                      2:'Wednesday',
                      3:'Thursday',
                      4:'Friday',
                      5:'Saturday',
                      6:'Sunday'
                  }

inv_weekday_dict = {v: k for k, v in weekday_dictionary.items()}
# Called whenever the app's callback URL receives a POST request
# That'll happen every time a message is sent in the group
@app.route('/', methods=['POST'])
def webhook():

    # 'message' is an object that represents a single GroupMe message.
    message = request.get_json()
    msg_txt = message['text'].lower()
    current_date = datetime.date.today()
    current_month = current_date.strftime('%B')
    for text in possible_text:
        if text in msg_txt and not sender_is_bot(message):
            if text == '!events' or '!events this week':
                values = get_events_gsheets(current_month)
                indices, date_ranges = get_weeks(values)
                possible_indices = []
                for i,d in enumerate(date_ranges):
                    if compare_dates(current_date,d):
                        current_week = d
                        for j in range(indices[i]+1,indices[i+1]):
                            possible_indices.append(j)
                psbl_dates = possible_dates(current_week)
                for x in psbl_dates:
                    print(x,type(x))
                current_timeframe_days = [x.day for x in psbl_dates]
                current_timeframe_weekdays = [weekday_dictionary[int(x.weekday())] for x in psbl_dates]
                finalized_dates = []
                data = []
                for i in possible_indices:
                    if len(values[i]) <= 2 or not values:
                        data.append('Nothing scheduled on this date')
                    else:
                        time, title, loc, desc = values[i][2], values[i][3], values[i][4], values[i][5]
                        data.append((time, title, loc, desc))

                    if int(values[i][0]) in current_timeframe_days:
                        j = current_timeframe_days.index(int(values[i][0]))
                        if values[i][1] == inv_weekday_dict[current_timeframe_weekdays[j]]:
                            finalized_dates.append(psbl_dates[j])
                        else:
                            fixed_date = psbl_dates[j] + relativedelta(months=1)
                            if fixed_date.weekday == current_timeframe_weekdays[j]:
                                finalized_dates.append(fixed_date)
                msgs = []
                for date, others in zip(finalized_dates, data):
                    base_msg = 'Date: {}'.format(date)
                    if others == 'Nothing scheduled on this date':
                        msg = base_msg + '\n{}'.format(others)
                    else:
                        msg = base_msg + '\nTitle: {}\nTime: {}\nLocation: {}\nDescription: {}'.format(others[1],
                                                                                                             others[0],
                                                                                                             others[2],
                                                                                                             others[3])
                    msgs.append(msg)
                final_msg = '\n'.join(msgs)
                bot_id = os.getenv('GROUPME_BOT_ID')
                reply(final_msg,bot_id)
    return "ok", 200
#methods used
# Send a message in the groupchat
def reply(msg,bot_id):
    url = 'https://api.groupme.com/v3/bots/post'
    data = {
        'bot_id'		: bot_id,
        'text'			: msg
    }
    request = Request(url, urlencode(data).encode())
    json = urlopen(request).read().decode()

# Send a message with an image attached in the groupchat
def reply_with_image(msg, imgURL,bot_id):
    url = 'https://api.groupme.com/v3/bots/post'
    data = {
        'bot_id'		: bot_id,
        'text'			: msg,
        'attachments'	: [{"type": "image", "url":imgURL}]
    }
    request = Request(url, urlencode(data).encode())
    json = urlopen(request).read().decode()

# Checks whether the message sender is a bot
def sender_is_bot(message):
    return message['sender_type'] == "bot"

def get_events_gsheets(current_month):
    SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
    SCOPE = ['https://www.googleapis.com/auth/spreadsheets.readonly','https://www.googleapis.com/auth/drive.readonly']
    google_sheets = get_service()
    range = '{}!A1:F60'.format(current_month)
    response = google_sheets.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID,range=range).execute()
    return response['values']

def get_weeks(values):
    indices = []
    date_ranges = []
    for i, row in enumerate(values):
        if row[0].startswith('Week of'):
            indices.append(i)
            date_ranges.append(parse_weeks(row[0]))
    return indices, date_ranges

def parse_weeks(row):
    text = row.split()
    if text[2] in ['September','October','November','December']:
        year = 2018
    else:
        year = 2019
    if len(text) == 7:
        d1_string = '{}-{}-{}'.format(year,text[2],text[3])
        d2_string = '{}-{}-{}'.format(year,text[5],text[6])
        d1 = datetime.datetime.strptime(d1_string,'%Y-%B-%d').date()
        d2 = datetime.datetime.strptime(d2_string,'%Y-%B-%d').date()
    elif len(text) == 6:
        d1_string = '{}-{}-{}'.format(year,text[2],text[3])
        d2_string = '{}-{}-{}'.format(year,text[2],text[5])
        d1 = datetime.datetime.strptime(d1_string,'%Y-%B-%d').date()
        d2 = datetime.datetime.strptime(d2_string,'%Y-%B-%d').date()
    return (d1, d2)

def possible_dates(dates):
    psbl_dates = []
    delta = dates[1]-dates[0]
    for i in range(delta.days+1):
        psbl_dates.append((dates[0]+datetime.timedelta(i)).date())
    return psbl_dates

def compare_dates(date_to_compare,date_tuple):
    if date_tuple[0] <= date_to_compare <= date_tuple[1]:
        return True
    else:
        return False
def get_credentials():
    account_info = json.loads(os.getenv('GOOGLE_ACCOUNT_CREDENTIALS'))
    SCOPE = ['https://www.googleapis.com/auth/spreadsheets.readonly','https://www.googleapis.com/auth/drive.readonly']
    credentials = service_account.Credentials.from_service_account_info(account_info, scopes=SCOPE)
    return credentials
def get_service(service_name='sheets', api_version='v4'):
    credentials = get_credentials()
    service = googleapiclient.discovery.build(service_name, api_version, credentials=credentials)
    return service
