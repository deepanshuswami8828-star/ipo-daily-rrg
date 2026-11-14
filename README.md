# IPO Daily RRG

Daily Relative Rotation Graph (RRG) of 76 Indian IPOs against NIFTY 50, each from its listing day:

- **Top 20 IPO 2026** - the 20 best-performing 2026 NSE mainboard IPOs
- **Robotics and Automation** - 6 stocks (2 of them NSE SME, which need NSE CSV files)
- **50 more mainboard IPOs** listed Nov 2024 - Dec 2025, picked at random (in the "All" tag only)

With a date slider for the tail, quadrant history, up/down cycles, a data validation panel, and a Daily-RRG
strategy (buy in Leading/Improving, sell in Weakening/Lagging, 10% or 15% stop-loss) simulated in rupees.
The RRG can be built on the daily close or on an N-day SMA of price.

- `app.py` - the Streamlit app; top navigation: RRG charts, Tags analysis, Vintage
- `tags_analysis.py` - per-tag strategy profitability, static time view, setup comparison
- `vintage_analysis.py` - month 0-6 vintage view, take-profit analysis, realistic OHLCV replay
- `rrg_core.py` - stock list and tags, data download, Daily RRG formula, strategy rules
- `analysis.py` - stock profiles, search, validation, quadrant periods, cycles, rupee simulation
- `data/` - saved daily prices (refreshed from Yahoo Finance once a day; used if a download fails)

Run locally: `streamlit run app.py`

Formula: RS-Ratio = 100 × EMA(SMA(RS,5),5) / EMA(SMA(RS,5),30); RS-Momentum = 100 × EMA(RS-Ratio,3) / EMA(RS-Ratio,14).
Historical test only - not investment advice.
