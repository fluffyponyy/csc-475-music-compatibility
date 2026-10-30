import sqlite3

sqliteConnection = sqlite3.connect('lastfm-tags.db')
cursor = sqliteConnection.cursor()

track_creation_query = """
    CREATE TABLE IF NOT EXISTS TRACK (
        Name TEXT NOT NULL,
        AlbumName TEXT NOT NULL,
        ArtistName TEXT NOT NULL,
        Tags TEXT NOT NULL
    );
"""

album_creation_query = """
    CREATE TABLE IF NOT EXISTS ALBUM (
        Name TEXT NOT NULL,
        ArtistName TEXT NOT NULL,
        Tags TEXT NOT NULL
    );
"""

artist_creation_query = """
    CREATE TABLE IF NOT EXISTS ARTIST (
        Name TEXT NOT NULL,
        Tags TEXT NOT NULL
    );
"""

# Execute the table creation query
cursor.execute(track_creation_query)
cursor.execute(album_creation_query)
cursor.execute(artist_creation_query)

# Confirm that the table has been created
print("Tables ready")

# Close the connection to the database
sqliteConnection.close()