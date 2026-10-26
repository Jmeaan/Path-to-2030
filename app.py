"""
Path to 2030 - AI for Good (SDG 7: Affordable and Clean Energy)
Run:  streamlit run app.py
"""
import os
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import engine as E
import ui

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
PROJECTS = os.path.join(DATA_DIR, "projects.csv")
os.makedirs(DATA_DIR, exist_ok=True)

st.set_page_config(page_title="Path to 2030", page_icon="⚡", layout="wide")


def fmt_year(y):
    if y is None or (isinstance(y, float) and (np.isnan(y) or np.isinf(y))):
        return "Not at this pace"
    return "After 2100" if y > 2100 else str(int(np.ceil(y)))


def late_text(y):
    if y is None or (isinstance(y, float) and (np.isnan(y) or np.isinf(y))):
        return "Off track: no progress trend"
    yy = int(np.ceil(y))
    return "On track ✅" if yy <= E.DEADLINE else f"{yy - E.DEADLINE} years late"


def money(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    for unit, div in [("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if abs(x) >= div:
            return f"${x / div:,.1f}{unit}"
    return f"${x:,.0f}"


@st.cache_data(show_spinner="Training models on UN data…")
def load(stamp):
    panel = E.load_panel(DATA_DIR)
    return panel, E.all_status(panel)


def data_stamp():
    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv") and not f.startswith("projects")]
    return tuple(sorted((f, os.path.getmtime(os.path.join(DATA_DIR, f))) for f in files))


# ---------------------------------------------------------------- header
ui.inject()
px.defaults.template = "plotly_dark"

# ---------------------------------------------------------------- data
try:
    panel, status_all = load(data_stamp())
except FileNotFoundError as e:
    st.warning(f"{e}. Upload the UN SDG CSVs for indicators 7.1.1 and 7.1.2 below "
               "(unstats.un.org/sdgs/dataportal → indicator → all countries, all years → Download CSV).")
    ups = st.file_uploader("UN SDG CSV files", type="csv", accept_multiple_files=True)
    if ups:
        for u in ups:
            with open(os.path.join(DATA_DIR, u.name), "wb") as f:
                f.write(u.getbuffer())
        st.cache_data.clear()
        st.rerun()
    st.stop()

countries = sorted(status_all.country)
projects = E.load_projects(PROJECTS)
ui.hero(panel.country.nunique(), int(panel.year.min()), int(panel.year.max()),
        int((status_all.years_late > 0).sum()))

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Your country")
    default = countries.index("Nigeria") if "Nigeria" in countries else 0
    country = st.selectbox("Country", countries, index=default)
    pop_m = st.number_input("Population (millions)", min_value=0.1, value=50.0, step=1.0,
                            help="Used to turn percentages into households, costs and project impact. "
                                 "Enter the latest official figure.")
    st.divider()
    st.caption(f"Data: {panel.country.nunique()} countries · {panel.year.min()}–{panel.year.max()}")
    st.caption(f"Projects logged: {len(projects)}")

S = E.country_status(panel, country)
twins, _ = E.find_twins(panel, country, k=5)
paths = E.path_forecast(S, twins) if not twins.empty else pd.DataFrame()
my_projects = projects[projects.country == country]
elec_people = my_projects[my_projects.type.isin(["Grid extension", "Solar mini-grid", "Solar home systems"])].people.sum()
cook_people = my_projects[my_projects.type.isin(["Clean cookstoves", "LPG / gas cooking", "Electric cooking"])].people.sum()
fx_e = E.project_effect(S, elec_people, pop_m, "elec")
fx_c = E.project_effect(S, cook_people, pop_m, "cook")

tabs = st.tabs(["🕐 Deadline Clock", "🧭 Path Finder", "💰 Impact Simulator",
                "📍 Impact Map", "🚨 Gap Alerts", "🔄 Update Data"])

# ================================================================ 1. CLOCK
with tabs[0]:
    st.subheader(f"{country}: where you are and when you'll get there")
    def _late(y):
        return not (np.isfinite(y) and np.ceil(y) <= E.DEADLINE)
    ui.clock_cards([
        ("⚡ Electricity today", f"{S['elec']:.0f}%", f"{S['elec_gain']:+.2f} pts / year", S["elec_gain"] <= 0),
        ("⚡ 100% electricity", fmt_year(S["elec_eta"]), late_text(S["elec_eta"]), _late(S["elec_eta"])),
        ("🔥 Clean cooking today", f"{S['cook']:.0f}%", f"{S['cook_gain']:+.2f} pts / year", S["cook_gain"] <= 0),
        ("🔥 100% clean cooking", fmt_year(S["cook_eta"]), late_text(S["cook_eta"]), _late(S["cook_eta"])),
    ])
    c1, c2 = st.columns(2)
    for col, key, label, fx in [(c1, "elec", "Electricity access (7.1.1)", fx_e),
                                (c2, "cook", "Clean cooking (7.1.2)", fx_c)]:
        with col:
            if fx["pp"] > 0:
                d = fx["days"]
                st.success(f"Logged projects add **+{fx['pp']:.2f} pts**"
                           + (f" and move the deadline **{d:,.0f} days** closer." if not np.isnan(d) else "."))
    g = panel[panel.country == country]
    fig = go.Figure()
    fig.add_scatter(x=g.year, y=g.elec, name="Electricity %", mode="lines+markers")
    fig.add_scatter(x=g.year, y=g.cook, name="Clean cooking %", mode="lines+markers")
    for key, name in [("elec", "Electricity trend"), ("cook", "Cooking trend")]:
        eta = S[key + "_eta"]
        end = min(eta if np.isfinite(eta) else 2060, 2060)
        xs = np.arange(S["year"], int(np.ceil(end)) + 1)
        fig.add_scatter(x=xs, y=np.clip(S[key] + S[key + "_gain"] * (xs - S["year"]), 0, 100),
                        name=name + " (forecast)", line=dict(dash="dot"))
    fig.add_vline(x=E.DEADLINE, line_dash="dash", annotation_text="2030 deadline")
    fig.update_layout(height=420, yaxis_title="% of population", yaxis_range=[0, 105], legend_orientation="h")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Forecast = linear regression on the last 10 years of UN data. It shows the current pace, not a guarantee. "
               "Backtest: trained on data up to 2019, it predicted 2024 levels for 194 countries with an average error "
               "of about 1.7 percentage points (median 0.04 for electricity, 1.0 for clean cooking).")

# ================================================================ 2. PATH FINDER
with tabs[1]:
    st.subheader("Who was where you are now, and how did they move forward?")
    st.caption("K-Nearest Neighbours compares your country today (electricity %, cooking %, and 5-year speed of both) "
               "with every country's past. Fit score = how close the match is.")
    if twins.empty:
        st.info("Not enough history to find twins for this country.")
    else:
        show = twins.copy()
        show["Matched year"] = show.matched_year
        show["Then: electricity %"] = show.elec_then.round(1)
        show["Then: cooking %"] = show.cook_then.round(1)
        show["Electricity gain / yr after"] = show.elec_gain_after.round(2)
        show["Cooking gain / yr after"] = show.cook_gain_after.round(2)
        st.dataframe(show[["twin", "Matched year", "Then: electricity %", "Then: cooking %", "path",
                           "Electricity gain / yr after", "Cooking gain / yr after", "fit"]]
                     .rename(columns={"twin": "Twin country", "path": "Path taken", "fit": "Fit"}),
                     hide_index=True, use_container_width=True)

        # Trajectories aligned to "years after matching"
        lines = []
        for _, t in twins.iterrows():
            f = panel[(panel.country == t.twin) & (panel.year >= t.matched_year)].head(E.HORIZON + 1)
            lines.append(f.assign(after=f.year - t.matched_year, who=f"{t.twin} (from {t.matched_year})"))
        traj = pd.concat(lines)
        metric = st.radio("Show path for", ["elec", "cook"], horizontal=True,
                          format_func=lambda m: "Electricity" if m == "elec" else "Clean cooking")
        fig = px.line(traj, x="after", y=metric, color="who", markers=True,
                      labels={"after": "Years after being where you are now", metric: "%"})
        fig.add_hline(y=S[metric], line_dash="dot", annotation_text=f"{country} today")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Deadline Clock under each path")
        st.caption("**If copied exactly** = your country moves at the twin's speed. "
                   "**Realistic for you** = the twin's speed blended with your own pace, weighted by fit, "
                   "because what worked for them may not fully work for you.")
        tbl = pd.DataFrame({
            "Twin": paths.twin, "Path": paths.path, "Fit": paths.fit,
            "Electricity 100%: copied": paths.elec_eta_copy.map(fmt_year),
            "Electricity 100%: realistic": paths.elec_eta_real.map(fmt_year),
            "Cooking 100%: copied": paths.cook_eta_copy.map(fmt_year),
            "Cooking 100%: realistic": paths.cook_eta_real.map(fmt_year),
        })
        mine = pd.DataFrame([{"Twin": "— Your current pace —", "Path": "", "Fit": "",
                              "Electricity 100%: copied": fmt_year(S["elec_eta"]),
                              "Electricity 100%: realistic": fmt_year(S["elec_eta"]),
                              "Cooking 100%: copied": fmt_year(S["cook_eta"]),
                              "Cooking 100%: realistic": fmt_year(S["cook_eta"])}])
        st.dataframe(pd.concat([mine, tbl]), hide_index=True, use_container_width=True)
        best = paths.assign(score=np.maximum(paths.elec_eta_real, paths.cook_eta_real)).sort_values("score").iloc[0]
        st.info(f"**Most promising realistic path:** follow **{best.twin}** ({best.path}, fit {best.fit}). "
                f"Full access around **{fmt_year(max(best.elec_eta_real, best.cook_eta_real))}**. "
                "Try it in the Impact Simulator tab to see the cost and trade-offs.")
        st.caption("UN data shows how fast and in what order countries improved, not which policies they used. "
                   "Field remarks in the Impact Map add that missing context over time.")

# ================================================================ 3. SIMULATOR
with tabs[2]:
    st.subheader("What would it cost, and what should we expect?")
    st.caption("All economic numbers are **assumptions you can edit** (defaults are illustrative). "
               "Replace them with local figures or World Bank / IEA benchmarks.")
    a = dict(E.DEFAULT_ASSUMPTIONS)
    if not paths.empty:
        opts = ["Current pace"] + [f"{r.twin}: {r.path} (realistic)" for r in paths.itertuples()]
        choice = st.selectbox("Path to plan for", opts)
        if choice == "Current pace":
            eta = max(S["elec_eta"], S["cook_eta"])
        else:
            r = paths.iloc[opts.index(choice) - 1]
            eta = max(r.elec_eta_real, r.cook_eta_real)
    else:
        eta = max(S["elec_eta"], S["cook_eta"])
    default_years = int(np.clip(np.ceil(eta) - S["year"], 1, 40)) if np.isfinite(eta) else 15
    years = st.slider("Years to reach full access", 1, 40, default_years)

    with st.expander("✏️ Edit assumptions", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Electricity mix (%)**")
            a["share_grid"] = st.slider("Grid extension", 0, 100, 40)
            a["share_minigrid"] = st.slider("Solar mini-grids", 0, 100, 30)
            a["share_solar"] = st.slider("Solar home systems", 0, 100, 30)
            a["household_size"] = st.number_input("People per household", 1.0, 12.0, a["household_size"])
        with c2:
            st.markdown("**Costs (USD per household)**")
            a["cost_grid"] = st.number_input("Grid connection", 0.0, 10000.0, a["cost_grid"])
            a["cost_minigrid"] = st.number_input("Mini-grid connection", 0.0, 10000.0, a["cost_minigrid"])
            a["cost_solar"] = st.number_input("Solar home system", 0.0, 5000.0, a["cost_solar"])
            a["cost_cookstove"] = st.number_input("Clean cooking setup", 0.0, 2000.0, a["cost_cookstove"])
            a["household_copay"] = st.slider("Share paid by households", 0.0, 1.0, a["household_copay"])
            a["energy_budget"] = st.number_input("National energy budget per year (USD, optional)", 0.0, 1e12, 0.0)
        with c3:
            st.markdown("**Side effects**")
            a["jobs_per_million"] = st.number_input("Jobs per $1M invested", 0.0, 500.0, a["jobs_per_million"])
            a["grid_upgrade_area_share"] = st.slider("Share of homes in grid-upgrade areas", 0.0, 1.0, a["grid_upgrade_area_share"])
            a["outage_days_per_year"] = st.number_input("Planned outage days / yr during works", 0, 60, a["outage_days_per_year"])
            a["charcoal_spend_per_hh"] = st.number_input("Charcoal/firewood spend per household / yr", 0.0, 2000.0, a["charcoal_spend_per_hh"])
            a["lpg_share"] = st.slider("Share switching to LPG gas", 0.0, 1.0, a["lpg_share"])
            a["lpg_price_per_kg"] = st.number_input("Imported LPG price per kg (USD)", 0.0, 10.0, a["lpg_price_per_kg"])
            a["health_saving_per_hh"] = st.number_input("Health cost avoided per household / yr", 0.0, 1000.0, a["health_saving_per_hh"])

    R = E.simulate(pop_m, S["elec"], S["cook"], years, a)
    st.markdown("#### 💵 Budget")
    m = st.columns(4)
    m[0].metric("Total investment", money(R["total_cost"]))
    m[1].metric("Per year", money(R["cost_per_year"]))
    m[2].metric("Share of energy budget / yr", f"{R['budget_share']:.0%}" if not np.isnan(R["budget_share"]) else "Add budget")
    m[3].metric("Benefits cover costs by", f"Year {R['breakeven_year']}" if R["breakeven_year"] else "Beyond horizon")

    st.markdown("#### ✅ Who gains")
    m = st.columns(4)
    m[0].metric("Households getting power", f"{R['hh_no_power']:,.0f}")
    m[1].metric("Households cooking clean", f"{R['hh_dirty']:,.0f}")
    m[2].metric("Jobs created", f"{R['jobs']:,.0f}")
    m[3].metric("Health + fuel savings / yr", money(R["health_saving"] + R["fuel_saving"]))

    st.markdown("#### ⚠️ Who or what gets disrupted")
    m = st.columns(3)
    m[0].metric("Homes facing planned outages", f"{R['outage_households']:,.0f}",
                f"~{a['outage_days_per_year']} days/yr during works", delta_color="off")
    m[1].metric("Income lost by charcoal/firewood sellers / yr", money(R["seller_income_lost"]),
                "needs retraining / support", delta_color="off")
    m[2].metric("Extra LPG import bill / yr", money(R["lpg_import_bill"]),
                "pressure on foreign currency", delta_color="off")

    st.markdown("#### 📅 What to expect, year by year")
    tl = R["timeline"]
    fig = go.Figure()
    fig.add_bar(x=tl.year, y=tl.spending, name="Spending")
    fig.add_bar(x=tl.year, y=tl.benefits, name="Benefits")
    fig.add_scatter(x=tl.year, y=tl.cum_benefits - tl.cum_spending, name="Net position (cumulative)", yaxis="y")
    fig.update_layout(barmode="group", height=380, xaxis_title="Year of programme", yaxis_title="USD",
                      legend_orientation="h")
    st.plotly_chart(fig, use_container_width=True)
    phase1 = max(1, years // 3)
    st.markdown(
        f"- **Years 1–{phase1}:** heaviest spending, construction and planned outages; charcoal sellers start losing customers.\n"
        f"- **Years {phase1 + 1}–{years}:** access climbs; health and fuel savings grow each year.\n"
        f"- **Year {years + 1}+:** full access; only maintenance costs (~{a['maintenance_pct']:.0%}/yr) remain.")

# ================================================================ 4. IMPACT MAP
with tabs[3]:
    st.subheader("Log a real project and see it move the clock")
    with st.form("log", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            p_country = st.selectbox("Country", countries, index=countries.index(country))
            p_name = st.text_input("Project name", placeholder="e.g. Kano solar mini-grid")
            p_type = st.selectbox("Type", ["Solar mini-grid", "Solar home systems", "Grid extension",
                                           "Clean cookstoves", "LPG / gas cooking", "Electric cooking"])
            p_people = st.number_input("People reached", 0, 50_000_000, 5000, step=500)
        with c2:
            p_lat = st.number_input("Latitude", -90.0, 90.0, 9.08, format="%.4f")
            p_lon = st.number_input("Longitude", -180.0, 180.0, 8.68, format="%.4f")
            p_rem = st.text_area("Remarks: what worked, what didn't, problems faced",
                                 placeholder="e.g. Pay-as-you-go worked; batteries failed in the rainy season")
        if st.form_submit_button("➕ Log project", type="primary"):
            new = pd.DataFrame([{"country": p_country, "project": p_name or p_type, "type": p_type,
                                 "lat": p_lat, "lon": p_lon, "people": p_people, "remarks": p_rem,
                                 "logged_at": datetime.now().strftime("%Y-%m-%d %H:%M")}])
            pd.concat([projects, new], ignore_index=True).to_csv(PROJECTS, index=False)
            fx = E.project_effect(E.country_status(panel, p_country), p_people,
                                  pop_m if p_country == country else 0, "cook" if "cook" in p_type.lower() or "LPG" in p_type else "elec")
            st.success(f"Logged! {p_people:,} people reached in {p_country}."
                       + (f" That moves the deadline ~{fx['days']:,.0f} days closer." if fx["pp"] > 0 and not np.isnan(fx["days"]) else ""))
            st.rerun()

    projects = E.load_projects(PROJECTS)
    if projects.empty:
        st.info("No projects logged yet. Add the first one above.")
    else:
        fig = px.scatter_geo(projects, lat="lat", lon="lon", color="type", size="people",
                             hover_name="project", hover_data={"country": True, "people": ":,", "remarks": True,
                                                               "lat": False, "lon": False},
                             projection="natural earth", size_max=30)
        fig.update_layout(height=450, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("#### 📝 Lessons from the field")
        st.dataframe(projects.sort_values("logged_at", ascending=False)
                     [["logged_at", "country", "project", "type", "people", "remarks"]],
                     hide_index=True, use_container_width=True)
    st.caption("Demo storage: data/projects.csv. In production this would be a shared online database.")

# ================================================================ 5. GAP ALERTS
with tabs[4]:
    st.subheader("Countries far behind with little action on the ground")
    counts = projects.groupby("country").size()
    g = status_all.copy()
    g["projects_logged"] = g.country.map(counts).fillna(0).astype(int)
    g["off_track"] = ~np.isfinite(np.maximum(g.elec_eta, g.cook_eta))
    g["sort"] = np.where(g.off_track, 999, g.years_late)
    alert = g[(g.sort > 0)].sort_values(["sort", "projects_logged"], ascending=[False, True])
    alert["Status"] = [("No progress trend" if off else f"{int(round(y))} yrs late")
                       for off, y in zip(alert.off_track, alert.years_late)]
    alert["Needs attention"] = np.where(alert.projects_logged == 0, "🚨 No projects logged", "")
    st.dataframe(alert[["country", "elec", "cook", "Status", "projects_logged", "Needs attention"]].head(25)
                 .rename(columns={"country": "Country", "elec": "Electricity %", "cook": "Clean cooking %",
                                  "projects_logged": "Projects"}).round(1),
                 hide_index=True, use_container_width=True)
    st.metric("Countries off track for 2030", f"{len(alert)} of {len(g)}")

# ================================================================ 6. UPDATE DATA
with tabs[5]:
    st.subheader("Drop in new UN data, models retrain automatically")
    st.caption("Download the latest 7.1.1 / 7.1.2 CSVs from unstats.un.org/sdgs/dataportal and upload them here. "
               "Files with the same name are replaced.")
    ups = st.file_uploader("UN SDG CSV files", type="csv", accept_multiple_files=True, key="update")
    if ups and st.button("Upload and retrain", type="primary"):
        for u in ups:
            with open(os.path.join(DATA_DIR, u.name), "wb") as f:
                f.write(u.getbuffer())
        st.cache_data.clear()
        st.success("Data updated. Models retrained.")
        st.rerun()
    st.write("Current data files:", [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")])
