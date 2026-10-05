import streamlit as st
import pandas as pd
st.set_page_config(page_title="B.P. Sports",page_icon="🏈",layout="wide",initial_sidebar_state="collapsed")
st.markdown('''<style>#MainMenu,footer{visibility:hidden}.block-container{max-width:1050px;padding-top:4.75rem}.brand{font-size:2.2rem;font-weight:900}.sub{opacity:.6;margin-bottom:20px}.card{background:linear-gradient(145deg,#242933,#15181e);border-top:6px solid #0076B6;border:1px solid #353b46;border-radius:20px;padding:22px;margin:15px 0}.meta{font-size:.75rem;font-weight:800;opacity:.55}.teams{display:grid;grid-template-columns:1fr auto 1fr;gap:15px;align-items:center;margin:18px 0}.team{font-size:1.5rem;font-weight:900}.right{text-align:right}.score{font-size:1.65rem;font-weight:900}.line{border-top:1px solid #343943;padding-top:15px}.label{font-size:.72rem;font-weight:800;opacity:.55}.pick{font-size:1.3rem;font-weight:900}.prow{display:flex;justify-content:space-between;font-weight:800;margin-top:12px}.bar{height:10px;background:#333842;border-radius:20px;overflow:hidden;margin:6px 0 12px}.fill{height:100%;background:linear-gradient(90deg,#0076B6,#B0B7BC)}.badge{display:inline-block;background:#303640;border-radius:20px;padding:5px 10px;font-size:.72rem;font-weight:800;margin-right:6px}.edges{margin-top:14px;font-size:.88rem;opacity:.8}@media(max-width:650px){.block-container{padding-left:14px;padding-right:14px}.card{padding:17px}.team{font-size:1.1rem}.score{font-size:1.2rem}}</style>''',unsafe_allow_html=True)

TEAM_COLORS={"DET":"#0076B6","CAR":"#0085CA","ATL":"#A71930","NO":"#D3BC8D","ARI":"#97233F","BAL":"#241773","BUF":"#00338D","CHI":"#C83803","CIN":"#FB4F14","CLE":"#FF3C00","DAL":"#003594","DEN":"#FB4F14","GB":"#203731","HOU":"#03202F","IND":"#002C5F","JAX":"#006778","KC":"#E31837","LV":"#A5ACAF","LAC":"#0080C6","LAR":"#003594","MIA":"#008E97","MIN":"#4F2683","NE":"#C60C30","NYG":"#0B2265","NYJ":"#125740","PHI":"#004C54","PIT":"#FFB612","SEA":"#69BE28","SF":"#AA0000","TB":"#D50A0A","TEN":"#4B92DB","WAS":"#5A1414"}

@st.cache_data(ttl=60)
def load(name):
    try:return pd.read_csv(name)
    except:return pd.DataFrame()
pred=load("predictions.csv"); hist=load("history.csv")
st.markdown('<div class="brand">🏈 B.P. SPORTS</div><div class="sub">Independent NFL predictions • Built to be tested</div>',unsafe_allow_html=True)
t1,t2,t3=st.tabs(["🏠 Predictions","📊 Model Record","🧠 About"])
with t1:
    if pred.empty: st.info("No predictions loaded.")
    else:
        weeks=sorted(pred.week.dropna().unique(),reverse=True); w=st.selectbox("Week",weeks,label_visibility="collapsed"); slate=pred[pred.week==w].sort_values("rank")
        st.header(f"NFL • WEEK {int(w)}")
        for _,r in slate.iterrows():
            factors=[("Offense",r.get("offense_edge",0)),("Defense",r.get("defense_edge",0)),("QB",r.get("qb_edge",0)),("Recent",r.get("recent_edge",0)),("Injuries",r.get("injury_edge",0)),("Home field",r.get("home_field_edge",0))]
            edge=" • ".join([n+" ↑" for n,v in factors if pd.notna(v) and v>.08]+[n+" ↓" for n,v in factors if pd.notna(v) and v<-.08]); pct=float(r.win_probability)
            accent=TEAM_COLORS.get(str(r['pick']),'#777777')
            html=f'''<div class="card" style="border-top-color:{accent}"><div class="meta">#{int(r["rank"])} MODEL RANK • WEEK {int(r["week"])}</div><div class="teams"><div class="team">{r["away"]}</div><div class="score">{int(r["away_score"])} - {int(r["home_score"])}</div><div class="team right">{r["home"]}</div></div><div class="line"><div class="label">B.P. MODEL PICK</div><div class="pick">{r["pick"]}</div><div class="prow"><span>WIN PROBABILITY</span><span>{pct:.0f}%</span></div><div class="bar"><div class="fill" style="width:{pct}%"></div></div><span class="badge">{str(r["confidence"]).upper()} CONFIDENCE</span><span class="badge">🔒 {str(r.get("status","LOCKED")).upper()}</span><div class="edges"><span class="label">MODEL EDGES</span><br>{edge or "Balanced matchup"}</div></div></div>'''
            st.markdown(html,unsafe_allow_html=True)
            with st.expander(f"Game breakdown • {r['away']} @ {r['home']}"):
                st.markdown("#### Model read")
                st.write(r.get("notes","No notes available."))
                st.markdown("#### Matchup factors")
                for name,value in factors:
                    if pd.isna(value) or abs(value) <= .08:
                        verdict = "Essentially even — no meaningful model advantage."
                    elif value > .08:
                        verdict = f"Advantage {r['pick']} — this factor supports the pick."
                    else:
                        verdict = f"Concern for {r['pick']} — this factor works against the pick."
                    st.markdown(f"**{name}:** {verdict}")
                negatives=[name for name,value in factors if pd.notna(value) and value < -.08]
                st.markdown("#### What could make the model wrong")
                if negatives:
                    st.write(f"The main risks to the {r['pick']} prediction are " + ", ".join(negatives) + ". Those are the areas where the opponent has the clearest path to outperform the projection.")
                else:
                    st.write("There is no single major modeled disadvantage, but turnovers, explosive plays and normal NFL game variance can still flip the result.")
                st.markdown("#### Final model call")
                st.success(f"{r['pick']} — {float(r['win_probability']):.0f}% win probability | Projected score: {r['away']} {int(r['away_score'])} - {r['home']} {int(r['home_score'])}")
        st.subheader("Sunday Update"); st.info("Final injury, QB, weather and availability changes are incorporated before a prediction is locked. After kickoff, the original prediction stays frozen.")
with t2:
    st.header("B.P. Model Record")
    if hist.empty or "correct" not in hist.columns or hist["correct"].dropna().empty: st.info("0-0 • The record starts now. Every locked prediction will be graded after the game.")
    else: st.dataframe(hist,use_container_width=True,hide_index=True)
with t3:
    st.header("How B.P. Sports Works")
    st.write("B.P. Sports predicts the game first and keeps market prices separate. The NFL model considers efficiency, quarterback play, recent performance, strength of schedule, turnovers, explosive plays, home field and meaningful personnel news.")
    st.write("Predictions are probabilistic, not guarantees. A locked pick is never rewritten after kickoff, so we can honestly measure the model over time.")
