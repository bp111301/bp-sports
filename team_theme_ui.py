"""Presentation colors only; never influences a saved forecast."""
import json
import re
from pathlib import Path
from functools import lru_cache
from college_team_ui import name_key
from preview_data import team

@lru_cache(maxsize=1)
def palette():
    return json.loads((Path(__file__).parent/'data/team_colors.json').read_text())

def team_color(sport,name,team_id=None):
    source=palette().get(sport,{})
    if sport in ('CFB','CBB'):
        color=source.get('ids',{}).get(str(team_id)) if team_id is not None else None
        color=color or source.get('names',{}).get(name_key(name))
    else: color=source.get(team(sport,name))
    return color if color and re.fullmatch(r'#[0-9a-fA-F]{6}',color) else '#315d96'

def text_color(color):
    red,green,blue=(int(color[i:i+2],16) for i in (1,3,5))
    return '#101722' if (red*299+green*587+blue*114)/1000>=145 else '#ffffff'

def accent_color(color):
    red,green,blue=(int(color[i:i+2],16) for i in (1,3,5))
    return '#'+''.join(f'{int(v+(255-v)*.3):02x}' for v in (red,green,blue))
