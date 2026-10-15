"""Read-only final-game recap, kept separate from pregame commentary."""
import json
from pathlib import Path
from urllib.request import Request,urlopen
import pandas as pd
import streamlit as st
from game_center_ui import context
from recap_data import recap_paragraphs,verified_final
from preview_data import game_id

@st.cache_data(ttl=120)
def load_recaps():
    try:
        req=Request('https://raw.githubusercontent.com/bp111301/bp-sports/main/data/game_recaps.json',headers={'User-Agent':'BP-Sports-Recap-UI/1.0'})
        with urlopen(req,timeout=5) as response:return json.loads(response.read(6*1024*1024)).get('games',{})
    except (OSError,ValueError):
        try:return json.loads((Path(__file__).parent/'data/game_recaps.json').read_text()).get('games',{})
        except (OSError,ValueError):return {}

def render_recap(d,now=None):
    status=context(d['sport'],d['game_id'],d['home'],d['away'])
    if not status or status.get('state')!='final':
        if d['settled']:
            st.markdown('#### Game recap');st.info('This pick has been graded, but a verified final score is unavailable in the score feed. The recap will appear once it can be verified.')
            return True
        return False
    record=load_recaps().get(d['sport']+':'+game_id(d['game_id']))
    if not record or not verified_final(record,status):
        record={**status,'flow':None,'facts':[],'leaders':[],'detailed':False}
    st.markdown('#### Game recap')
    for paragraph in recap_paragraphs(record):st.write(paragraph)
    st.caption('Postgame facts are separate from the original forecast. '+('Grading is still pending.' if not d['settled'] else 'Saved pick result: '+d['result']+'.'))
    checked=pd.to_datetime(record.get('checked_at_utc'),utc=True,errors='coerce')
    if pd.notna(checked):st.caption('Recap checked '+checked.tz_convert('America/Chicago').strftime('%b %d · %-I:%M %p CT'))
    for source in record.get('sources',[{'name':'Verified final source','url':status['source_url']}]):st.link_button(source['name'],source['url'])
    return True
