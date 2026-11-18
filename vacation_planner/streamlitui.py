"""Simple vacation planning UI with the portfolio's dark, colorful theme."""
from datetime import datetime
import re
import streamlit as st

st.set_page_config(page_title="AI Vacation Planner", page_icon="\u2708\ufe0f", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600;700&display=swap');
.stApp {
 background:radial-gradient(ellipse 650px 480px at 10% 0%,#fa6f0014,transparent),radial-gradient(ellipse 650px 650px at 100% 70%,#c300e00c,transparent),#0f141a;
 color:#f3f3f7;
 font-family:'IBM Plex Mono',monospace;
}
[data-testid="stHeader"] { background:transparent; }
.block-container { max-width:850px; padding:3.5rem 1.5rem 3rem; }
h1,h2,h3 { font-family:Inter,Arial,sans-serif; color:#f3f3f7; }
.intro { text-align:center; padding:15px 0 28px; }
.intro h1 { font-size:clamp(32px,5vw,46px); font-weight:600; letter-spacing:-1.8px; line-height:1.2; margin:0 0 18px; padding:0; }
.intro h1 span { background:linear-gradient(110deg,#fa6f00,#e433ff); background-clip:text; -webkit-background-clip:text; color:transparent; }
.intro p { color:#b8bbc4; font-size:14px; line-height:1.9; max-width:580px; margin:auto; }
.st-key-planner { max-width:620px; margin:0 auto; padding:26px; border:1px solid #ffffff14; border-radius:10px; background:linear-gradient(130deg,#ffffff04,#ffffff02); }
.st-key-planner h2 { font-size:21px; font-weight:500; letter-spacing:-.5px; padding-top:0; }
.st-key-planner [data-testid="stForm"] { border:0; padding:0; }
[data-testid="stTextInput"] input { background:#161d26; color:#f3f3f7; border-radius:6px; }
[data-testid="stTextInput"] input::placeholder { color:#9ca4b1; }
[data-testid="stFormSubmitButton"] button { background:#fa6f00; color:#0f141a; border:0; border-radius:6px; min-height:44px; font-weight:600; }
[data-testid="stFormSubmitButton"] button:hover { background:#ff903d; color:#0f141a; }
.features { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; margin:32px auto 28px; max-width:700px; text-align:center; }
.feature { padding:15px 9px; }
.feature-icon { font-size:26px; display:block; margin-bottom:12px; }
.feature h3 { font-size:14px; font-weight:500; color:#f8c7ff; padding:0; margin:0 0 8px; }
.feature p { font-size:11px; color:#b8bbc4; line-height:1.8; margin:0; }
.st-key-plan-result { border-top:1px solid #ffffff14; padding-top:24px; margin-top:12px; }
.st-key-plan-result h2 { font-size:27px; font-weight:500; }
a { color:#ffc0ad; }
@media(max-width:600px) {
 .block-container { padding:2.6rem 1rem 2rem; }
 .st-key-planner { padding:22px; }
 .intro h1 { letter-spacing:-1px; }
 .intro p { font-size:12px; }
 .features { gap:8px; }
 .feature { padding:12px 2px; }
 .feature h3 { font-size:12px; }
 .feature p { font-size:10px; }
}
</style>
""", unsafe_allow_html=True)


def create_plan(destination: str) -> str:
    # Providers and credentials are initialized only when a plan is requested.
    from vacation_planner.crew import VacationPlanner
    result = VacationPlanner().crew().kickoff(
        inputs={"topic": destination, "current_year": str(datetime.now().year)}
    )
    content = getattr(result, "raw", None) or str(result)
    if not content.strip():
        raise ValueError("The planner returned an empty itinerary.")
    return content


st.session_state.setdefault("plan", None)
st.markdown("""
<div class="intro">
 <h1>AI <span>Vacation Planner</span></h1>
 <p>Find places to visit, local food to try, and the stories behind your destination.
 Turn it all into a simple travel plan.</p>
</div>
""", unsafe_allow_html=True)

with st.container(key="planner"):
    st.subheader("Where would you like to go?")
    with st.form("vacation_form", border=False):
        destination = st.text_input("Destination", placeholder="e.g. London, Paris, Tokyo", max_chars=120, key="destination_input")
        submitted = st.form_submit_button("Plan my trip", type="primary", width="stretch")
    if submitted and not destination.strip():
        st.warning("Enter a city or country to start your plan.")

st.markdown("""
<div class="features">
 <div class="feature"><span class="feature-icon" aria-hidden="true">&#x1F5FA;&#xFE0F;</span><h3>Places to visit</h3><p>Find attractions and interesting places to explore.</p></div>
 <div class="feature"><span class="feature-icon" aria-hidden="true">&#x1F35C;</span><h3>Local food</h3><p>Discover regional dishes and flavors worth trying.</p></div>
 <div class="feature"><span class="feature-icon" aria-hidden="true">&#x1F3DB;&#xFE0F;</span><h3>Culture &amp; history</h3><p>Get to know the stories behind your destination.</p></div>
</div>
""", unsafe_allow_html=True)

if submitted and destination.strip():
    with st.spinner("Researching your destination and creating your plan..."):
        try:
            content = create_plan(destination.strip())
        except Exception:
            # Provider exceptions can contain sensitive details. Do not display them.
            st.error("We couldn't create your plan right now. Please try again in a moment.")
        else:
            st.session_state["plan"] = {"destination": destination.strip(), "content": content}

plan = st.session_state["plan"]
if plan:
    with st.container(key="plan-result"):
        st.subheader(f"Your {plan['destination']} travel plan")
        st.markdown(plan["content"])
        filename = re.sub(r"[^\w-]+", "_", plan["destination"], flags=re.UNICODE).strip("_") or "vacation"
        st.download_button("Download your plan", data=plan["content"], file_name=f"{filename}_travel_plan.md", mime="text/markdown", on_click="ignore")
        st.caption("AI-generated suggestions. Confirm opening hours, availability, and prices before traveling.")
