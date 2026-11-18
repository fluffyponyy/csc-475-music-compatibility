import csv
import requests
from dotenv import load_dotenv
import os
import json
import time
from datetime import datetime
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import sqlite3

import pandas as pd

load_dotenv()

USERNAME_A = "fluffyponyy"
USERNAME_B = "devanasson"

API_KEY = os.getenv('KEY')
USER_AGENT = os.getenv('USERNAME')

# CSV files from https://benjaminbenben.com/lastfm-to-csv/

# number of seconds between api calls
RATE_LIMIT = 0.2

def convert_2_date(timestamp: str):
    return datetime.strptime(timestamp, "%d %b %Y, %H:%M")

# time duration to compare both users to
# what time/date object can we use for easier comparision here?
# file end and start:
# date_start_str = "01 Mar 2026, 00:00"
# date_end_str = "27 Oct 2026, 23:59"

date_start_str = "1 Mar 2025, 00:00"
date_end_str = "30 Apr 2025, 23:59"

DATE_START = convert_2_date(date_start_str)
DATE_END = convert_2_date(date_end_str)

bad_tags = ["album", "albums", "best", "great", "greatest", "worst",
            "vinyl", "boxset", "own", "digital", "eps", "aoty", "fav", 
            "favorite", "favourite", "short", "currentfavorites", 
            "amazing", "songsaboutexes", "mvrrockradio", "sawthemlive", "damnedgood", "soty",
            "ilovethis", "fuckingbeautiful", "ynaayt", "dbdbdbdbdbdbdbdbdbdbdb", "jennie", "juliamofada",
            "all", "listened", "gorgeous", "tolisten", "beautiful", "spotify", "perfect", "friends", "release", "releases",
            "topcd", "cool", "fire", "good"]


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
                # jprint(r.json())
                # print(item["artist"])

                if "message" in r.json() and "could not be found" in r.json()['message']: 
                    print(f"did not find album {item["album"]}  by {item["artist"]}; skipping track {item["track"]} entirely")
                    continue
                
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

import re


def clean_tags(user_dataframe, tag_column_name):
    def parse(value):
        try:
            return ast.literal_eval(value) if isinstance(value, str) else value
        except (ValueError, SyntaxError):
            return value  # keep the original string

    tags = user_dataframe[tag_column_name].dropna().apply(parse)

    for idx, row in tags.items():
        newrow = []
        for pair in row:
            tag = pair["name"]
            tag = tag.strip().lower()


            # match any numbers
            if bool(re.fullmatch(r'\d+', tag)):
                print(f"removing tag {tag}")
                continue
            words = tag.split()
            if len(words) > 3:
                print(f"removing tag {tag}")
                continue

            # ignore spaces and hyphens
            tag = tag.replace(" ", "")
            tag = tag.replace("-", "")

            if any(t in bad_tags for t in words):
                print(f"removing tag {tag}")
                continue
            #if artist name (in lowercase) = tag name, then remove
            #what about equivalences? i.e "vgm" = "video game music"
            # more stupid number include 4-5, 45, 24 first listen, country200er, country2001, mtplay, totec radio, 3-5, 1980s=80s, 00s=2000s, 1990s=90s, 1960s=60s, 1970s=70s, 1950s=50s, mygang10, 2025releases
            # ignore a /

            pair["name"] = tag
            newrow.append(pair)
        tags.at[idx] = newrow
        
    return tags

def get_top_tags(tags, weight=1.0):
    unique_tags_by_count = {}
    
    for row in tags:
        #print(row)
        for pair in row:
            tagname = pair["name"]
            tagcount = pair["count"]

            if tagname in unique_tags_by_count.keys():
                unique_tags_by_count[tagname] += (tagcount / 100) * weight
            else:
                unique_tags_by_count[tagname] = (tagcount / 100) * weight

    #print(dict(sorted(unique_tags_by_count.items(), key=lambda item: item[1], reverse=True),))
            
    return dict(sorted(unique_tags_by_count.items(), key=lambda item: item[1], reverse=True),)

def get_top_percentile(df,percent):

    start = 0
    end = int(len(df)*percent)

    return df.iloc[start:end]

print(f" -------- TOP TRACKS - PLAYCOUNT > 1 -------")
a_playcount = user_a_tracks_with_counter[user_a_tracks_with_counter['playcount'] > 2]
a_playcount.sort_values("playcount", ascending=False, inplace=True)
# print(a_playcount[['track', 'artist', 'playcount']])

a_album_tags = clean_tags(a_playcount, "album_tags")
a_track_tags = clean_tags(a_playcount, "track_tags")
a_artist_tags = clean_tags(a_playcount, "artist_tags")

# Weight artist, track, and album equally
sum_of_tags_a = a_album_tags+a_track_tags+a_artist_tags
print(sum_of_tags_a)
#for unweighted
a_dict = get_top_tags(sum_of_tags_a)

#for weighted
a_dict_top_album = get_top_tags(a_album_tags, 0.5)
a_dict_top_artist = get_top_tags(a_artist_tags)
a_dict_top_tracks = get_top_tags(a_track_tags, 0.15)

combined = {}
for d in (a_dict_top_artist, a_dict_top_album, a_dict_top_tracks):
    for tag, v in d.items():
        combined[tag] = combined.get(tag, 0) + v

a_dict_weighted = dict(sorted(combined.items(), key=lambda kv: kv[1], reverse=True))

print("FINAL dict for user A: ----------------------------------")
print(a_dict)
print("---------------------------------------")
b_playcount = user_b_tracks_with_counter[user_b_tracks_with_counter['playcount'] > 2]
b_playcount.sort_values("playcount", ascending=False, inplace=True)
# print(b_playcount[['track', 'artist', 'playcount']])

b_album_tags = clean_tags(b_playcount, "album_tags")
b_track_tags = clean_tags(b_playcount, "track_tags")
b_artist_tags = clean_tags(b_playcount, "artist_tags")

# Weight artist, track, and album equally
sum_of_tags_b = b_album_tags+b_track_tags+b_artist_tags
print(sum_of_tags_b)
b_dict = get_top_tags(sum_of_tags_b)

#for weighted
b_dict_top_album = get_top_tags(b_album_tags, 0.5)
b_dict_top_artist = get_top_tags(b_artist_tags)
b_dict_top_tracks = get_top_tags(b_track_tags, 0.15)

combined = {}
for d in (b_dict_top_artist, b_dict_top_album, b_dict_top_tracks):
    for tag, v in d.items():
        combined[tag] = combined.get(tag, 0) + v

b_dict_weighted = dict(sorted(combined.items(), key=lambda kv: kv[1], reverse=True))

print("FINAL dict for user B: ----------------------------------")
print(b_dict)

print("normalized dicts")
print(a_dict_weighted)
print(b_dict_weighted)

# Duckduckgo AI summary:
# DictVectorizer turns both dictionaries into vectors with the same feature columns, using the union of their keys.
# A feature’s dictionary value is placed in its column, and a missing feature is treated as 0.
# cosine_similarity(X)[0, 1] then compares the two vectors’ patterns of values, producing a score from 0 to 1 when all values are nonnegative

#DictVectorizer creates one shared feature space for both rows and treats absent features as zero.
#You don’t need to manually add missing keys to either dictionary.
# Make both dictionaries use the union of their feature names, filling missing features with 0
vec = DictVectorizer(sparse=True) # probably better to use sparse=True as most people will not have that many things in common?

X = vec.fit_transform([a_dict, b_dict])
X_weighted = vec.fit_transform([a_dict_weighted, b_dict_weighted])

print("vectors")
print(X)
print(X_weighted)

similarity = cosine_similarity(X)[0, 1]
w_similarity = cosine_similarity(X_weighted)[0, 1]
print(similarity)
print(w_similarity)
print("top 10 tags: unweighted")
print(list(a_dict.items())[:10])
print(list(b_dict.items())[:10])

print("top 10 tags: weighted")
print(list(a_dict_weighted.items())[:10])
print(list(b_dict_weighted.items())[:10])





# print(f" -------- TOP TRACKS - TOP 25% BY PLAYCOUNT -------")
# user_a_tracks_with_counter.sort_values("playcount", ascending=False, inplace=True)
# user_a_tracks_with_counter = get_top_percentile(user_a_tracks_with_counter,0.25)
# print(user_a_tracks_with_counter[['track', 'artist', 'playcount']])
# print("---------------------------------------")
# user_b_tracks_with_counter.sort_values("playcount", ascending=False, inplace=True)
# user_b_tracks_with_counter = get_top_percentile(user_b_tracks_with_counter,0.25)
# print(user_b_tracks_with_counter[['track', 'artist', 'playcount']])

# print(f" -------- TOP ALBUM TAGS -------")
# print(get_top_tags(user_a_tracks_with_counter, "album_tags"))
# print("---------------------------------------")
# print(get_top_tags(user_b_tracks_with_counter, "album_tags"))

# print(f" -------- TOP ARTIST TAGS -------")
# print(get_top_tags(user_a_tracks_with_counter, "artist_tags"))
# print("---------------------------------------")
# print(get_top_tags(user_b_tracks_with_counter, "artist_tags"))

# extra: prioritize artist > album > track
# HOW: report tag coverage by % of plays for each user ?


sqliteConnection.commit()
sqliteConnection.close()

# TODO: extra considerations
# what if an artist/album/artist does eventually get tags added to it? what do? solution: add a query timestamp to na and if it has been longer than x period of time, can requery
# entries with no listen timestamp (some of Ty's)? handle how?
# entries with wrong len of foundTrack? why?
# entries with NaN album: twenty one pilots can't help falling in love & alphabet war Greenland (needed 2 seperate solutions; alphabet war skipped entirely)
# artists that have tags on the website BUT it does not work properly 
# check that the artist exists before getting toptags
# STORE dataframes for future usage/reference as well?
# edge case: those who don't have ANY or enough data over a given timespan?
# **** EXPERIMENT WITH: how to select user's top tracks? top 25% by playcount? anything with playcount > 1? select between the two based on what top % anything with playcount > 1 results in?
# ** EXPERIMENT WITH: does it make a difference for the cosine similarity computation if we divide the tagcounts by 100? does it do better with bigger number?
# pls organize this file into different files.....
# should do cleaning once and save results? should clean after collecting data?
# move user CSVs to their own folder, save dataframes to its own folder

# TODO: turn these into actual coding steps with details. what do they mean?
# DONE PI3 (expected): Fetch weighted tags for each user's most-played songs and filter out non-genre tags
# DONE PI4 (expected): Add artist-level tags as a fallback for songs with missing or very few tags, and exclude songs that still have no tags
# SORT OF DONE PI5 (advanced): Analyze why songs fail to get tags (name mismatches, obscure tracks) and add a general cleaning step that fixes the common cases for any input history, and report tag coverage by % of plays for each user

# TODO: experiment with these steps as actual coding steps. what libraries will build the appropriate vector? what do they look like ? (print them)
# DONE PI1 (basic): Build a taste vector for each user from play-count-weighted tags
# DONE PI2 (basic): Compute cosine similarity between two users and convert it to a percentage

# TODO: NEXT STEPS (11/17)
# 1. (DONE) integrate all 3 tag types into calculations
# 2. PI4 (expected): Output the top shared tags and artists that drive AN INDIVIDUAL user's score -> how to seperate between users?
# 3. # PI3 (expected): Add time decay so recent plays count more, and compute the vector at any chosen date
# 4. PI5 (advanced): Weight each tag by how rare it is across songs, and each artist by how few listeners it has (shared niche taste counts for more than shared mainstream taste)
# 5. Experiment with: 
# euclidean/manhattan distance if absolute differences matter: sklearn.metrics.pairwise.euclidean_distances(X)[0, 1] (lower = more similar, so you’d convert it to a similarity yourself)
# weighted jaccard (sum of min / sum of max per tag) if you want something that explicitly punishes value gaps and is bounded 0 to 1


#notes: 
# Traceback (most recent call last):
#   File "C:\Users\fluffyponyy\Documents\UVic\CSC 475\csc-475-music-compatibility\lastfm-api.py", line 270, in <module>
#   File "C:\Users\fluffyponyy\Documents\UVic\CSC 475\csc-475-music-compatibility\lastfm-api.py", line 129, in create_user_dataframe
#     gotTrackTags = True
# sqlite3.IntegrityError: NOT NULL constraint failed: TRACK.AlbumName