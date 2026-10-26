# ⚡ Path to 2030
**AI for Good · SDG 7: Affordable and Clean Energy**

An AI tool that helps countries choose, plan, and track their path to clean energy for all.

## Data
UN SDG Global Database (unstats.un.org/sdgs/dataportal)
- **7.1.1** Proportion of population with access to electricity (`EG_ELC_ACCS`)
- **7.1.2** Proportion of population with primary reliance on clean fuels and technology (`EG_EGY_CLEAN`)

Put both CSVs in the `data/` folder (any file name), or upload them in the app.
National totals are kept, regions/groupings are removed, small gaps are interpolated.

## Models
| Feature | Method |
|---|---|
| Deadline Clock | Linear regression on each country's last 10 years → year it reaches 100% |
| Path Finder | K-Nearest Neighbours on (electricity %, cooking %, 5-year speed of each) to find "twin" countries in the past |
| Fit Score | Distance of the twin match → High / Medium / Low; the "realistic" forecast blends the twin's speed with your own pace by fit |
| Impact Simulator | Assumption-driven cost / jobs / disruption model (all inputs editable) |
| Impact Map | Logged projects convert people reached into % points and days gained on the Deadline Clock |

## Accuracy (backtest)
Trained on data up to 2019, the Deadline Clock predicted 2024 levels for 194 countries with a mean absolute error of about 1.7 percentage points for both indicators (median 0.04 for electricity, 1.0 for clean cooking).

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (free)
Push this folder to a GitHub repo → share.streamlit.io → New app → pick the repo and `app.py`.

## Limitations
- Forecasts show current pace, not guarantees.
- UN data shows how fast countries improved, not which policies they used. Field remarks in the Impact Map add that context.
- Economic defaults are illustrative; replace with local or World Bank / IEA figures.
- Demo project log is a CSV; production would use a shared database.
