"""Shared product styling. No model, forecast or data-loading behavior."""
import streamlit as st


def render_product_styles():
    st.markdown('''<style>
.stApp{background:radial-gradient(ellipse at 90% 0,#14243b80,transparent 38%),#080b10}
.block-container{max-width:1180px;padding-top:1.25rem;padding-bottom:4rem}
/* Style and script-only blocks need no space in the content stack. */
[data-testid="stElementContainer"]:has(style):not(:has(h1,h2,h3,table,.bp-mini,.hero)){display:none}
[data-testid="stElementContainer"]:has(>.stHtml script){display:none}
[data-testid="stElementContainer"]:has(#bp-board-top){display:contents}
#bp-board-top{position:absolute;top:0}
.stMainBlockContainer [data-testid="stVerticalBlock"]{gap:12px}
.bp-nav{padding:4px 0 18px;border-bottom:1px solid #253247;margin-bottom:18px}
.bp-logo{gap:12px}.bp-mark{width:46px;height:46px;border-radius:14px;background:#182f4c;border:1px solid #42658c;color:#c2dcff;box-shadow:none;font-size:1.1rem}
.bp-wordmark{font-size:1.25rem;letter-spacing:-.04em}.bp-kicker{font-size:.57rem;color:#8ca3bd;letter-spacing:.16em;margin-top:3px}
.bp-edition{text-align:right;color:#d7e2f0;font-size:.8rem;font-weight:600}.bp-edition span{display:block;color:#849ab5;font-size:.65rem;margin-top:3px;font-weight:400}
.st-key-bp_sport{width:100%!important}
.st-key-bp_sport [data-testid="stRadioGroup"]{display:grid!important;grid-template-columns:1.35fr repeat(5,minmax(0,1fr))!important;gap:6px!important;width:100%!important}
.st-key-bp_sport [data-testid="stRadioGroup"]>div{width:100%!important;min-width:0}
.st-key-bp_sport [data-testid="stRadioOption"]{width:100%!important;min-width:0!important;min-height:44px;justify-content:center;border:1px solid #2a3c52!important;border-radius:11px!important;background:#101a28!important;padding:10px 6px!important;box-sizing:border-box}
.st-key-bp_sport [data-testid="stRadioOption"][data-selected="true"]{background:#203e62!important;border-color:#78a7df!important;box-shadow:0 0 0 1px #78a7df25}
.st-key-bp_sport label p{font-size:.83rem;font-weight:650}
.board-intro{padding:16px 0 8px}.board-eyebrow{font-size:.62rem;letter-spacing:.17em;color:#84abd7;font-weight:700;margin-bottom:8px}
.board-intro h1{font-size:clamp(1.65rem,4vw,2.25rem);line-height:1.12;letter-spacing:-.045em;font-weight:750;margin:0;padding:0;color:#f1f5fb}
.board-intro p{font-size:.91rem;line-height:1.6;color:#a7b7cc;margin:10px 0 0}
[data-testid="stTabs"] [role="tablist"]{gap:12px;border-bottom:1px solid #2b3a50;margin-top:6px}
[data-testid="stTabs"] [role="tab"]{font-size:.73rem;min-height:46px;padding:9px 2px;font-weight:650;letter-spacing:.025em}
.st-key-bp_toolbar{padding-bottom:6px}.st-key-bp_toolbar [data-testid="stButton"] button{min-height:42px;border-radius:10px}
[data-testid="stWidgetLabel"]{background:transparent!important;border:0!important;padding:0!important;min-height:0!important}
.st-key-desk_status [data-testid="stWidgetLabel"]{display:none!important}
.st-key-desk_status{width:100%!important}
.st-key-desk_status [data-testid="stRadioGroup"]{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
.st-key-desk_status [data-testid="stRadioGroup"]>div{display:flex}
.st-key-desk_status [data-testid="stRadioOption"]{border-radius:10px;padding:8px 5px;background:#101b2b;border:1px solid #293e58;min-height:44px;width:100%;justify-content:center}
.st-key-desk_status [data-testid="stRadioOption"]>div{width:100%;justify-content:center}
.st-key-desk_status [data-testid="stRadioOption"][data-selected="true"]{background:#254a75;border-color:#8ab5e7}
.st-key-desk_status [data-testid="stRadioOption"] p{font-size:.72rem;text-align:center;line-height:1.4}
.st-key-desk_status [data-testid="stRadioOption"]>div>div:first-child:not([data-testid="stMarkdownContainer"]),.st-key-bp_sport [data-testid="stRadioOption"]>div>div:first-child:not([data-testid="stMarkdownContainer"]){display:none}
.bp-mini{padding:18px;border-radius:18px;border:1px solid #2d4058;border-left:3px solid var(--bp-pick);box-shadow:0 5px 22px #00000018;transition:border-color .15s,box-shadow .15s}
.bp-mini:hover{border-color:#587aa1;box-shadow:0 7px 25px #00000035}
.bp-mini-top{font-size:.72rem;color:#a7bdd8;line-height:1.4;margin-bottom:13px}
.bp-mini-team{margin:11px 0;gap:11px}.bp-mini-name{font-size:.98rem;line-height:1.35;font-weight:650}
.bp-mini-badge{width:34px;height:34px;flex-basis:34px;border-radius:10px}.bp-mini-team strong{font-size:1.25rem;font-variant-numeric:tabular-nums}
.bp-mini-pick{padding-top:13px;margin-top:15px}.bp-mini-selected{font-size:.6rem;letter-spacing:.04em}.bp-mini-selected b{font-size:.95rem;letter-spacing:0;line-height:1.4}
.bp-mini-selected small{font-size:.71rem;letter-spacing:0}.bp-mini-confidence b{font-size:1.35rem;font-variant-numeric:tabular-nums}.bp-mini-confidence small{font-size:.53rem;letter-spacing:.04em}
.bp-mini-bar{height:4px;margin-top:13px}.bp-mini-link{display:flex;justify-content:space-between;gap:8px;color:#afccee;font-size:.73rem;border-top:1px solid #2b3e5633;margin-top:13px;padding-top:10px}
[class*="st-key-bp_game_tile_"] button:focus-visible{outline:3px solid #a8cbff!important;outline-offset:3px!important}
.story-compare{border:1px solid #30435d;border-radius:15px;overflow:hidden;margin:20px 0 10px;background:#0f1b2b}
.story-compare-head,.story-compare-row{display:grid;grid-template-columns:minmax(0,1.2fr) repeat(2,minmax(0,1fr));align-items:center;gap:12px;padding:13px 16px}
.story-compare-head{background:#1a2c43;color:#c8d9ee;font-size:.75rem}.story-compare-head span{font-size:.58rem;letter-spacing:.06em;color:#92accd}
.story-compare-head b{overflow-wrap:anywhere;line-height:1.4;text-align:right}.story-compare-row{border-top:1px solid #293b52;font-size:.83rem;color:#aebfd3}.story-compare-row strong{font-size:.95rem;color:#eef4ff;text-align:right;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
[role="dialog"]{max-width:780px;width:calc(100vw - 32px);border:1px solid #354b68;border-radius:20px;background:#0d1521}
[role="dialog"] [data-testid="stMetricValue"]{font-size:1.5rem;white-space:normal!important;overflow:visible!important;text-overflow:clip;overflow-wrap:anywhere;line-height:1.3}[role="dialog"] [data-testid="stMarkdownContainer"] p{line-height:1.75;color:#c8d5e5}
[role="dialog"] h4{font-size:1.25rem;letter-spacing:-.025em;padding-top:8px}
@media(max-width:640px){
.block-container{padding:1rem .95rem 3rem}.bp-nav{margin-bottom:14px;padding-bottom:15px}.bp-wordmark{font-size:1.08rem}.bp-mark{width:39px;height:39px;border-radius:12px}.bp-kicker{font-size:.49rem}.bp-edition{font-size:.7rem}
.st-key-bp_sport [data-testid="stRadioOption"]{padding:9px 3px!important}.st-key-bp_sport label p{font-size:.72rem}
.board-intro{padding:12px 0 6px}.board-intro p{font-size:.82rem;margin-top:8px}.board-eyebrow{font-size:.57rem}
[data-testid="stTabs"] [role="tablist"]{gap:5px}[data-testid="stTabs"] [role="tab"]{font-size:.65rem;padding:8px 3px}
.bp-mini{padding:15px;border-radius:16px}.bp-mini-name{font-size:.94rem}.bp-mini-pick{margin-top:12px}.bp-mini-link{font-size:.72rem}
.story-compare-head,.story-compare-row{padding:11px 10px;gap:8px;grid-template-columns:minmax(0,1.15fr) repeat(2,minmax(0,1fr))}.story-compare-row{font-size:.72rem}.story-compare-row strong{font-size:.84rem}.story-compare-head{font-size:.68rem}
[role="dialog"]{width:calc(100vw - 16px);border-radius:16px}[role="dialog"] [data-testid="stMetricValue"]{font-size:1.2rem}
}
@media(prefers-reduced-motion:reduce){.bp-mini{transition:none}}
</style>''',unsafe_allow_html=True)
