"""
rrg_core.py - data, Daily RRG and the Daily strategy for the 2026 IPO RRG app.

The RRG formula and the strategy rules are taken from the "RRG Graph app" help folder
(make_rrg_pvrinox.py and strategies.py -> Strategy 2 Version 3). They are copied here,
not imported, so nothing in that folder is touched. The one change asked for: the
strategy reads the DAILY RRG instead of the weekly one.

    RS          = stock close / NIFTY 50 close
    RS-Ratio    = 100 * EMA(SMA(RS,5),5) / EMA(SMA(RS,5),30)
    RS-Momentum = 100 * EMA(RS-Ratio,3) / EMA(RS-Ratio,14)        (EMAs with adjust=False)

Strategy (Daily RRG, 10% stop-loss):
    BUY   flat and Daily in {Leading, Improving}  -> bought next trading day at (open+close)/2
          (after a stop-loss: only once Daily has been in Weakening/Lagging and comes back up)
    SELL  Daily in {Weakening, Lagging}           -> sold next trading day at (open+close)/2
          or any day's close <= 90% of buy price  -> sold that day at that close (stop-loss)
"""
import os
from datetime import datetime

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)

# ---- method parameters (same as the help folder) -----------------------------
RS_PRESMOOTH, RS_SHORT, RS_LONG, MOM_SHORT, MOM_LONG = 5, 5, 30, 3, 14
WARMUP_DAILY = 200          # capped at len // 3 for short histories, as in the help folder
STOP_LOSS_PCT = 10.0
STOP_LOSS_OPTIONS = (10.0, 15.0)
SMA_DEFAULT = 14            # days, for the "SMA price" RRG option
COST_PCT = 0.12             # charges per side (%)

BENCH_TICKER, BENCH = "^NSEI", "NIFTY 50"
UP, DOWN = {"Improving", "Leading"}, {"Weakening", "Lagging"}
ORDER = ["Leading", "Weakening", "Lagging", "Improving"]

# palette (same tokens as the help folder charts)
SURFACE, INK_1, INK_2, INK_3, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8983", "#e7e6e2"
SERIES = "#2a78d6"
QUAD_BG = {"Leading": "#edf4ee", "Weakening": "#f7f3e8", "Lagging": "#f8eeee", "Improving": "#ebf1f8"}
QUAD_FG = {"Leading": "#3f7d55", "Weakening": "#8a6d2f", "Lagging": "#a05252", "Improving": "#4a6c96"}

# ---- tags ----------------------------------------------------------------------
# A stock can carry several tags. To add a tag: give it a name here, then add it to the stocks' tag lists.
TAG_TOP20 = "Top 20 IPO 2026"
TAG_ROBOTICS = "Robotics and Automation"
TAGS = [TAG_TOP20, TAG_ROBOTICS]

# ---- the 20 IPOs (verified on Chittorgarh, prices as of 6-9 Nov 2026) --------
# symbol, name, listing date, issue price, issue size (Rs cr)
TOP20 = [
    ("INDOMIM", "Indo-MIM", "2026-07-30", 485, 3812.11),
    ("ESDS", "ESDS Software Solution", "2026-09-04", 429, 720.00),
    ("OMNI", "Omnitech Engineering", "2026-03-05", 227, 583.00),
    ("TECHNOCRAF", "Technocraft Ventures", "2026-08-14", 212, 251.88),
    ("RAMBHAJO", "Advit Jewels", "2026-07-01", 138, 165.16),
    ("SHADOWFAX", "Shadowfax Technologies", "2026-01-28", 124, 1907.27),
    ("SEDEMAC", "SEDEMAC Mechatronics", "2026-03-11", 1352, 1087.35),
    ("MILKYMIST", "Milky Mist Dairy Food", "2026-08-18", 140, 1553.00),
    ("TONBO", "Tonbo Imaging India", "2026-10-23", 700, 852.09),
    ("KISSHT", "OnEMI Technology (Kissht)", "2026-05-08", 171, 925.92),
    ("XTRANET", "Xtranet Technologies", "2026-07-30", 127, 166.80),
    ("LALITHAA", "Lalithaa Jewellery Mart", "2026-08-24", 201, 1700.00),
    ("DHOOTTRANS", "Dhoot Transmission", "2026-08-17", 871, 3066.89),
    ("TEMPSENS", "Tempsens Instruments", "2026-08-28", 300, 650.00),
    ("MVELECTRO", "MV Electrosystems", "2026-08-06", 425, 290.00),
    ("JSIPL", "Jindal Supreme (India)", "2026-09-23", 93, 124.88),
    ("MOLBIO", "Molbio Diagnostics", "2026-08-17", 807, 939.70),
    ("STEAMHOUSE", "Steamhouse India", "2026-09-17", 81, 414.00),
    ("PNGSREVA", "PNGS Reva Diamond Jewellery", "2026-03-04", 386, 379.52),
    ("KANOHAR", "Kanohar Electricals", "2026-09-16", 632, 1055.74),
]

# ---- Robotics and Automation (added 10 Nov 2026; details from Chittorgarh / NSE) ----
# symbol, name, listing date, issue price (None = not an IPO), issue size (Rs cr, None = unknown),
# data ticker, data source ("yahoo", or "nse_csv" = NSE SME stock: Yahoo has no history, use NSE CSV files)
ROBOTICS = [
    ("KAYNES", "Kaynes Technology India", "2022-11-22", 587, 857.82, "KAYNES.NS", "yahoo"),
    ("OBSCP", "OBSC Perfection", "2024-10-29", 100, None, "OBSCP", "nse_csv"),
    ("SKFINDUS", "SKF India (Industrial)", "2025-12-05", None, None, "SKFINDUS.NS", "yahoo"),
    ("PATILAUTOM", "Patil Automation", "2025-06-23", 120, 69.61, "PATILAUTOM", "nse_csv"),
    ("AFFORDABLE", "Affordable Robotic & Automation", "2018-06-04", 85, None, "AFFORDABLE.NS", "yahoo"),
    ("BONFIG", "Bonfiglioli Transmissions", "2026-10-23", 586, 2533.67, "BONFIG.NS", "yahoo"),
]

# ---- 24 more mainboard IPOs, picked at random (added 14 Nov 2026) ------------------------
# Pool: 52 NSE mainboard IPOs listed 15 Nov 2024 - 14 Nov 2026 that have Yahoo price history;
# random.seed(2026); random.sample(pool, 24). No extra tag: they appear under "All".
# Issue price (upper band) and size verified 14 Nov 2026 from broker / news IPO pages;
# every listing date matches the first trading day in the Yahoo data.
# symbol, name, listing date, issue price, issue size (Rs cr)
MORE24 = [
    ("NTPCGREEN", "NTPC Green Energy", "2024-11-27", 108, 10000.00),
    ("SURAKSHA", "Suraksha Diagnostic", "2024-12-06", 441, 846.25),
    ("SAILIFE", "Sai Life Sciences", "2024-12-18", 549, 3042.62),
    ("MOBIKWIK", "One Mobikwik Systems", "2024-12-18", 279, 572.00),
    ("IKS", "Inventurus Knowledge Solutions", "2024-12-19", 1329, 2497.92),
    ("DAMCAPITAL", "DAM Capital Advisors", "2024-12-27", 283, 840.25),
    ("MAMATA", "Mamata Machinery", "2024-12-27", 243, 179.39),
    ("STALLION", "Stallion India Fluorochemicals", "2025-01-23", 90, 199.45),
    ("HEXT", "Hexaware Technologies", "2025-02-19", 708, 8750.00),
    ("SCODATUBES", "Scoda Tubes", "2025-06-04", 140, 220.00),
    ("HDBFS", "HDB Financial Services", "2025-07-02", 740, 12500.00),
    ("SAMBHV", "Sambhv Steel Tubes", "2025-07-02", 82, 540.00),
    ("CRIZAC", "Crizac", "2025-07-09", 245, 860.00),
    ("ANTHEM", "Anthem Biosciences", "2025-07-21", 570, 3395.00),
    ("BRIGHOTEL", "Brigade Hotel Ventures", "2025-07-31", 90, 759.60),
    ("CPPLUS", "Aditya Infotech (CP Plus)", "2025-08-05", 675, 1300.00),
    ("JSWCEMENT", "JSW Cement", "2025-08-14", 147, 3600.00),
    ("VIKRAMSOLR", "Vikram Solar", "2025-08-26", 332, 2079.37),
    ("TATACAP", "Tata Capital", "2025-10-13", 326, 15511.87),
    ("LGEINDIA", "LG Electronics India", "2025-10-14", 1140, 11607.01),
    ("CRAMC", "Canara Robeco Asset Management", "2025-10-16", 266, 1326.13),
    ("STUDDS", "Studds Accessories", "2025-11-07", 585, 455.49),
    ("GROWW", "Billionbrains Garage Ventures (Groww)", "2025-11-12", 100, 6632.30),
    ("PWL", "PhysicsWallah", "2025-11-18", 109, 3480.00),
]

# ---- 26 more, so there are 50 new mainboard IPOs in all (added 14 Nov 2026) -----------------
# The 28 left in the same pool after MORE24; random.seed(2026); random.sample(rest, 26).
# Left out by the draw: TRANSRAILL, ATHERENERG. Verified the same way as MORE24. BlackBuck and
# Dr Agarwal's have two listing dates in the sources; the first trading day in the data is used.
MORE26 = [
    ("BLACKBUCK", "Zinka Logistics Solutions (BlackBuck)", "2024-11-22", 273, 1114.72),
    ("EIEL", "Enviro Infra Engineers", "2024-11-29", 148, 650.43),
    ("VMM", "Vishal Mega Mart", "2024-12-18", 78, 8000.00),
    ("IGIL", "International Gemmological Institute (India)", "2024-12-20", 417, 4225.00),
    ("CEWATER", "Concord Enviro Systems", "2024-12-27", 701, 500.33),
    ("VENTIVE", "Ventive Hospitality", "2024-12-30", 643, 1600.00),
    ("SENORES", "Senores Pharmaceuticals", "2024-12-30", 391, 582.11),
    ("CARRARO", "Carraro India", "2024-12-30", 704, 1250.00),
    ("UNIMECH", "Unimech Aerospace and Manufacturing", "2024-12-31", 785, 500.00),
    ("LAXMIDENTL", "Laxmi Dental", "2025-01-20", 428, 698.06),
    ("AGARWALEYE", "Dr. Agarwal's Health Care", "2025-02-04", 402, 3027.26),
    ("BELRISE", "Belrise Industries", "2025-05-28", 90, 2150.00),
    ("AEGISVOPAK", "Aegis Vopak Terminals", "2025-06-02", 235, 2800.00),
    ("THELEELA", "Schloss Bangalore (The Leela)", "2025-06-02", 435, 3500.00),
    ("PROSTARM", "Prostarm Info Systems", "2025-06-03", 105, 168.00),
    ("OSWALPUMPS", "Oswal Pumps", "2025-06-20", 614, 1387.34),
    ("KALPATARU", "Kalpataru", "2025-07-01", 414, 1590.00),
    ("ELLEN", "Ellenbarrie Industrial Gases", "2025-07-01", 400, 852.53),
    ("TRAVELFOOD", "Travel Food Services", "2025-07-14", 1100, 2000.00),
    ("SMARTWORKS", "Smartworks Coworking Spaces", "2025-07-17", 407, 582.56),
    ("URBANCO", "Urban Company", "2025-09-17", 103, 1900.00),
    ("WEWORK", "WeWork India Management", "2025-10-10", 648, 3000.00),
    ("ORKLAINDIA", "Orkla India", "2025-11-06", 730, 1667.54),
    ("LENSKART", "Lenskart Solutions", "2025-11-10", 402, 7278.00),
    ("PINELABS", "Pine Labs", "2025-11-14", 221, 3899.91),
    ("MEESHO", "Meesho", "2025-12-10", 111, 5421.20),
]
NEW50 = MORE24 + MORE26

STOCKS = [(s, n) for s, n, *_ in TOP20] + [(s, n) for s, n, *_ in ROBOTICS] + [(s, n) for s, n, *_ in NEW50]
INFO = {}
for s, n, l, i, z in TOP20:
    INFO[s] = dict(symbol=s, name=n, listed=pd.Timestamp(l), issue=float(i), size=z,
                   ticker=s + ".NS", source="yahoo", tags=[TAG_TOP20])
for s, n, l, i, z, t, src in ROBOTICS:
    INFO[s] = dict(symbol=s, name=n, listed=pd.Timestamp(l), issue=float(i) if i else None, size=z,
                   ticker=t, source=src, tags=[TAG_ROBOTICS])
for s, n, l, i, z in NEW50:
    INFO[s] = dict(symbol=s, name=n, listed=pd.Timestamp(l), issue=float(i), size=z,
                   ticker=s + ".NS", source="yahoo", tags=[])


def stocks_for_tag(tag):
    """Symbols carrying `tag` (None or "All" = every stock), in list order."""
    return [s for s, _ in STOCKS if tag in (None, "All") or tag in INFO[s]["tags"]]


def tag_text(symbol):
    """Tags of a stock for display; a stock with no tag of its own is only in "All"."""
    return ", ".join(INFO[symbol]["tags"]) or "All only"


# ---- data ---------------------------------------------------------------------
def _csv(ticker):
    return os.path.join(DATA, ticker.replace("^", "") + ".csv")


def _fetch(ticker):
    import yfinance as yf
    d = yf.download(ticker, period="max", interval="1d", auto_adjust=True, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d[["Open", "Close"]].apply(pd.to_numeric, errors="coerce").dropna()
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    d = d[(d > 0).all(axis=1)]
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d.index.name = "Date"
    if d.empty:
        raise ValueError("no rows for %s" % ticker)
    return d


def get_prices(ticker, force=False):
    """Open/Close for one ticker. Downloads once a day (or on force) and keeps a CSV copy;
    if the download fails the saved copy is used. -> (frame, note)"""
    path = _csv(ticker)
    fresh = os.path.exists(path) and \
        datetime.fromtimestamp(os.path.getmtime(path)).date() == datetime.now().date()
    if force or not fresh:
        try:
            d = _fetch(ticker)
            d.to_csv(path)
            return d, "Yahoo Finance (downloaded now)"
        except Exception as exc:
            if not os.path.exists(path):
                raise RuntimeError("Download failed for %s and no saved copy: %s" % (ticker, exc))
            note = "saved copy (download failed: %s)" % str(exc)[:60]
    else:
        note = "saved copy from today"
    d = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
    return d, note


def get_ohlcv(ticker, force=False):
    """Open/High/Low/Close/Volume for the realistic trade replay. Kept in its own CSV copy
    (data/<ticker>_ohlcv.csv) so the Open/Close data used by the RRG is not touched. -> frame"""
    path = os.path.join(DATA, ticker.replace("^", "") + "_ohlcv.csv")
    fresh = os.path.exists(path) and \
        datetime.fromtimestamp(os.path.getmtime(path)).date() == datetime.now().date()
    if force or not fresh:
        try:
            import yfinance as yf
            d = yf.download(ticker, period="max", interval="1d", auto_adjust=True, progress=False)
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            d = d[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce").dropna()
            d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
            d = d[(d[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
            d = d[~d.index.duplicated(keep="last")].sort_index()
            d.index.name = "Date"
            if d.empty:
                raise ValueError("no rows")
            d.to_csv(path)
            return d
        except Exception:
            if not os.path.exists(path):
                raise
    return pd.read_csv(path, parse_dates=["Date"], index_col="Date")


MANUAL = os.path.join(DATA, "nse_csv")
os.makedirs(MANUAL, exist_ok=True)


def _num(col):
    return pd.to_numeric(col.astype(str).str.replace(",", "").str.strip(), errors="coerce")


def nse_csv_prices(symbol):
    """Prices from CSV files downloaded by hand from nseindia.com (quote page -> Historical Data ->
    Download .csv), saved as data/nse_csv/<SYMBOL>*.csv. Several files (one per year) are merged.
    NSE files are as-traded prices (not adjusted for splits/bonus)."""
    import glob
    files = sorted(glob.glob(os.path.join(MANUAL, symbol + "*.csv")))
    if not files:
        raise RuntimeError("NSE_CSV_MISSING")
    parts = []
    for f in files:
        d = pd.read_csv(f)
        d.columns = [str(c).strip().lower().replace("﻿", "") for c in d.columns]
        dcol = next(c for c in d.columns if "date" in c)
        ocol = next(c for c in d.columns if c in ("open", "open price", "ch_opening_price"))
        ccol = next(c for c in d.columns if c in ("close", "close price", "ch_closing_price"))
        p = pd.DataFrame({"Open": _num(d[ocol]), "Close": _num(d[ccol])})
        p.index = pd.to_datetime(d[dcol].astype(str).str.strip(), format="mixed", dayfirst=True)
        parts.append(p)
    d = pd.concat(parts).dropna()
    d = d[(d > 0).all(axis=1)]
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d.index.name = "Date"
    return d, "NSE CSV files (%d) in data/nse_csv" % len(files)


def aligned(symbol, force=False):
    """Stock Open/Close + NIFTY 50 Close on the dates both traded (inner join, no fill)."""
    info = INFO[symbol]
    if info["source"] == "nse_csv":
        s, note = nse_csv_prices(symbol)
    else:
        s, note = get_prices(info["ticker"], force)
    b, _ = get_prices(BENCH_TICKER, force)
    al = s.join(b[["Close"]].rename(columns={"Close": "Bench"}), how="inner").dropna()
    return al, note


# ---- Daily RRG ----------------------------------------------------------------
def quadrant(r, m):
    if r >= 100:
        return "Leading" if m >= 100 else "Weakening"
    return "Improving" if m >= 100 else "Lagging"


def daily_rrg(al, sma=0):
    """Daily RS-Ratio / RS-Momentum / quadrant. Empty frame if the history is too short.

    sma=0  -> RS from the daily close (original method).
    sma=N  -> RS from N-day simple moving averages of price: SMA_N(stock) / SMA_N(NIFTY).
              Trades still use the real Open/Close; the RRG starts on the same date as sma=0."""
    if sma and sma > 1:
        rs = al["Close"].rolling(sma).mean() / al["Bench"].rolling(sma).mean()
    else:
        rs = al["Close"] / al["Bench"]
    sm = rs.rolling(RS_PRESMOOTH, min_periods=1).mean()
    rr = 100.0 * sm.ewm(span=RS_SHORT, adjust=False).mean() / sm.ewm(span=RS_LONG, adjust=False).mean()
    rm = 100.0 * rr.ewm(span=MOM_SHORT, adjust=False).mean() / rr.ewm(span=MOM_LONG, adjust=False).mean()
    df = pd.DataFrame({"RS_Ratio": rr, "RS_Momentum": rm, "Open": al["Open"], "Close": al["Close"]}).dropna()
    warm = min(WARMUP_DAILY, len(al) // 3)
    if len(al) < warm + 10:
        return pd.DataFrame(columns=["RS_Ratio", "RS_Momentum", "Open", "Close", "Quadrant"]), warm
    df = df[df.index >= al.index[warm]].copy()      # same start date whatever the price basis
    if len(df) < 10:
        return pd.DataFrame(columns=["RS_Ratio", "RS_Momentum", "Open", "Close", "Quadrant"]), warm
    df["Quadrant"] = [quadrant(a, b) for a, b in zip(df["RS_Ratio"], df["RS_Momentum"])]
    return df, warm


# ---- strategy: Strategy 2 Version 3 rules on the DAILY RRG ---------------------
def _fill(o, c):
    return (o + c) / 2.0 if o == o else c


def run_strategy(rrg, stop_loss_pct=STOP_LOSS_PCT, cost_pct=COST_PCT, take_profit_pct=None):
    """-> (trades, pending buy signal, pending sell signal). Pending = signalled on the last
    day, to be executed on the next trading day.
    take_profit_pct (optional): any day's close >= buy price + x% sells that day at that close
    (profit booked); like a stop-loss, it buys again only after a down-and-up of the Daily RRG."""
    dates, q = rrg.index, rrg["Quadrant"].to_numpy()
    c, o = rrg["Close"].to_numpy(), rrg["Open"].to_numpy()
    trades, pos, armed, pending, pending_exit = [], None, True, None, None
    for i, d in enumerate(dates):
        if pending_exit is not None:                     # RRG exit: sell today
            trades.append(dict(pos, sell=d, sell_px=_fill(o[i], c[i]), open=False, **pending_exit))
            pos, pending_exit, armed = None, None, True
            continue
        if pending is not None:                          # entry: buy today, exits checked from tomorrow
            pos = dict(pending, buy=d, buy_px=_fill(o[i], c[i]))
            pending = None
            continue
        if pos is not None:
            stop_px = pos["buy_px"] * (1 - stop_loss_pct / 100.0)
            if c[i] <= stop_px:
                trades.append(dict(pos, sell=d, sell_px=c[i], open=False, exit_signal=d,
                                   exit_into=q[i], stop=True, stop_px=stop_px,
                                   exit_reason="Stop-loss %g%%: close ₹%.2f ≤ ₹%.2f (Daily %s)"
                                               % (stop_loss_pct, c[i], stop_px, q[i])))
                pos = None
                armed = q[i] in DOWN        # stopped in an up phase: wait for a down-and-up
            elif take_profit_pct and c[i] >= pos["buy_px"] * (1 + take_profit_pct / 100.0):
                trades.append(dict(pos, sell=d, sell_px=c[i], open=False, exit_signal=d, exit_into=q[i],
                                   stop=False, take_profit=True, stop_px=stop_px,
                                   exit_reason="Take-profit %g%%: close ₹%.2f ≥ ₹%.2f (Daily %s)"
                                               % (take_profit_pct, c[i], pos["buy_px"] * (1 + take_profit_pct / 100.0), q[i])))
                pos = None
                armed = q[i] in DOWN
            elif q[i] in DOWN:
                pending_exit = dict(exit_signal=d, exit_into=q[i], stop=False, stop_px=stop_px,
                                    exit_reason="Daily → %s" % q[i])
            continue
        if q[i] in DOWN:
            armed = True
        elif armed and q[i] in UP:
            pending = dict(signal=d, into=q[i], frm=q[i - 1] if i else "")
    if pos is not None:
        trades.append(dict(pos, sell=None, sell_px=c[-1], open=True, exit_signal=None, exit_into=None,
                           stop=False, stop_px=pos["buy_px"] * (1 - stop_loss_pct / 100.0),
                           exit_reason="Open position" + (" (sell signal on %s, sells next day)"
                                                          % pending_exit["exit_signal"].date()
                                                          if pending_exit else "")))
    k = cost_pct / 100.0
    for t in trades:
        t["ret"] = 100.0 * ((t["sell_px"] * (1 - k)) / (t["buy_px"] * (1 + k)) - 1)
        end = t["sell"] if t["sell"] is not None else dates[-1]
        t["held"] = int(dates.searchsorted(end, side="right") - dates.searchsorted(t["buy"], side="right"))
    return trades, pending, pending_exit


def replay_realistic(rrg, px, tp_pct=10.0, sl_pct=10.0, cost_pct=COST_PCT, amount=100000.0, end=None):
    """Replay the Daily RRG strategy with orders a trader could actually place, on daily OHLCV `px`.

    Entry  : the day after the RRG turns Improving/Leading, market buy at that day's OPEN (whole shares).
    Exits  : stop-loss order at buy - sl%  -> fills when the day's LOW reaches it (at the stop, or at the
             open if the stock opens below it = gap-down);
             take-profit limit at buy + tp% -> fills when the day's HIGH reaches it (at the target, or at
             the open if it opens above it);
             if one day's range contains BOTH levels the order is unknown from daily data, so the
             stop-loss is assumed first (conservative);
             RRG exit: the day after Weakening/Lagging, market sell at that day's OPEN.
    Re-entry after a stop-loss / take-profit only after the Daily RRG goes down and comes back up.
    Every trade carries `flags`: practical barriers seen on its entry / exit days."""
    q = rrg["Quadrant"]
    px = px[px.index.isin(rrg.index)]
    days = list(px.index)
    prev_close = px["Close"].shift(1)
    k = cost_pct / 100.0
    trades, pos, armed, want_buy, want_sell = [], None, True, None, None

    def day_flags(d, side):
        f = []
        o, h, l, c, v = (px.at[d, x] for x in ("Open", "High", "Low", "Close", "Volume"))
        pc = prev_close.get(d)
        if h == l:
            f.append("%s %s: price locked all day (High = Low) — likely circuit, order may not fill"
                     % (side, d.strftime("%d %b %Y")))
        elif pc == pc and pc and abs(c / pc - 1) >= 0.195:
            f.append("%s %s: %+.1f%% day — near a 20%% circuit band, fills can be hard"
                     % (side, d.strftime("%d %b %Y"), 100 * (c / pc - 1)))
        value = v * c
        if value > 0 and amount / value > 0.02:
            f.append("%s %s: ₹%s = %.1f%% of the day's traded value (₹%.1f lakh) — thin liquidity, expect slippage"
                     % (side, d.strftime("%d %b %Y"), format(amount, ",.0f"), 100 * amount / value, value / 1e5))
        return f

    for i, d in enumerate(days):
        o, h, l, c = (px.at[d, x] for x in ("Open", "High", "Low", "Close"))
        if want_sell is not None and pos is not None:               # RRG exit at today's open
            pos.update(sell=d, sell_px=o, exit="Daily RRG → %s" % want_sell, flags=pos["flags"] + day_flags(d, "Sell"))
            trades.append(pos); pos, want_sell, armed = None, None, True
        elif want_buy is not None and pos is None:                  # entry at today's open
            sh = int(amount // (o * (1 + k)))
            if sh == 0:
                want_buy = None
            else:
                pos = dict(signal=want_buy, buy=d, buy_px=o, shares=sh, flags=day_flags(d, "Buy"))
                want_buy = None
        if pos is not None and pos.get("sell") is None:
            stop, target = pos["buy_px"] * (1 - sl_pct / 100.0), pos["buy_px"] * (1 + tp_pct / 100.0)
            gap_open = d != pos["buy"]                              # on the entry day we bought at the open
            hit = None
            if gap_open and o <= stop:
                hit = ("Stop-loss (gap-down open)", o, "stop")
                pos["flags"].append("Sell %s: opened at ₹%.2f, below the stop ₹%.2f — loss bigger than %g%%"
                                    % (d.strftime("%d %b %Y"), o, stop, sl_pct))
            elif gap_open and o >= target:
                hit = ("Take-profit (gap-up open)", o, "tp")
            elif l <= stop and h >= target:
                hit = ("Stop-loss (both levels in one day — assumed stop first)", stop, "stop")
                pos["flags"].append("Sell %s: day's range touched BOTH stop ₹%.2f and target ₹%.2f — daily data can't "
                                    "tell which came first; stop-loss assumed" % (d.strftime("%d %b %Y"), stop, target))
            elif l <= stop:
                hit = ("Stop-loss %g%%" % sl_pct, stop, "stop")
            elif h >= target:
                hit = ("Take-profit %g%%" % tp_pct, target, "tp")
            if hit:
                pos.update(sell=d, sell_px=hit[1], exit=hit[0], kind=hit[2], flags=pos["flags"] + day_flags(d, "Sell"))
                trades.append(pos); pos = None
                armed = q.get(d) in DOWN
                continue
            if q.get(d) in DOWN:
                want_sell = q.get(d)
            continue
        if pos is None and want_buy is None:
            if q.get(d) in DOWN:
                armed = True
            elif armed and q.get(d) in UP and i + 1 < len(days) and (end is None or days[i + 1] <= end):
                want_buy = d
    if pos is not None:
        pos.update(sell=None, sell_px=float(px["Close"].iloc[-1]), exit="Open position (marked at last close)")
        trades.append(pos)
    for t in trades:
        t.setdefault("kind", "rrg" if t["sell"] is not None else "open")
        paid = t["shares"] * t["buy_px"] * (1 + k)
        got = t["shares"] * t["sell_px"] * (1 - k)
        t["ret"] = 100.0 * (got - paid) / paid
        t["days"] = int(((t["sell"] if t["sell"] is not None else days[-1]) - t["buy"]).days)
        if t["sell"] is not None and t["days"] == 0:
            t["flags"].append("Bought and sold the same day (%s) — that is an intraday trade (different charges and tax "
                              "from delivery); counted as 1 day held" % t["buy"].strftime("%d %b %Y"))
            t["days"] = 1
    return trades


def summary(trades):
    closed = [t for t in trades if not t["open"]]
    wins = [t for t in closed if t["ret"] > 0]
    growth = float(np.prod([1 + t["ret"] / 100.0 for t in trades])) if trades else 1.0
    return dict(trades=len(trades), closed=len(closed), wins=len(wins),
                stops=sum(1 for t in closed if t.get("stop")),
                win_rate=100.0 * len(wins) / len(closed) if closed else float("nan"),
                compound=100.0 * (growth - 1),
                best=max((t["ret"] for t in trades), default=float("nan")),
                worst=min((t["ret"] for t in trades), default=float("nan")))
