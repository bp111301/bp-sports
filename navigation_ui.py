"""Reset the document's scroll only when the user changes boards."""
import streamlit as st
from uuid import uuid4

def request_top():
    st.session_state['bp_navigation_revision']=st.session_state.get('bp_navigation_revision',0)+1

def open_board(sport):
    st.session_state['bp_sport']=sport
    request_top()

def render_top_anchor():
    st.markdown('<span id="bp-board-top" aria-hidden="true"></span>',unsafe_allow_html=True)

def render_scroll_reset():
    revision=st.session_state.get('bp_navigation_revision',0)
    if revision==st.session_state.get('bp_navigation_rendered_revision',0):return
    st.session_state['bp_navigation_rendered_revision']=revision
    if 'bp_navigation_token' not in st.session_state:st.session_state['bp_navigation_token']=uuid4().hex
    identity=st.session_state['bp_navigation_token']+'-'+str(int(revision))
    # Only a server-generated token enters this trusted script. No feed text.
    with st.container(key='bp_scroll_reset'):
        st.html('''<style>.st-key-bp_scroll_reset{display:none}</style><script>
        (() => {
          const revision = "REVISION";
          if (window.__bpNavigationRevision === revision) return;
          window.__bpNavigationRevision = revision;
          const reset = () => {
            if (window.__bpNavigationRevision !== revision) return;
            const anchor = document.getElementById('bp-board-top');
            if (!anchor) return;
            anchor.scrollIntoView({block:'start', behavior:'instant'});
            for (let node = anchor.parentElement; node; node = node.parentElement) {
              if (node.scrollTop) node.scrollTop = 0;
            }
            window.scrollTo({top:0, left:0, behavior:'instant'});
          };
          requestAnimationFrame(reset);
          [80, 250, 600].forEach(delay => setTimeout(reset, delay));
        })();
        </script>'''.replace('REVISION',identity),unsafe_allow_javascript=True)
