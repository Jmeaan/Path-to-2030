"""
Path to 2030 - core engine (data + models + simulator).
Kept separate from the Streamlit UI so it can be tested on its own.

SDG 7 indicators used:
  7.1.1  EG_ELC_ACCS   Proportion of population with access to electricity (%)
  7.1.2  EG_EGY_CLEAN  Proportion of population with primary reliance on clean fuels and technology (%)
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

TARGET = 100.0          # SDG 7.1: universal access by 2030
DEADLINE = 2030

SERIES = {
    "elec": {"codes": ["EG_ACS_ELEC", "EG_ELC_ACCS"], "keys": ["7.1.1", "electricity"]},
    "cook": {"codes": ["EG_EGY_CLEAN"], "keys": ["7.1.2", "clean fuels"]},
}

# UN M49 codes for regions / groupings (not individual countries)
REGION_CODES = {
    1, 2, 5, 9, 11, 13, 14, 15, 17, 18, 19, 21, 29, 30, 34, 35, 39, 53, 54, 57,
    61, 62, 142, 143, 145, 150, 151, 154, 155, 199, 202, 419, 432, 513, 514,
    515, 517, 518, 543, 722, 738, 746, 747, 753,
}
REGION_WORDS = ["(M49)", "(MDG", "income", "excluding", "Least Developed",
                "Landlocked", "Small Island", "Sub-Saharan", "Latin America",
                "Northern America", "World", "countries", "Developed regions",
                "Developing regions"]


# --------------------------------------------------------------------------
# 1. DATA
# --------------------------------------------------------------------------
def _to_number(v):
    """UN values are sometimes text like '<5' or '>95'. Keep the number."""
    if pd.isna(v):
        return np.nan
    s = str(v).strip().replace("<", "").replace(">", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return np.nan


def _which_series(df: pd.DataFrame) -> str | None:
    text = " ".join(str(x) for col in ["SeriesCode", "Indicator", "SeriesDescription"]
                    if col in df.columns for x in df[col].dropna().unique()[:5])
    for key, spec in SERIES.items():
        if any(c in text for c in spec["codes"]):
            return key
    low = text.lower()
    for key, spec in SERIES.items():
        if any(k.lower() in low for k in spec["keys"]):
            return key
    return None


def _clean_one(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    # Keep national totals only (drop urban / rural splits)
    for col in ["Location", "[Location]"]:
        if col in df.columns:
            mask = df[col].astype(str).str.upper().isin(["ALLAREA", "TOTAL", "NAN", ""])
            if mask.any():
                df = df[mask]
    df["value"] = df["Value"].map(_to_number)
    df["year"] = pd.to_numeric(df["TimePeriod"], errors="coerce")
    df["code"] = pd.to_numeric(df["GeoAreaCode"], errors="coerce")
    df["country"] = df["GeoAreaName"].astype(str).str.strip()
    df = df.dropna(subset=["value", "year"])
    # Drop regions / groupings
    is_region = df["code"].isin(REGION_CODES) | df["country"].apply(
        lambda n: any(w.lower() in n.lower() for w in REGION_WORDS))
    df = df[~is_region]
    df["year"] = df["year"].astype(int)
    return df.groupby(["country", "year"], as_index=False)["value"].mean()


def load_panel(data_dir: str) -> pd.DataFrame:
    """Read every UN CSV in data_dir, detect 7.1.1 / 7.1.2, merge to one table:
    country | year | elec | cook   (one row per country per year)"""
    parts = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "*.csv"))):
        if os.path.basename(path).startswith("projects"):
            continue
        try:
            raw = pd.read_csv(path, low_memory=False)
        except Exception:
            raw = pd.read_csv(path, low_memory=False, encoding="latin-1")
        if not {"GeoAreaName", "TimePeriod", "Value"}.issubset({c.strip() for c in raw.columns}):
            continue
        key = _which_series(raw)
        if key:
            parts.setdefault(key, []).append(_clean_one(raw))
    if "elec" not in parts or "cook" not in parts:
        missing = [k for k in ("elec", "cook") if k not in parts]
        raise FileNotFoundError(
            "Missing UN data for: " + ", ".join(
                {"elec": "7.1.1 (electricity)", "cook": "7.1.2 (clean cooking)"}[m] for m in missing))
    elec = pd.concat(parts["elec"]).groupby(["country", "year"], as_index=False)["value"].mean()
    cook = pd.concat(parts["cook"]).groupby(["country", "year"], as_index=False)["value"].mean()
    panel = elec.rename(columns={"value": "elec"}).merge(
        cook.rename(columns={"value": "cook"}), on=["country", "year"], how="outer")

    # Fill small gaps inside each country's time range (no extrapolation)
    out = []
    for c, g in panel.groupby("country"):
        g = g.set_index("year").reindex(range(g.year.min(), g.year.max() + 1))
        g[["elec", "cook"]] = g[["elec", "cook"]].interpolate(limit_area="inside")
        g["country"] = c
        out.append(g.reset_index().rename(columns={"index": "year"}))
    panel = pd.concat(out, ignore_index=True)
    panel[["elec", "cook"]] = panel[["elec", "cook"]].clip(0, 100)
    return panel.dropna(subset=["elec", "cook"]).sort_values(["country", "year"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# 2. MODEL A - Deadline Clock (trend forecasting)
# --------------------------------------------------------------------------
def trend(g: pd.DataFrame, col: str, window: int = 10) -> float:
    """Average yearly gain (percentage points/yr) from a linear regression on recent years."""
    g = g.dropna(subset=[col]).tail(window)
    if len(g) < 3:
        return np.nan
    m = LinearRegression().fit(g[["year"]].values, g[col].values)
    return float(m.coef_[0])


def year_to_target(level: float, gain: float, start_year: int) -> float:
    if level >= TARGET - 0.5:
        return float(start_year)
    if gain is None or np.isnan(gain) or gain <= 0.05:
        return np.inf            # flat or falling: never at this pace
    return start_year + (TARGET - level) / gain


def country_status(panel: pd.DataFrame, country: str) -> dict:
    g = panel[panel.country == country].sort_values("year")
    last = g.iloc[-1]
    s = {"country": country, "year": int(last.year),
         "elec": float(last.elec), "cook": float(last.cook),
         "elec_gain": trend(g, "elec"), "cook_gain": trend(g, "cook")}
    s["elec_eta"] = year_to_target(s["elec"], s["elec_gain"], s["year"])
    s["cook_eta"] = year_to_target(s["cook"], s["cook_gain"], s["year"])
    return s


def all_status(panel: pd.DataFrame) -> pd.DataFrame:
    rows = [country_status(panel, c) for c in panel.country.unique()
            if (panel.country == c).sum() >= 3]
    df = pd.DataFrame(rows)
    df["years_late"] = (np.maximum(df.elec_eta, df.cook_eta) - DEADLINE).clip(lower=0)
    return df


# --------------------------------------------------------------------------
# 3. MODEL B - Path Finder (K-Nearest Neighbours on past country states)
# --------------------------------------------------------------------------
FEATURES = ["elec", "cook", "elec_gain5", "cook_gain5"]
HORIZON = 10   # how many years of a twin's future we look at


def _states(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.sort_values(["country", "year"]).copy()
    p["elec_gain5"] = p.groupby("country")["elec"].diff(5) / 5
    p["cook_gain5"] = p.groupby("country")["cook"].diff(5) / 5
    return p.dropna(subset=FEATURES)


def classify_path(d_elec: float, d_cook: float) -> str:
    if d_elec < 3 and d_cook < 3:
        return "Slow / stalled"
    if d_elec > 2 * max(d_cook, 0.5):
        return "Electricity first"
    if d_cook > 2 * max(d_elec, 0.5):
        return "Clean cooking first"
    return "Both together"


def find_twins(panel: pd.DataFrame, country: str, k: int = 5) -> tuple[pd.DataFrame, dict]:
    states = _states(panel)
    me = states[states.country == country].sort_values("year")
    if me.empty:
        return pd.DataFrame(), {}
    me = me.iloc[-1]
    last_year = panel.groupby("country")["year"].max()
    # Candidates: other countries, at a past moment that has >= 5 years of future after it
    cand = states[(states.country != country) &
                  (states.year + 5 <= states.country.map(last_year))].copy()
    if cand.empty:
        return pd.DataFrame(), {}
    scaler = StandardScaler().fit(states[FEATURES])
    nn = NearestNeighbors(n_neighbors=min(len(cand), 200)).fit(scaler.transform(cand[FEATURES]))
    dist, idx = nn.kneighbors(scaler.transform(me[FEATURES].to_frame().T))
    cand = cand.iloc[idx[0]].assign(distance=dist[0])
    cand = cand.sort_values("distance").drop_duplicates("country").head(k)

    rows = []
    for _, t in cand.iterrows():
        fut = panel[(panel.country == t.country) & (panel.year >= t.year) &
                    (panel.year <= t.year + HORIZON)].sort_values("year")
        yrs = max(int(fut.year.max() - t.year), 1)
        d_e, d_c = fut.elec.iloc[-1] - t.elec, fut.cook.iloc[-1] - t.cook
        fit = "High" if t.distance < 0.5 else ("Medium" if t.distance < 1.0 else "Low")
        rows.append({
            "twin": t.country, "matched_year": int(t.year),
            "elec_then": t.elec, "cook_then": t.cook,
            "elec_gain_after": d_e / yrs, "cook_gain_after": d_c / yrs,
            "path": classify_path(d_e, d_c), "distance": t.distance,
            "fit": fit, "fit_weight": float(1 / (1 + t.distance)),
        })
    return pd.DataFrame(rows), me.to_dict()


def path_forecast(status: dict, twins: pd.DataFrame) -> pd.DataFrame:
    """Deadline Clock under each twin's path.
    'Realistic' blends the twin's speed with our own pace using the fit weight,
    because what worked for them may not fully work for us."""
    out = []
    y0 = status["year"]
    for _, t in twins.iterrows():
        w = t.fit_weight
        real_e = w * t.elec_gain_after + (1 - w) * max(status["elec_gain"] or 0, 0)
        real_c = w * t.cook_gain_after + (1 - w) * max(status["cook_gain"] or 0, 0)
        out.append({
            "twin": t.twin, "path": t.path, "fit": t.fit,
            "elec_eta_copy": year_to_target(status["elec"], t.elec_gain_after, y0),
            "cook_eta_copy": year_to_target(status["cook"], t.cook_gain_after, y0),
            "elec_eta_real": year_to_target(status["elec"], real_e, y0),
            "cook_eta_real": year_to_target(status["cook"], real_c, y0),
            "elec_gain_real": real_e, "cook_gain_real": real_c,
        })
    return pd.DataFrame(out)


# --------------------------------------------------------------------------
# 4. IMPACT & TRADE-OFF SIMULATOR (assumption-driven, user-editable)
# --------------------------------------------------------------------------
def simulate(pop_m: float, elec: float, cook: float, years: int, a: dict) -> dict:
    """pop_m: population in millions. a: assumptions dict (all editable in the UI)."""
    years = max(int(years), 1)
    hh = a["household_size"]
    hh_no_power = pop_m * 1e6 * (100 - elec) / 100 / hh
    hh_dirty = pop_m * 1e6 * (100 - cook) / 100 / hh

    mix = np.array([a["share_grid"], a["share_minigrid"], a["share_solar"]], dtype=float)
    mix = mix / mix.sum() if mix.sum() > 0 else np.array([1 / 3] * 3)
    cost_conn = hh_no_power * (mix[0] * a["cost_grid"] + mix[1] * a["cost_minigrid"] + mix[2] * a["cost_solar"])
    cost_cook = hh_dirty * a["cost_cookstove"] * (1 - a["household_copay"])
    total = cost_conn + cost_cook

    jobs = total / 1e6 * a["jobs_per_million"]
    outage_hh = (pop_m * 1e6 / hh) * a["grid_upgrade_area_share"]
    seller_income_lost = hh_dirty * a["charcoal_spend_per_hh"]          # per year once switched
    lpg_imports = hh_dirty * a["lpg_share"] * a["lpg_kg_per_hh"] * a["lpg_price_per_kg"]
    health_saving = hh_dirty * a["health_saving_per_hh"]
    fuel_saving = hh_dirty * a["charcoal_spend_per_hh"] * 0.5

    # Year-by-year timeline: spending spread evenly, benefits ramp up as people connect
    tl = []
    for y in range(1, years + 6):
        done = min(y / years, 1.0)
        spend = total / years if y <= years else a["maintenance_pct"] * total
        benefit = done * (health_saving + fuel_saving)
        tl.append({"year": y, "spending": spend, "benefits": benefit,
                   "outage_days": a["outage_days_per_year"] if y <= years else 0,
                   "households_connected": done * hh_no_power})
    tl = pd.DataFrame(tl)
    tl["cum_spending"] = tl.spending.cumsum()
    tl["cum_benefits"] = tl.benefits.cumsum()
    breakeven = tl[tl.cum_benefits >= tl.cum_spending]
    return {
        "hh_no_power": hh_no_power, "hh_dirty": hh_dirty,
        "cost_connections": cost_conn, "cost_cooking": cost_cook, "total_cost": total,
        "cost_per_year": total / years,
        "budget_share": (total / years) / a["energy_budget"] if a.get("energy_budget") else np.nan,
        "jobs": jobs, "outage_households": outage_hh,
        "seller_income_lost": seller_income_lost, "lpg_import_bill": lpg_imports,
        "health_saving": health_saving, "fuel_saving": fuel_saving,
        "breakeven_year": int(breakeven.year.iloc[0]) if len(breakeven) else None,
        "timeline": tl,
    }


DEFAULT_ASSUMPTIONS = {
    # Illustrative starting values only - replace with local / World Bank ESMAP / IEA figures.
    "household_size": 4.5,
    "share_grid": 40, "share_minigrid": 30, "share_solar": 30,
    "cost_grid": 1500.0, "cost_minigrid": 900.0, "cost_solar": 350.0,     # USD per household
    "cost_cookstove": 80.0, "household_copay": 0.3,                        # USD per household, share paid by family
    "jobs_per_million": 25.0,
    "grid_upgrade_area_share": 0.10, "outage_days_per_year": 5,
    "charcoal_spend_per_hh": 150.0,                                        # USD/yr spent on charcoal/firewood
    "lpg_share": 0.5, "lpg_kg_per_hh": 120.0, "lpg_price_per_kg": 1.2,
    "health_saving_per_hh": 40.0,                                          # USD/yr avoided illness costs
    "maintenance_pct": 0.02,
    "energy_budget": 0.0,
}


# --------------------------------------------------------------------------
# 5. IMPACT MAP - logged projects move the clock
# --------------------------------------------------------------------------
PROJECT_COLS = ["country", "project", "type", "lat", "lon", "people", "remarks", "logged_at"]


def load_projects(path: str) -> pd.DataFrame:
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame(columns=PROJECT_COLS)


def project_effect(status: dict, people: float, pop_m: float, kind: str) -> dict:
    """How many percentage points (and days of deadline) the logged projects buy."""
    if not pop_m or pop_m <= 0:
        return {"pp": 0.0, "days": 0.0}
    pp = people / (pop_m * 1e6) * 100
    gain = status["cook_gain"] if kind == "cook" else status["elec_gain"]
    days = pp / gain * 365 if gain and gain > 0.05 else float("nan")
    return {"pp": pp, "days": days}
