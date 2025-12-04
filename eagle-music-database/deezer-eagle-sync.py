from time import sleep
import requests
import json
import pickle
from dotenv import load_dotenv
import os

# Load the environment variables
load_dotenv()
PROJECT_PATH = os.getenv("PROJECT_PATH")
DEEZER_USER_ID = os.getenv("DEEZER_USER_ID")
EAGLE_API_BASE = "http://localhost:41595/api"

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def deezer_api_request(endpoint: str, id: str):
    """Returns the json response of a deezer api request"""
    url = f"https://api.deezer.com/{endpoint}/{id}"
    response = requests.get(url)
    try:
        return response.json()
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {url}")
        return {}

def get_deezer_paginated(url: str):
    """Generator that yields items from a paginated Deezer API endpoint."""
    while url:
        try:
            response = requests.get(url)
            data = response.json()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            break
        
        if "error" in data:
            print(f"Deezer API Error: {data['error']}")
            break

        for item in data.get("data", []):
            yield item
        
        url = data.get("next")
        if url:
            sleep(0.1)

def eagle_api_request(endpoint: str, method="GET", data=None):
    """Centralized handler for Eagle API requests."""
    url = f"{EAGLE_API_BASE}/{endpoint}"
    headers = {"Content-Type": "application/json"}
    
    try:
        if method == "GET":
            response = requests.get(url, params=data)
        else:
            response = requests.post(url, data=json.dumps(data) if data else None, headers=headers)
            
        if response.status_code != 200:
            print(f"Eagle API Error ({endpoint}): {response.status_code}")
            return None
        return response.json()
    except Exception as e:
        print(f"Eagle API Exception ({endpoint}): {e}")
        return None

def remove_non_file_chars(name: str) -> str:
    """Replaces characters which can't be in filenames with similar ones."""
    find = ['\"', ":", "/", "???", "?", "<", ">", "*", "|"]
    replace = ["⧵", "׃", "／", "unknown artist", "", "ᐸ", "ᐳ", "⚹", "⎟"]

    name = name.strip()
    for f, r in zip(find, replace):
        name = name.replace(f, r)
    return name

def minusminus(string: str) -> str:
    """Replaces ' - ' with ' ‒ '."""
    return string.strip().replace(" - ", " ‒ ")

def get_filename(title: str, artist: str) -> str:
    """Returns the eagle filename of a track."""
    return remove_non_file_chars(f"{minusminus(title)} - {minusminus(artist)}")

def split_name(name):
    """Splits the name of a track into title and artist"""
    if name.count(" - ") > 1:
        raise ValueError(f"'{name}' contains more than one ' - '")

    split = name.split(" - ")
    if len(split) == 2:
        return split[0], split[1]
    else:
        raise ValueError(f"'{name}' could not be split in title and artist")

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class track(object):
    def __init__(
        self, title: str, artist: str, deezer_id: str, tags: list[str], eagle_id="", link=""
    ):
        self.title = title
        self.artist = artist
        self.deezer_id = deezer_id
        self.eagle_id = eagle_id
        self.tags = set(tags)
        self.link = link

    @property
    def api_link(self):
        if self.link:
            return self.link
        return f"https://api.deezer.com/track/{self.deezer_id}"

    @property
    def is_mp3(self):
        try:
            return int(self.deezer_id) < 0
        except ValueError:
            return False

    def __eq__(self, other) -> bool:
        if not isinstance(other, track):
            return False
        return self.deezer_id == other.deezer_id

    def __hash__(self) -> int:
        return hash(self.deezer_id)

    def __str__(self) -> str:
        return f"{self.title} - {self.artist} - {self.deezer_id}"

    def __repr__(self) -> str:
        return self.__str__()

    def coverimage_link(self):
        if self.is_mp3:
            return None
        data = deezer_api_request("track", self.deezer_id)
        return data.get("album", {}).get("cover_big")

    def preview_link(self):
        if self.is_mp3:
            return ""
        data = deezer_api_request("track", self.deezer_id)
        return data.get("preview", "")


class playlist(object):
    def __init__(
        self,
        title: str,
        deezer_id: str = "",
        tracklist_url: str = "",
        tracklist: list[track] = None,
    ):
        self.title = title
        self.deezer_id = deezer_id
        self.tracklist_url = tracklist_url
        self.tracklist: set[track] = set(tracklist) if tracklist else set()

    @property
    def api_link(self):
        return f"https://api.deezer.com/playlist/{self.deezer_id}"

    def complement(self, other):
        return list(set(self.tracklist) - set(other.tracklist))

    def __str__(self) -> str:
        return f"{self.title} - {len(self.tracklist)} tracks"

    def __repr__(self) -> str:
        return self.__str__() + "\n"

    def coverimage_link(self):
        data = deezer_api_request("playlist", self.deezer_id)
        return data.get("picture_big")

    def fetch_tracks(self):
        """Fetches tracks from Deezer and populates the tracklist."""
        if not self.tracklist_url:
            # Fallback if URL wasn't provided during init
            data = deezer_api_request("playlist", self.deezer_id)
            self.tracklist_url = data.get("tracklist")
            
        if not self.tracklist_url:
            print(f"Could not find tracklist URL for playlist {self.title}")
            return

        for item in get_deezer_paginated(self.tracklist_url):
            # Handle cases where track might be unreadable or missing details
            if "id" not in item:
                continue
                
            t = track(
                title=item["title"],
                artist=item["artist"]["name"] if "artist" in item else "Unknown",
                deezer_id=str(item["id"]),
                tags=[self.title],
                link=item.get("link", "")
            )
            self.tracklist.add(t)

# -----------------------------------------------------------------------------
# Core Logic
# -----------------------------------------------------------------------------

def deezer_user_playlists(user_id: str):
    """Returns a list of playlists from Deezer."""
    url = f"https://api.deezer.com/user/{user_id}/playlists"
    playlists = []
    
    for item in get_deezer_paginated(url):
        playlists.append(
            playlist(
                title=item["title"], 
                deezer_id=str(item["id"]), 
                tracklist_url=item.get("tracklist", "")
            )
        )
    return playlists

def eagle_playlist(limit=1000000):
    """Returns a list of playlists based on the tags in eagle"""
    data = eagle_api_request("item/list", data={"limit": limit})
    if not data:
        return []

    length = len(data["data"])
    print(f"Found {length} items in Eagle")

    playlists = dict()
    failed = []

    for item in data["data"]:
        try:
            title, artist = split_name(item["name"])
        except ValueError as e:
            print(e)
            failed.append(item["name"])
            continue

        for tag in item["tags"]:
            if tag not in playlists:
                playlists[tag] = playlist(tag)

            playlists[tag].tracklist.add(
                track(
                    title=title,
                    artist=artist,
                    deezer_id=item["annotation"],
                    eagle_id=item["id"],
                    tags=item["tags"],
                )
            )

    print(f"{len(failed)} items failed to parse from Eagle") if len(failed) > 0 else None
    return list(playlists.values())

def get_eagle_id_by_name(name: str) -> str | None:
    data = eagle_api_request("item/list", data={"limit": 1, "name": name})
    if data and data["data"] and data["data"][0]["name"] == name:
        return data["data"][0]["id"]
    return None

def get_eagle_item_tags(eagle_id: str) -> list[str]:
    data = eagle_api_request("item/info", data={"id": eagle_id})
    if data:
        return data.get("data", {}).get("tags", [])
    return []

def add_to_eagle(track: track, tags: list[str]):
    """Adds a track to the Eagle music database."""
    filename = get_filename(track.title, track.artist)
    
    if track.is_mp3:
        # Use local placeholder image for MP3s
        image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mp3.jpg")
        data = {
            "path": image_path,
            "name": filename,
            "website": track.api_link,
            "tags": list(set(tags)),
            "annotation": track.deezer_id,
        }
        endpoint = "item/addFromPath"
    else:
        try:
            image_url = track.coverimage_link()
        except Exception as e:
            print(f"Could not get cover image for {track}: {e}")
            return

        web_link = f"https://www.deezer.com/track/{track.deezer_id}"
        data = {
            "url": image_url,
            "name": filename,
            "website": web_link,
            "tags": list(set(tags)),
            "annotation": track.deezer_id,
        }
        endpoint = "item/addFromURL"

    result = eagle_api_request(endpoint, method="POST", data=data)
    if result:
        print(f"Added {filename} to Eagle.")

def update_eagle_item(eagle_id: str, deezer_id: str, tags: list[str] = None):
    data = {
        "id": eagle_id,
        "annotation": deezer_id,
        "url": f"https://www.deezer.com/track/{deezer_id}",
    }
    if tags is not None:
        data["tags"] = list(set(tags))
        
    result = eagle_api_request("item/update", method="POST", data=data)
    if result:
        print(f"Updated Eagle ID {eagle_id} with Deezer ID {deezer_id}")

def update_eagle_from_complement(complement: list[track], playlist_title: str):
    """Updates eagle with the complement of the deezer playlist."""
    if not complement:
        return

    print(f"Processing {len(complement)} tracks for sync...")
    
    for track in complement:
        filename = get_filename(track.title, track.artist)
        eagle_id = get_eagle_id_by_name(filename)
        
        if eagle_id:
            print(f"Updating existing track: {filename}")
            current_tags = get_eagle_item_tags(eagle_id)
            new_tags = current_tags + [playlist_title]
            update_eagle_item(eagle_id, track.deezer_id, new_tags)
        else:
            print(f"Adding new track: {filename}")
            add_to_eagle(track, [playlist_title])

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    if not DEEZER_USER_ID:
        print("Error: DEEZER_USER_ID not found in environment variables.")
        exit(1)

    # Cache configuration
    USE_CACHE = True
    CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deezer_playlists.pkl")

    deezer_playlists = []

    # Try to load from cache
    if USE_CACHE and os.path.exists(CACHE_FILE):
        print(f"Loading Deezer playlists from cache: {CACHE_FILE}")
        try:
            with open(CACHE_FILE, "rb") as f:
                deezer_playlists = pickle.load(f)
            
            # Validate cache schema compatibility
            valid_cache = True
            if deezer_playlists:
                for pl in deezer_playlists:
                    if pl.tracklist:
                        sample_track = next(iter(pl.tracklist))
                        if not hasattr(sample_track, "deezer_id"):
                            print("Cache contains outdated data structure. Discarding.")
                            valid_cache = False
                        break
            
            if not valid_cache:
                deezer_playlists = []
            else:
                print("Loaded playlists from cache.")

        except Exception as e:
            print(f"Failed to load cache: {e}")
            deezer_playlists = []

    # If not loaded from cache, fetch from API
    if not deezer_playlists:
        print("Fetching Deezer playlists...")
        deezer_playlists = deezer_user_playlists(DEEZER_USER_ID)
        deezer_playlists.sort(key=lambda x: x.title)

        print("Downloading tracklists for all playlists...")
        for i, d_playlist in enumerate(deezer_playlists):
            print(f"Fetching tracks for {d_playlist.title} ({i+1}/{len(deezer_playlists)})")
            d_playlist.fetch_tracks()
        
        if USE_CACHE:
            print(f"Saving to cache: {CACHE_FILE}")
            with open(CACHE_FILE, "wb") as f:
                pickle.dump(deezer_playlists, f)

    print("Fetching Eagle playlists...")
    eagle_playlists = eagle_playlist()
    eagle_playlists.sort(key=lambda x: x.title)

    # Create a map of Eagle playlists for faster lookup
    eagle_map = {p.title: p for p in eagle_playlists}

    for d_playlist in deezer_playlists:
        print(f"Syncing playlist: {d_playlist.title}")
        # d_playlist.fetch_tracks() # Already fetched
        print(d_playlist)
        
        e_playlist = eagle_map.get(d_playlist.title)
        
        if e_playlist:
            complement = d_playlist.complement(e_playlist)
            print(f"Missing in Eagle: {len(complement)} tracks")
            update_eagle_from_complement(complement, d_playlist.title)
        else:
            print(f"New playlist found: {d_playlist.title}")
            # If playlist doesn't exist in Eagle, all tracks are the complement
            update_eagle_from_complement(list(d_playlist.tracklist), d_playlist.title)
        
        print("-" * 40)
    

    