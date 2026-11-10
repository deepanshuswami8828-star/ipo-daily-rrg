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

STOCKS = [(s, n) for s, n, *_ in TOP20] + [(s, n) for s, n, *_ in ROBOTICS]
INFO = {}
for s, n, l, i, z in TOP20:
    INFO[s] = dict(symbol=s, name=n, listed=pd.Timestamp(l), issue=float(i), size=z,
                   ticker=s + ".NS", source="yahoo", tags=[TAG_TOP20])
for s, n, l, i, z, t, src in ROBOTICS:
    INFO[s] = dict(symbol=s, name=n, listed=pd.Timestamp(l), issue=float(i) if i else None, size=z,
                   ticker=t, source=src, tags=[TAG_ROBOTICS])


def stocks_for_tag(tag):
    """Symbols carrying `tag` (None or "All" = every stock), in list order."""
    return [s for s, _ in STOCKS if tag in (None, "All") or tag in INFO[s]["tags"]]


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


def daily_rrg(al):
    """Daily RS-Ratio / RS-Momentum / quadrant. Empty frame if the history is too short."""
    rs = al["Close"] / al["Bench"]
    sm = rs.rolling(RS_PRESMOOTH, min_periods=1).mean()
    rr = 100.0 * sm.ewm(span=RS_SHORT, adjust=False).mean() / sm.ewm(span=RS_LONG, adjust=False).mean()
    rm = 100.0 * rr.ewm(span=MOM_SHORT, adjust=False).mean() / rr.ewm(span=MOM_LONG, adjust=False).mean()
    df = pd.DataFrame({"RS_Ratio": rr, "RS_Momentum": rm, "Open": al["Open"], "Close": al["Close"]}).dropna()
    warm = min(WARMUP_DAILY, len(df) // 3)
    if len(df) < warm + 10:
        return pd.DataFrame(columns=["RS_Ratio", "RS_Momentum", "Open", "Close", "Quadrant"]), warm
    df = df.iloc[warm:].copy()
    df["Quadrant"] = [quadrant(a, b) for a, b in zip(df["RS_Ratio"], df["RS_Momentum"])]
    return df, warm


# ---- strategy: Strategy 2 Version 3 rules on the DAILY RRG ---------------------
def _fill(o, c):
    return (o + c) / 2.0 if o == o else c


def run_strategy(rrg, stop_loss_pct=STOP_LOSS_PCT, cost_pct=COST_PCT):
    """-> (trades, pending buy signal, pending sell signal). Pending = signalled on the last
    day, to be executed on the next trading day."""
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
