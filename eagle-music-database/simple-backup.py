import json
import os
from time import sleep

import requests


def get_user_playlists(user_id):
    """Returns a list of all of the Deezer users playlists."""
    user_playlists_url = f"https://api.deezer.com/user/{user_id}/playlists"
    response = requests.get(user_playlists_url)
    playlist_data = response.json()

    playlists = []
    if "error" in playlist_data:
        print(f"Error fetching playlists: {playlist_data['error']}")
        return []

    while True:
        for item in playlist_data.get("data", []):
            playlists.append({
                "title": item["title"],
                "tracklist_url": item["tracklist"],
                "id": item["id"],
                "nb_tracks": item["nb_tracks"]
            })
        
        if "next" in playlist_data:
            response = requests.get(playlist_data["next"])
            playlist_data = response.json()
        else:
            break
            
    return playlists


def get_playlist_tracks(tracklist_url):
    """Fetches all tracks from a given playlist URL."""
    response = requests.get(tracklist_url)
    tracks_data = response.json()
    
    tracks = []
    if "error" in tracks_data:
        print(f"Error fetching tracks: {tracks_data['error']}")
        return []

    while True:
        for item in tracks_data.get("data", []):
            # Handle cases where track might be unreadable or missing details
            if "id" not in item:
                continue

            track_info = {
                "id": item["id"],
                "title": item["title"],
                "artist": item["artist"]["name"] if "artist" in item else "Unknown",
                "album": item["album"]["title"] if "album" in item else "Unknown",
                "link": item["link"] if "link" in item else "",
                "duration": item.get("duration", 0),
                "rank": item.get("rank", 0),
                "preview": item.get("preview", "")
            }
            tracks.append(track_info)
            
        if "next" in tracks_data:
            sleep(0.1) # Be polite to the API
            response = requests.get(tracks_data["next"])
            tracks_data = response.json()
        else:
            break
            
    return tracks


def backup_playlists(deezer_user_id=None):
    print(f"Fetching playlists for user ID: {deezer_user_id}")
    playlists = get_user_playlists(deezer_user_id)
    print(f"Found {len(playlists)} playlists.")
    
    all_data = []
    
    for i, playlist in enumerate(playlists):
        print(f"Processing playlist {i+1}/{len(playlists)}: {playlist['title']} ({playlist['nb_tracks']} tracks)")
        tracks = get_playlist_tracks(playlist['tracklist_url'])
        
        playlist_entry = {
            "playlist_id": playlist["id"],
            "title": playlist["title"],
            "nb_tracks": playlist["nb_tracks"],
            "tracks": tracks
        }
        all_data.append(playlist_entry)
        
    # Save to the same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "backups/deezer_backup.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)
        
    print(f"Backup complete. Saved {len(all_data)} playlists to {output_file}")


if __name__ == "__main__":
    backup_playlists("DEEZER_USER_ID_HERE")
