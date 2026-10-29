import csv
import requests
from dotenv import load_dotenv
import os
import json
import time

import sqlite3

import pandas as pd

load_dotenv()

USERNAME_A = "devanasson"
USERNAME_B = "fluffyponyy"

API_KEY = os.getenv('KEY')
USER_AGENT = os.getenv('USERNAME')

# CSV files from https://benjaminbenben.com/lastfm-to-csv/

# note: 
# make sure can handle  rus/uk cyrillic/japanese/korean/chinese alphabets

# number of seconds between api calls
RATE_LIMIT = 5

# time duration to compare both users to
# what time/date object can we use for easier comparision here?
START_COMPARISION_SPAN = "01 Mar 2026, 00:00"
END_COMPARISION_SPAN = "27 Oct 2026, 23:59"

def jprint(obj):
    # create a formatted string of the Python JSON object
    text = json.dumps(obj, sort_keys=True, indent=4)
    print(text)

def lastfm_get(payload):
    # define headers and URL
    headers = {'user-agent': USER_AGENT}
    url = 'https://ws.audioscrobbler.com/2.0/'

    # Add API key and format to the payload
    payload['api_key'] = API_KEY
    payload['format'] = 'json'

    print(payload)

    response = requests.get(url, headers=headers, params=payload)
    return response

# get usera track file
username_a_tracks= pd.read_csv(f'{USERNAME_A}.csv')
username_a_tracks.columns = ["artist", "album", "track", "timestamp"]

# get userb track file
username_b_tracks= pd.read_csv(f'{USERNAME_B}.csv')
username_b_tracks.columns = ["artist", "album", "track", "timestamp"]

# connect to sqlite3 database
sqliteConnection = sqlite3.connect('lastfm-tags.db')
cursor = sqliteConnection.cursor()

print(username_a_tracks.head())

for q, item in username_a_tracks.iterrows():
    cursor.execute("select Name from TRACK where Name=?", (item["track"],))
    foundTrack = cursor.fetchall()

    if not foundTrack:
        print("did not find track!")
        r = lastfm_get({
            'method': 'track.getTopTags',
            'artist': item["artist"],
            'track': item["track"],
            # 'album': item["album"],
            'user': USER_AGENT
        })
        jprint(r.json())
        time.sleep(RATE_LIMIT)
    else:
        print("found track!")


# close connection to database

# for each track in usera tracks, check if exists in track database based on track name & artist
# if yes:
    # if the last timestamp is smaller than the current timestamp, add the current timestamp to the end of the timestamp list and add one to # of scrobbles
    # print out tags associated with the song
# if no:
    # call lastfm api using track.getTags and append t
    # wait RATE_LIMIT amount of time after API call completes