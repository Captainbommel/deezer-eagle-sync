import datetime
import json
import os
import re

import requests
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
PROJECT_PATH = os.getenv("PROJECT_PATH")
VAULT_PATH = os.getenv("VAULT_PATH")
IMAGE_LIBRARY_NAME = os.getenv("IMAGE_LIBRARY_NAME")


def get_eagle_name(eagle_id):
    url = f"http://localhost:41595/api/item/info?id={eagle_id}"
    response = requests.get(url)
    data = response.json()
    name = data["data"]["name"]

    if response.status_code != 200:
        print("Error:", response.status_code)
        return None

    return name


def get_eagle_id(name):
    url = f"http://localhost:41595/api/item/list?limit=1&name={name}"
    response = requests.get(url)
    data = response.json()

    if response.status_code != 200:
        print("Error:", response.status_code)
        return None

    if data["data"][0]["name"] == name:
        return data["data"][0]["id"]

    return None


def get_eagle_ids_and_names(limit=1000000):
    """Returns the eagle ids and the names of the files"""
    url = f"http://localhost:41595/api/item/list?limit={limit}"
    response = requests.get(url)
    data = response.json()

    if response.status_code != 200:
        print("Error:", response.status_code)
        return []

    length = len(data["data"])
    print(f"Number of Pictures found: {length}")
    ids = [None] * length
    names = [None] * length
    for i in range(length):
        ids[i] = data["data"][i]["id"]
        names[i] = data["data"][i]["name"]

    return ids, names


def get_date(eagle_id):
    url = f"http://localhost:41595/api/item/info?id={eagle_id}"

    response = requests.get(url)
    data = response.json()
    timestamp = data["data"]["btime"]

    if response.status_code != 200:
        print("Error:", response.status_code)
        return

    return datetime.datetime.fromtimestamp(timestamp / 1000)


def update_btime(eagle_id, new_time):
    path = f"{VAULT_PATH}/{IMAGE_LIBRARY_NAME}/images/{eagle_id}.info/metadata.json"
    timestamp = int(new_time.timestamp() * 1000)

    with open(path, "r") as file:
        metadata = json.load(file)
    file.close()

    metadata["btime"] = timestamp
    with open(path, "w") as file:
        json.dump(metadata, file)
    file.close()


def get_date_from_string(str):
    pattern = [r"VID-(\d{8})-WA\d{4}", r"IMG-(\d{8})-WA\d{4}", r"PXL-(\d{8})-\d{9}"]

    for regex_pattern in pattern:
        match = re.search(regex_pattern, str)
        if match:
            #? import datetime 
            return datetime.strptime(match.group(1), "%Y%m%d")
    return None


def get_date_taken_from_exif(eagle_id):
    path = f"{VAULT_PATH}/{IMAGE_LIBRARY_NAME}/images/{eagle_id}.info/"

    with open(path + "metadata.json", "r") as file:
        metadata = json.load(file)
    file.close()

    if metadata["ext"] in ["mov", "mp4", "gif", "pdf"]:
        return None
    exif = Image.open(path + metadata["name"] + "." + metadata["ext"])._getexif()
    if not exif:
        return None
    return datetime.datetime.strptime(exif[36867], "%Y:%m:%d %H:%M:%S")


def main():
    ids, names = get_eagle_ids_and_names()

    pattern = [
        r"VID-(\d{8})-WA\d{4}",  # whatsapp video
        r"IMG-(\d{8})-WA\d{4}",  # whatsapp image
        r"PXL-(\d{8})-\d{9}",  # pixel image
        r"PXL_(\d{8})_\d{9}",  # pixel image
        r"(\d{8})_\d{9}_iOS",  # iOS image
        r"VID-(\d{8})-\d{6}",  # unknown source video
        r"VID_(\d{8})_\d{6}",  # unknown source video
        r"Screenshot_(\d{8})-\d{6}",  # screenshot
        r"Screenshot_(\d{4})-(\d{2})-(\d{2})-\d{2}-\d{2}-\d{2}",  # screenshot
        r"\d{3}-DSC\d{5}-(\d{8})-\d{4}-\d{2}-\d{2}-",  # unknown source image
        r"IMG_(\d{8})_\d{6}",  # unknown source image
        r"(\d{8})\d{8}-",  # switch screenshot
        r"(\d{13})-.{8}(-)",
    ]

    skip = []

    start = 0
    missing = []
    for i in range(start, len(names)):
        if names[i] in skip:
            continue
        print(names[i], i)

        found = False
        for regex_pattern in pattern:
            match = re.search(regex_pattern, names[i])
            if match:
                if re.compile(regex_pattern).groups == 3:
                    date = datetime.datetime.strptime(
                        match.group(1) + match.group(2) + match.group(3), "%Y%m%d"
                    )
                    update_btime(ids[i], date)

                elif re.compile(regex_pattern).groups == 2:
                    date = datetime.datetime.fromtimestamp(int(match.groups(1)[0]) / 1000)
                    update_btime(ids[i], date)

                else:
                    date = datetime.datetime.strptime(match.group(1), "%Y%m%d")
                    update_btime(ids[i], date)

                found = True
                break

        if found is False:
            date = get_date_taken_from_exif(ids[i])
            if date is not None:
                update_btime(ids[i], date)
            else:
                missing.append(names[i])
                print(f"the date for: '{names[i]}' could not be found")

    print(missing)


if __name__ == "__main__":
    main()
