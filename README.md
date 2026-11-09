# IPO Daily RRG

Daily Relative Rotation Graph (RRG) of the 20 best-performing 2026 NSE mainboard IPOs against NIFTY 50,
each from its listing day, with a date slider for the tail, quadrant history, up/down cycles, a data
validation panel, and a Daily-RRG strategy (buy in Leading/Improving, sell in Weakening/Lagging, 10% stop-loss)
simulated in rupees.

- `app.py` - the Streamlit app (pages: Daily RRG, Strategy, All stocks, Rules)
- `rrg_core.py` - data download, Daily RRG formula, strategy rules
- `analysis.py` - validation, quadrant periods, cycles, rupee simulation, profit/loss explanation
- `data/` - saved daily prices (refreshed from Yahoo Finance once a day; used if a download fails)

Run locally: `streamlit run app.py`

Formula: RS-Ratio = 100 × EMA(SMA(RS,5),5) / EMA(SMA(RS,5),30); RS-Momentum = 100 × EMA(RS-Ratio,3) / EMA(RS-Ratio,14).
Historical test only - not investment advice.
