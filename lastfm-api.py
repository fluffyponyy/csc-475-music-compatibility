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
RATE_LIMIT = 0.2

def convert_2_date(timestamp: str):
    return datetime.strptime(timestamp, "%d %b %Y, %H:%M")

# time duration to compare both users to
# what time/date object can we use for easier comparision here?
# file end and start:
# date_start_str = "01 Mar 2026, 00:00"
# date_end_str = "27 Oct 2026, 23:59"

date_start_str = "01 Jul 2026, 00:00"
date_end_str = "27 Oct 2026, 23:59"

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


def create_user_dataframe(user_tracks, user_dataframe, user):

    for q, item in user_tracks.iterrows():
        gotTrackTags = False
        gotArtistTags = False
        gotAlbumTags = False

        if(type(item["timestamp"]) is not str):
            # print(f"this item is wrong: {item}")
            continue

        
        # print(item["timestamp"])

        if convert_2_date(item["timestamp"]) > DATE_START and convert_2_date(item["timestamp"]) < DATE_END:
            cursor.execute("select * from TRACK where Name=? and AlbumName=? and ArtistName=?", (item["track"],item["album"],item["artist"],))
            foundTrack = cursor.fetchall()

            if not foundTrack:
                #print("did not find track!")
                r = lastfm_get({
                    'method': 'track.getTopTags',
                    'artist': item["artist"],
                    'track': item["track"],
                    'user': USER_AGENT
                })
                time.sleep(RATE_LIMIT)

                if "message" in r.json() and r.json()['message'] ==  "Track not found": 
                    print(f"did not find track on album {item["album"]}  by {item["artist"]}; skipping track {item["track"]} entirely")
                    continue

                tag_list = r.json()['toptags']['tag']

                # jprint(tag_list)

                hasTags = len(tag_list) > 0

                if hasTags:
                    sql = "insert into TRACK (Name, AlbumName, ArtistName, Tags) VALUES (?, ?, ?, ?)"
                    cursor.execute(sql, (item["track"], item["album"], item["artist"], str(tag_list)))
                    sqliteConnection.commit()
                    foundTrack = (item["track"], item["album"], item["artist"], str(tag_list))
                    gotTrackTags = True
                else:
                    if (item["album"] != item["album"]): item["album"] = "na"
                    sql = "insert into TRACK (Name, AlbumName, ArtistName, Tags) VALUES (?, ?, ?, ?)"
                    cursor.execute(sql, (item["track"], item["album"], item["artist"], "na"))
                    sqliteConnection.commit()
                    
            elif foundTrack[0][3] == "na":
                #print("track has already been searched in a previous iteration and has no tags. skippin.")
                gotTrackTags = False #do not change val

            else:
                #print("found track in database! here are its tags")
                # print(foundTrack[0][3])
                gotTrackTags = True

            # look for album tags in 100% of cases
            cursor.execute("select * from ALBUM where Name=? and ArtistName=?", (item["album"],item["artist"],)) 
            foundAlbum = cursor.fetchall()

            if not foundAlbum:
                # print("did not find album!")
                r = lastfm_get({
                    'method': 'album.getTopTags',
                    'artist': item["artist"],
                    'album': item["album"],
                    'user': USER_AGENT
                })
                time.sleep(RATE_LIMIT)
                if "message" in r.json() and r.json()['message'] ==  "Album not found": 
                    print(f"did not find album {item["album"]}  by {item["artist"]}; skipping track {item["track"]} entirely")
                    continue
                tag_list = r.json()['toptags']['tag']
                
                # jprint(tag_list)

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
                # print("album has already been searched in a previous iteration and has no tags. skippin.")
                gotAlbumTags = False # do not change

            else:
                # print("found album in database! tags:")
                # print(foundAlbum[0][2])
                gotAlbumTags = True

            # look for artist tags in 100% of cases
            cursor.execute("select * from ARTIST where Name=?", (item["artist"],))
            foundArtist = cursor.fetchall()
            
            if not foundArtist:
                # print("did not find artist!")
                r = lastfm_get({
                    'method': 'artist.getTopTags',
                    'artist': item["artist"],
                    'user': USER_AGENT
                })
                time.sleep(RATE_LIMIT)
                tag_list = r.json()['toptags']['tag']
                
                # jprint(tag_list)

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
                # print("artist has already been searched in a previous iteration and has no tags. skippin.")
                gotTrackTags = False

            else: 
                # print("found artist in database! tags:")
                # print(foundArtist[0][1])
                gotArtistTags = True
        
            if gotArtistTags or gotAlbumTags or gotTrackTags:
                #print(f"NO tags found for track {item["track"]} on album {item["album"]} by {item["artist"]}; not adding anything to DF")
                # if first time in dataframe

                mask = (
                (user_dataframe["artist"] == item["artist"]) &
                (user_dataframe["album"] == item["album"]) &
                (user_dataframe["track"] == item["track"])
            )

            if not mask.any():
                user_dataframe.loc[len(user_dataframe)] = {
                    "artist": item["artist"],
                    "album": item["album"],
                    "track": item["track"],
                    "timestamps": [convert_2_date(item["timestamp"])],
                    "playcount": 1,
                    "artist_tags": [] if not gotArtistTags or len(foundArtist[0]) < 2 else foundArtist[0][1],
                    "album_tags": [] if not gotAlbumTags or len(foundAlbum[0]) < 3 else foundAlbum[0][2],
                    "track_tags": [] if not gotTrackTags or len(foundTrack[0]) < 4 else foundTrack[0][3],
                }
            else:
                user_dataframe.loc[mask, "playcount"] += 1

                new_timestamp = convert_2_date(item["timestamp"])
                user_dataframe.loc[mask, "timestamps"] = (
                    user_dataframe.loc[mask, "timestamps"].apply(
                        lambda timestamps: timestamps + [new_timestamp]
                    )
                )
    user_dataframe.to_csv(f'{user}-dataframe-{DATE_START}-{DATE_END}.csv'.replace(" ", "").replace(":", "_"), index=False)



create_user_dataframe(username_a_tracks, user_a_tracks_with_counter, USERNAME_A)
create_user_dataframe(username_b_tracks, user_b_tracks_with_counter, USERNAME_B)



import ast
from collections import Counter


def get_top_tags(user_dataframe, tag_column_name):
    tags = user_dataframe[tag_column_name].dropna().apply(
        lambda value: ast.literal_eval(value) if isinstance(value, str) else value
    )

    counts = Counter(
        tag["name"]
        for row in tags
        for tag in row
        if isinstance(tag, dict) and "name" in tag
    )

    return counts.most_common()

print(user_a_tracks_with_counter.head())
print(user_b_tracks_with_counter.head())

print(f" -------- TOP TRACK TAGS -------")
print(get_top_tags(user_a_tracks_with_counter, "track_tags"))
print("---------------------------------------")
print(get_top_tags(user_b_tracks_with_counter, "track_tags"))

print(f" -------- TOP ALBUM TAGS -------")
print(get_top_tags(user_a_tracks_with_counter, "album_tags"))
print("---------------------------------------")
print(get_top_tags(user_b_tracks_with_counter, "album_tags"))

print(f" -------- TOP ARTIST TAGS -------")
print(get_top_tags(user_a_tracks_with_counter, "artist_tags"))
print("---------------------------------------")
print(get_top_tags(user_b_tracks_with_counter, "artist_tags"))

# filter out non-genre tags -> tags with only "1" use?
# ignore capitalization in tags
# remove exact year tags (4 digit tags)
# HOW: report tag coverage by % of plays for each user ?


sqliteConnection.commit()
sqliteConnection.close()

# TODO: extra considerations
# what if an artist/album/artist does eventually get tags added to it? what do? solution: add a query timestamp to na and if it has been longer than x period of time, can requery
# entries with no listen timestamp (some of Ty's)? handle how?
# entries with wrong len of foundTrack? why?
# entries with NaN album: twenty one pilots can't help falling in love & alphabet war Greenland (needed 2 seperate solutions; alphabet war skipped entirely)
# artists that have tags on the website BUT it does not work properly 
# STORE dataframes for future usage/reference as well?

# TODO: turn these into actual coding steps with details. what do they mean?
# PI3 (expected): Fetch weighted tags for each user's most-played songs and filter out non-genre tags
# DONE PI4 (expected): Add artist-level tags as a fallback for songs with missing or very few tags, and exclude songs that still have no tags
# PI5 (advanced): Analyze why songs fail to get tags (name mismatches, obscure tracks) and add a general cleaning step that fixes the common cases for any input history, and report tag coverage by % of plays for each user

# TODO: experiment with these steps as actual coding steps. what libraries will build the appropriate vector? what do they look like ? (print them)
# PI1 (basic): Build a taste vector for each user from play-count-weighted tags
# PI2 (basic): Compute cosine similarity between two users and convert it to a percentage
# PI3 (expected): Add time decay so recent plays count more, and compute the vector at any chosen date