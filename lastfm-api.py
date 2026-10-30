import csv
import requests
from dotenv import load_dotenv
import os
import json
import time
from datetime import datetime

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
RATE_LIMIT = 0.7

def convert_2_date(timestamp: str):
    return datetime.strptime(timestamp, "%d %b %Y, %H:%M")

# time duration to compare both users to
# what time/date object can we use for easier comparision here?
START_COMPARISION_SPAN = "01 Mar 2026, 00:00"
END_COMPARISION_SPAN = "27 Oct 2026, 23:59"

parsed_date_start = convert_2_date(START_COMPARISION_SPAN)
parsed_date_end = convert_2_date(END_COMPARISION_SPAN)

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

# The user dataframe we are going to use for vector calculations later; all tracks are expected to be UNIQUE & timestamps are from most recent play -> end of date
user_a_tracks_with_counter = pd.DataFrame(columns=['artist', 'album', 'track', 'timestamps', 'playcount', 'artist_tags', 'album_tags', 'track_tags'])
for q, item in username_b_tracks.iterrows():
    cursor.execute("select Name from TRACK where Name=? and AlbumName=? and ArtistName=?", (item["track"],item["album"],item["artist"],))
    foundTrack = cursor.fetchall()

    if not foundTrack:
        print("did not find track!")
        r = lastfm_get({
            'method': 'track.getTopTags',
            'artist': item["artist"],
            'track': item["track"],
            'user': USER_AGENT
        })
        time.sleep(RATE_LIMIT)
        tag_list = r.json()['toptags']['tag']

        jprint(tag_list)

        hasTags = len(tag_list) > 0

        if hasTags:
            sql = "insert into TRACK (Name, AlbumName, ArtistName, Tags) VALUES (?, ?, ?, ?)"
            cursor.execute(sql, (item["track"], item["album"], item["artist"], str(tag_list)))
            sqliteConnection.commit()
        else:
            cursor.execute("select Name from ALBUM where Name=? and ArtistName=?", (item["album"],item["artist"],)) 
            foundAlbum = cursor.fetchall()
        
            if not foundAlbum:
                print("did not find album!")
                r = lastfm_get({
                    'method': 'album.getTopTags',
                    'artist': item["artist"],
                    'album': item["album"],
                    'user': USER_AGENT
                })
                time.sleep(RATE_LIMIT)
                tag_list = r.json()['toptags']['tag']
                
                jprint(tag_list)
        
                hasTags = len(tag_list) > 0

                if hasTags:
                    sql = "insert into ALBUM (Name, ArtistName, Tags) VALUES (?, ?, ?)"

                    cursor.execute(sql, (item["album"], item["artist"], str(tag_list)))
                    sqliteConnection.commit()
                else:
                    cursor.execute("select Name from ARTIST where Name=?", (item["artist"],))
                    foundArtist = cursor.fetchall()
                
                    if not foundArtist:
                        print("did not find artist!")
                        r = lastfm_get({
                            'method': 'artist.getTopTags',
                            'artist': item["artist"],
                            'user': USER_AGENT
                        })
                        time.sleep(RATE_LIMIT)
                        tag_list = r.json()['toptags']['tag']
                        
                        jprint(tag_list)

                        hasTags = len(tag_list) > 0

                        if hasTags:
                            sql = "insert into ARTIST (Name, Tags) VALUES (?, ?)"
                            
                            cursor.execute(sql, (item["artist"], str(tag_list)))
                            sqliteConnection.commit()
                        else: 
                            print(f"NO tags found for track {item["track"]} on album {item["album"]} by {item["artist"]}")

                    else: 
                        print("found artist in database!")
                        print(foundArtist)
    
            else:
                print("found album in database!")
                print(foundAlbum)

    else:
        print("found track in database!")
        print(foundTrack)

sqliteConnection.commit()
sqliteConnection.close()

# for each track in usera tracks, check if exists in track database based on track name & artist
# if yes:
    # if the last timestamp is smaller than the current timestamp, add the current timestamp to the end of the timestamp list and add one to # of scrobbles
    # print out tags associated with the song
# if no:
    # call lastfm api using track.getTags and append t
    # wait RATE_LIMIT amount of time after API call completes