# IMPORTS
import os
import datetime
import json
from urllib.parse import urlencode
import requests
from flask import Flask, request
from google.oauth2 import service_account
import googleapiclient.discovery
import dateutil.relativedelta as relativedelta

app = Flask(__name__)

keyword_phrases = ['!events','!events this week','!maintenance','!maintenance number']

weekday_dictionary = {0:'Monday',
                      1:'Tuesday',
                      2:'Wednesday',
                      3:'Thursday',
                      4:'Friday',
                      5:'Saturday',
                      6:'Sunday'
                      }
inv_weekday_dict = {v: k for k, v in weekday_dictionary.items()}
bot_id = os.getenv('GROUPME_BOT_ID')

@app.route('/', methods=['POST'])
def webhook():
    message = request.get_json()
    msg_txt = message['text'].lower()
    current_date = datetime.date.today()
    current_month = current_date.strftime('%B')
    for text in keyword_phrases:
        if text in msg_txt and not sender_is_bot(message):
            print(text)
            if text == '!events' or text == '!events this week':
                values = get_events_gsheets(current_month)
                indices, date_ranges = get_weeks(values)
                possible_indices = []
                for i,d in enumerate(date_ranges):
                    if compare_dates(current_date,d):
                        current_week = d
                        for j in range(indices[i]+1,indices[i+1]):
                            possible_indices.append(j)
                psbl_dates = possible_dates(current_week)
                current_timeframe_days = [x.day for x in psbl_dates]
                current_timeframe_weekdays = [weekday_dictionary[int(x.weekday())] for x in psbl_dates]
                finalized_dates = []
                data = []
                for i in possible_indices:
                    print(values[i])
                    if len(values[i][2]) is "" or not values:
                        data.append('Nothing scheduled on this date')
                    else:
                        time, loc, title, desc = values[i][2], values[i][3], values[i][4], values[i][5]
                        data.append((time, loc, title,desc))

                    if int(values[i][0]) in current_timeframe_days:
                        j = current_timeframe_days.index(int(values[i][0]))
                        if values[i][1] in [current_timeframe_weekdays[j]]:
                            finalized_dates.append(psbl_dates[j])
                        else:
                            fixed_date = psbl_dates[j] + relativedelta.relativedelta(months=1)
                            if fixed_date.weekday == current_timeframe_weekdays[j]:
                                finalized_dates.append(fixed_date)

                msgs = []

                for date, others in zip(finalized_dates, data):
                    if date < current_date:
                        continue
                    base_msg = "Date: {}".format(date.strftime('%m-%d-%Y'))
                    if others == "Nothing scheduled on this date":
                        msg = base_msg + "\n{}".format(others)
                    else:
                        msg = base_msg + "\nTitle: {}\nTime: {}\nLocation: {}\nDescription: {}\n".format(others[2],others[0],others[1],others[3])

                    msgs.append(msg)

                for msg in msgs:
                    reply(msg,bot_id)

            else:
                base_msg = "Sorry to hear you are having maintenance issues. :(\n{}"
                current_datetime = datetime.datetime.now()
                current_day = current_datetime.weekday()
                maintenace_open = current_datetime.replace(hour=13,minute=0)#these are utc time 8am and 5pm us central tz
                maintenace_close = current_datetime.replace(hour=22,minute=0)
                print(current_datetime,maintenace_open,maintenace_close)
                if current_datetime >= maintenace_open and current_datetime <= maintenace_close and current_day in (0,1,2,3,4):
                    msg = base_msg.format("The maintenance office is currently open. Call the number below to place a maintenance ticket.\nPhone:405-744-8510")
                else:
                    msg = base_msg.format("The maintenance office is currently closed. If you have a flooding, plumbing, A/C emergency call the after hours number below.\nPhone:405-744-7154.")

                reply(msg,bot_id)

    return 'ok'

#METHODS
def reply(msg,bot_id):
    url = "https://api.groupme.com/v3/bots/post"
    data = {
        "bot_id" : bot_id,
        "text": msg
    }
    response = requests.post(url, json=data)

def reply_with_image(msg, imgURL,bot_id):
    url = 'https://api.groupme.com/v3/bots/post'
    data = {
        "bot_id"		: bot_id,
        "text"		    : msg,
        "attachments"	: [{"type": "image", "url":imgURL}]
    }

    response = requests.post(url, json=data)

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
        psbl_dates.append(dates[0]+datetime.timedelta(i))
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
