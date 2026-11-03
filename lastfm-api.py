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
RATE_LIMIT = 0.4

def convert_2_date(timestamp: str):
    return datetime.strptime(timestamp, "%d %b %Y, %H:%M")

# time duration to compare both users to
# what time/date object can we use for easier comparision here?
# file end and start:
# date_start_str = "01 Mar 2026, 00:00"
# date_end_str = "27 Oct 2026, 23:59"

date_start_str = "15 Jul 2026, 00:00"
date_end_str = "19 Jul 2026, 23:59"

DATE_START = convert_2_date(date_start_str)
DATE_END = convert_2_date(date_end_str)

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
user_b_tracks_with_counter = pd.DataFrame(columns=['artist', 'album', 'track', 'timestamps', 'playcount', 'artist_tags', 'album_tags', 'track_tags'])

for q, item in username_a_tracks.iterrows():
    gotTrackTags = False
    gotArtistTags = False
    gotAlbumTags = False
    if(type(item["timestamp"]) is not str):
        print(f"this item is wrong: {item}")
        continue

    if convert_2_date(item["timestamp"]) > DATE_START and convert_2_date(item["timestamp"]) < DATE_END:
        cursor.execute("select * from TRACK where Name=? and AlbumName=? and ArtistName=?", (item["track"],item["album"],item["artist"],))
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
                foundTrack = (item["track"], item["album"], item["artist"], str(tag_list))
                gotTrackTags = True
            else:
                sql = "insert into TRACK (Name, AlbumName, ArtistName, Tags) VALUES (?, ?, ?, ?)"
                cursor.execute(sql, (item["track"], item["album"], item["artist"], "na"))
                sqliteConnection.commit()
                
        elif foundTrack[0][3] == "na":
            print("track has already been searched in a previous iteration and has no tags. skippin.")

        else:
            print("found track in database! here are its tags")
            print(foundTrack[0][3])
            gotTrackTags = True

        # look for album tags in 100% of cases
        cursor.execute("select * from ALBUM where Name=? and ArtistName=?", (item["album"],item["artist"],)) 
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
                foundAlbum = (item["track"], item["album"], item["artist"], str(tag_list))
                gotAlbumTags = True
            else:
                sql = "insert into ALBUM (Name, ArtistName, Tags) VALUES (?, ?, ?)"
                cursor.execute(sql, (item["album"], item["artist"], "na"))
                sqliteConnection.commit()

        elif foundAlbum[0][2] == "na":
            print("album has already been searched in a previous iteration and has no tags. skippin.")

        else:
            print("found album in database! tags:")
            print(foundAlbum[0][2])
            gotAlbumTags = True

        # look for artist tags in 100% of cases
        cursor.execute("select * from ARTIST where Name=?", (item["artist"],))
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
                foundArtist = (item["track"], item["album"], item["artist"], str(tag_list))
                gotArtistTags = True
            else:
                sql = "insert into ARTIST (Name, Tags) VALUES (?, ?)"
                cursor.execute(sql, (item["artist"], "na"))
                sqliteConnection.commit()

        elif foundArtist[0][1] == "na":
            print("artist has already been searched in a previous iteration and has no tags. skippin.")

        else: 
            print("found artist in database! tags:")
            print(foundArtist[0][1])
            gotArtistTags = True
    
        if not gotArtistTags and not gotAlbumTags and not gotTrackTags:
            print(f"NO tags found for track {item["track"]} on album {item["album"]} by {item["artist"]}; not adding anything to DF")
        else:
            # if first time in dataframe

            mask = (
            (user_a_tracks_with_counter["artist"] == item["artist"]) &
            (user_a_tracks_with_counter["album"] == item["album"]) &
            (user_a_tracks_with_counter["track"] == item["track"])
        )

        if not mask.any():
            user_a_tracks_with_counter.loc[len(user_a_tracks_with_counter)] = {
                "artist": item["artist"],
                "album": item["album"],
                "track": item["track"],
                "timestamps": [convert_2_date(item["timestamp"])],
                "playcount": 1,
                "artist_tags": [] if not gotArtistTags else foundArtist[0][1],
                "album_tags": [] if not gotAlbumTags else foundAlbum[0][2],
                "track_tags": [] if not gotTrackTags else foundTrack[0][3],
            }
        else:
            user_a_tracks_with_counter.loc[mask, "playcount"] += 1

            new_timestamp = convert_2_date(item["timestamp"])
            user_a_tracks_with_counter.loc[mask, "timestamps"] = (
                user_a_tracks_with_counter.loc[mask, "timestamps"].apply(
                    lambda timestamps: timestamps + [new_timestamp]
                )
            )

        print("-----------------------------")
print(user_a_tracks_with_counter[["artist", "playcount", "timestamps", "artist_tags"]])

import ast
from collections import Counter

tags = user_a_tracks_with_counter["artist_tags"].dropna().apply(
    lambda value: ast.literal_eval(value) if isinstance(value, str) else value
)

counts = Counter(
    tag["name"]
    for row in tags
    for tag in row
    if isinstance(tag, dict) and "name" in tag
)

print(counts.most_common())


sqliteConnection.commit()
sqliteConnection.close()

# for each track in usera tracks, check if exists in track database based on track name & artist
# if yes:
    # if the last timestamp is smaller than the current timestamp, add the current timestamp to the end of the timestamp list and add one to # of scrobbles
    # print out tags associated with the song
# if no:
    # call lastfm api using track.getTags and append t
    # wait RATE_LIMIT amount of time after API call completes