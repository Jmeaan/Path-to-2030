"""Animista-style CSS animations + dark 'mission control' theme for Path to 2030."""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');

:root { --neon:#facc15; --cyan:#22d3ee; --pink:#f472b6; --bg:#0b1020; --card:rgba(255,255,255,.04); }
html, body, [class*="css"], .stApp { font-family:'Space Grotesk', sans-serif; }
.stApp { background: radial-gradient(1200px 600px at 10% -10%, rgba(250,204,21,.12), transparent 60%),
                     radial-gradient(900px 500px at 110% 10%, rgba(34,211,238,.12), transparent 60%), var(--bg); }

/* ---------- Animista keyframes ---------- */
@keyframes text-focus-in { 0%{filter:blur(12px);opacity:0} 100%{filter:blur(0);opacity:1} }
@keyframes slide-in-bottom { 0%{transform:translateY(40px);opacity:0} 100%{transform:translateY(0);opacity:1} }
@keyframes scale-in-center { 0%{transform:scale(.85);opacity:0} 100%{transform:scale(1);opacity:1} }
@keyframes tracking-in-expand { 0%{letter-spacing:-.5em;opacity:0} 40%{opacity:.6} 100%{opacity:1} }
@keyframes pulsate-fwd { 0%,100%{transform:scale(1)} 50%{transform:scale(1.06)} }
@keyframes gradient-shift { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
@keyframes shimmer { 0%{transform:translateX(-100%)} 100%{transform:translateX(100%)} }
@keyframes glow { 0%,100%{box-shadow:0 0 0 rgba(250,204,21,0)} 50%{box-shadow:0 0 28px rgba(250,204,21,.35)} }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.25} }
@keyframes count { from{--n:0} }

/* ---------- Hero ---------- */
.hero { position:relative; overflow:hidden; padding:28px 32px; border-radius:22px; margin-bottom:18px;
        border:1px solid rgba(255,255,255,.08); background:linear-gradient(135deg,rgba(250,204,21,.08),rgba(34,211,238,.06));
        animation: scale-in-center .7s cubic-bezier(.25,.46,.45,.94) both; }
.hero::after { content:""; position:absolute; inset:0; background:linear-gradient(90deg,transparent,rgba(255,255,255,.06),transparent);
               animation: shimmer 3.5s infinite; }
.hero h1 { margin:0; font-size:3rem; font-weight:700; line-height:1.05;
           background:linear-gradient(90deg,var(--neon),var(--cyan),var(--pink),var(--neon)); background-size:300% 100%;
           -webkit-background-clip:text; background-clip:text; color:transparent;
           animation: tracking-in-expand .9s cubic-bezier(.215,.61,.355,1) both, gradient-shift 6s ease infinite; }
.hero p { color:#cbd5e1; margin:.5rem 0 0; animation: text-focus-in 1s .3s both; }
.badge { display:inline-block; padding:4px 12px; border-radius:999px; font-size:.75rem; font-weight:600; margin-right:6px;
         background:rgba(250,204,21,.15); color:var(--neon); border:1px solid rgba(250,204,21,.35); animation: slide-in-bottom .6s .5s both; }
.live { color:#4ade80; animation: blink 1.4s infinite; }

/* ---------- Big clock cards ---------- */
.clock-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin:6px 0 18px; }
.clock { padding:20px; border-radius:18px; background:var(--card); border:1px solid rgba(255,255,255,.08);
         animation: slide-in-bottom .6s cubic-bezier(.25,.46,.45,.94) both; transition: transform .25s, border-color .25s; }
.clock:hover { transform: translateY(-4px); border-color: rgba(250,204,21,.5); animation: glow 2s infinite; }
.clock .k { color:#94a3b8; font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; }
.clock .v { font-size:2.4rem; font-weight:700; color:#f8fafc; }
.clock .s { font-size:.9rem; }
.late { color:#f87171; } .ok { color:#4ade80; }
.clock.alert .v { color:#f87171; animation: pulsate-fwd 1.8s ease-in-out infinite; }

/* ---------- Streamlit widgets ---------- */
[data-testid="stMetric"] { background:var(--card); border:1px solid rgba(255,255,255,.08); border-radius:16px; padding:14px 16px;
                           animation: scale-in-center .5s both; transition: transform .2s, border-color .2s; }
[data-testid="stMetric"]:hover { transform: translateY(-3px); border-color: rgba(34,211,238,.6); }
[data-testid="stMetricValue"] { color:#f8fafc; }
.stTabs [data-baseweb="tab-list"] { gap:6px; }
.stTabs [data-baseweb="tab"] { border-radius:12px 12px 0 0; padding:10px 16px; transition: background .2s; }
.stTabs [aria-selected="true"] { background:rgba(250,204,21,.12); }
.stTabs [data-baseweb="tab-panel"] { animation: text-focus-in .5s both; }
[data-testid="stPlotlyChart"], [data-testid="stDataFrame"] { animation: slide-in-bottom .6s both; }
.stButton button, .stFormSubmitButton button { border-radius:12px; transition: transform .15s, box-shadow .15s; }
.stButton button:hover, .stFormSubmitButton button:hover { transform: translateY(-2px); box-shadow:0 0 18px rgba(250,204,21,.4); }
h2, h3, h4 { animation: text-focus-in .6s both; }
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(n_countries: int, y0: int, y1: int, off_track: int):
    st.markdown(f"""
<div class="hero">
  <span class="badge">AI FOR GOOD</span><span class="badge">SDG 7</span><span class="badge">7.1.1 · 7.1.2</span>
  <h1>⚡ Path to 2030</h1>
  <p>Find who solved it before you, see when you'll get there, know what it costs, and log real projects that move the clock.</p>
  <p><span class="live">●</span> UN SDG data · {n_countries} countries · {y0}–{y1} ·
     <b style="color:#f87171">{off_track}</b> countries off track for 2030</p>
</div>""", unsafe_allow_html=True)


def clock_cards(cards):
    """cards: list of (label, value, subtitle, is_late)"""
    html = '<div class="clock-grid">'
    for i, (k, v, s, late) in enumerate(cards):
        html += (f'<div class="clock{" alert" if late else ""}" style="animation-delay:{i * .12:.2f}s">'
                 f'<div class="k">{k}</div><div class="v">{v}</div>'
                 f'<div class="s {"late" if late else "ok"}">{s}</div></div>')
    st.markdown(html + "</div>", unsafe_allow_html=True)
