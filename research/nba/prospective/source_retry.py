"""Bounded retries for unavailable or malformed ESPN scoreboards."""
import json
import time
import requests

def fetch_scoreboard(fetch, url):
    for attempt in range(3):
        try:
            data = json.loads(fetch(url))
            if not isinstance(data, dict) or not isinstance(data.get('events'), list):
                raise ValueError('Missing scoreboard events list')
            return data
        except (requests.RequestException, ValueError) as error:
            if attempt == 2:
                raise ValueError('NBA scoreboard unavailable after 3 attempts: ' + url) from error
            time.sleep(2 ** attempt)
