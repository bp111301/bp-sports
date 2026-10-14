"""Display abbreviations from ESPN team metadata, independent of model inputs."""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

def name_key(name):
    text = unicodedata.normalize('NFKD',str(name).replace('&',' and '))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]','',text.casefold())

@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).parent/'data/college_team_abbreviations.json').read_text())

def college_abbreviation(sport,name,team_id=None):
    entries=catalog().get(sport,{})
    if team_id is not None:
        abbreviation=entries.get('ids',{}).get(str(team_id))
        if abbreviation:return abbreviation
    return entries.get('names',{}).get(name_key(name),'NCAA')
