"""
compute.py - the heavy calculations of the Vintage page, with no Streamlit code, so that build_cache.py can run
them once and save the results (results.py) and the page can fall back to them for settings not saved.

Month 0 = a stock's first Daily RRG session; the vintage window is month 0 to month 12 (1 year).
"""
import numpy as np
import pandas as pd

import rrg_core as core
from rrg_core import INFO

MONTH_DAYS = 30.4375
MAX_MONTHS = 12                                        # vintage window: month 0 to month 12 (1 year)
TAKE_PROFITS = [5, 7, 10, 12, 15, 17, 20, 25, 30]     # profit exit points (%) on the take-profit charts
EXITS = [None] + TAKE_PROFITS                          # None = no take-profit (sold on the Daily RRG only)
WINDOW_DAYS = int(round(MAX_MONTHS * MONTH_DAYS))
REPLAY_DEFAULT = dict(tp=10.0, sl=10.0, amount=100000.0, only6=True)


def _status(symbol, exc=None, n=0):
    if exc is not None:
        return "NSE SME stock — add NSE CSV files" if INFO[symbol]["source"] == "nse_csv" else "No data"
    return "Only %d sessions — too few for RRG" % n


def vintage(symbol, sma, stop_loss, cost, take_profit=None):
    """(status, start, DataFrame[day, month, strategy %, buyhold %, daily %], trades bought by the end of the window).
    status '' = ok. strategy % is marked to market every session (open trades at that day's close, charges in);
    daily % = Tags-method daily profit of the closed trades so far (sum of profit % / sum of days held)."""
    try:
        al, rrg, _ = core.rrg_for(symbol, sma)
    except Exception as exc:
        return _status(symbol, exc), None, None, []
    if rrg.empty:
        return _status(symbol, n=len(al)), None, None, []
    trades, _, _ = core.run_strategy(rrg, stop_loss, cost, take_profit)
    idx = rrg.index
    start = idx[0]
    end = start + pd.Timedelta(days=WINDOW_DAYS)
    close = rrg["Close"].to_numpy(dtype=float)
    k = cost / 100.0
    curve, v = np.ones(len(idx)), 1.0
    for t in trades:                                       # mark to market, charges in
        i0 = idx.searchsorted(t["buy"])
        i1 = idx.searchsorted(t["sell"]) if t["sell"] is not None else len(idx) - 1
        curve[i0:i1 + 1] = v * close[i0:i1 + 1] * (1 - k) / (t["buy_px"] * (1 + k))
        v *= 1 + t["ret"] / 100.0
        if t["sell"] is not None:
            curve[i1:] = v
    n = int(idx.searchsorted(end, side="right"))
    win = idx[:n]
    days = np.asarray((win - start).days)
    daily = np.full(n, np.nan)
    held = np.zeros(n)                                     # calendar days held, closed trades so far
    ntr = np.zeros(n)                                      # closed trades so far
    psum, dsum, k_tr = 0.0, 0, 0
    for t in sorted((t for t in trades if t["sell"] is not None and not t["open"] and start <= t["buy"]
                     and t["sell"] <= end), key=lambda t: t["sell"]):
        psum += t["ret"]
        dsum += int((t["sell"] - t["buy"]).days)
        k_tr += 1
        j = idx.searchsorted(t["sell"])
        held[j:], ntr[j:] = dsum, k_tr
        if dsum > 0:
            daily[j:] = psum / dsum
    df = pd.DataFrame({"day": days, "month": days / MONTH_DAYS, "strategy": 100 * (curve[:n] - 1),
                       "buyhold": 100 * (close[:n] / close[0] - 1), "daily": daily, "held": held, "ntr": ntr},
                      index=win)
    return "", start, df, [t for t in trades if t["buy"] <= end]


def in_window(trades, start):
    """Closed trades bought AND sold between month 0 and month 12 (the vintage window)."""
    end = start + pd.Timedelta(days=WINDOW_DAYS)
    return [t for t in trades if not t["open"] and t["sell"] is not None and start <= t["buy"] and t["sell"] <= end]


def average_line(curves, col):
    """Average of `col` over stocks on a calendar-day grid 0..12 months. A stock counts from its first value
    (carried forward between sessions) up to its last session. -> DataFrame[month, avg, n]"""
    grid = np.arange(0, int(MAX_MONTHS * MONTH_DAYS) + 1)
    if not curves:
        return pd.DataFrame({"month": grid / MONTH_DAYS, "avg": np.nan, "n": 0})
    mat = np.full((len(curves), len(grid)), np.nan)
    for r, df in enumerate(curves.values()):
        d = df["day"].to_numpy()
        pos = np.searchsorted(d, grid, side="right") - 1          # last session on or before each day
        ok = (pos >= 0) & (grid <= d[-1])
        vals = df[col].to_numpy(dtype=float)
        mat[r, ok] = vals[pos[ok]]
    n = np.sum(~np.isnan(mat), axis=0)
    with np.errstate(invalid="ignore"):
        avg = np.where(n > 0, np.nansum(mat, axis=0) / np.maximum(n, 1), np.nan)
    return pd.DataFrame({"month": grid / MONTH_DAYS, "avg": avg, "n": n})


def pooled_line(curves, num, den):
    """sum(num) / sum(den) over the stocks on the calendar-day grid 0..12 months (e.g. held / ntr = average
    calendar days held per closed trade, all stocks' trades so far). -> DataFrame[month, avg, n]"""
    grid = np.arange(0, int(MAX_MONTHS * MONTH_DAYS) + 1)
    tn, td = np.zeros(len(grid)), np.zeros(len(grid))
    for df in curves.values():
        d = df["day"].to_numpy()
        pos = np.searchsorted(d, grid, side="right") - 1
        ok = (pos >= 0) & (grid <= d[-1])
        tn[ok] += df[num].to_numpy(dtype=float)[pos[ok]]
        td[ok] += df[den].to_numpy(dtype=float)[pos[ok]]
    with np.errstate(invalid="ignore", divide="ignore"):
        avg = np.where(td > 0, tn / np.maximum(td, 1e-12), np.nan)
    return pd.DataFrame({"month": grid / MONTH_DAYS, "avg": avg, "n": td})


def tp_stock(symbol, sma, stop_loss, cost, tp):
    """One stock, one stop-loss / take-profit setting, first 12 months -> dict or None (no RRG)."""
    return tp_summary(vintage(symbol, sma, stop_loss, cost, tp))


def curve_series(v):
    """From a vintage() result: (days since month 0, cumulative profit %, Tags-method daily profit %, calendar days
    held by the closed trades so far, closed trades so far) or None - compact enough to save for every stock and
    exit point."""
    status, _, df, _ = v
    if status:
        return None
    return (df["day"].to_numpy().astype(np.int16), df["strategy"].to_numpy().astype(np.float32),
            df["daily"].to_numpy().astype(np.float32), df["held"].to_numpy().astype(np.int32),
            df["ntr"].to_numpy().astype(np.int16))


def tp_summary(v):
    """From a vintage() result: the take-profit chart numbers for one stock -> dict or None (no RRG)."""
    status, start, df, trs = v
    if status:
        return None
    closed = in_window(trs, start)
    d = sum(int((t["sell"] - t["buy"]).days) for t in closed)
    return {"final": float(df["strategy"].iloc[-1]),
            "daily": None if pd.isna(df["daily"].iloc[-1]) else float(df["daily"].iloc[-1]),
            "tag": sum(t["ret"] for t in closed) / d if d > 0 else None,
            "trades": len(trs), "tp_hits": sum(1 for t in closed if t.get("take_profit")),
            "closed": len(closed), "days": d}


def rule_check_stock(symbol, sma, cost):
    """For every stop-loss level and take-profit exit: trades checked, stop-loss exits, take-profit exits and
    trades that broke 'stop-loss first' (a stop-loss after the profit exit was already reached, or the
    reverse). -> (checked, stops, tps, bad)"""
    checked = stops = tps = bad = 0
    try:
        al, _ = core.aligned(symbol)
    except Exception:
        return 0, 0, 0, 0
    c = al["Close"]
    for sl in core.STOP_LOSS_OPTIONS:
        for tp in TAKE_PROFITS:
            status, _, _, trs = vintage(symbol, sma, sl, cost, tp)
            if status:
                continue
            for t in trs:
                if t["open"] or t["sell"] is None:
                    continue
                checked += 1
                stop_px, tgt = t["buy_px"] * (1 - sl / 100.0), t["buy_px"] * (1 + tp / 100.0)
                before = c[(c.index > t["buy"]) & (c.index < t["sell"])]
                if t.get("stop"):
                    stops += 1
                    bad += int((before >= tgt).any())
                elif t.get("take_profit"):
                    tps += 1
                    bad += int((before <= stop_px).any())
    return checked, stops, tps, bad


def replay(symbol, sma, tp, sl, cost, amount, only6):
    """Realistic OHLCV replay (rrg_core.replay_realistic) -> (trades or None, reason)."""
    try:
        _, rrg, _ = core.rrg_for(symbol, sma)              # no price data (e.g. NSE SME) -> stop before downloading
        px = core.get_ohlcv(INFO[symbol]["ticker"])
    except Exception as exc:
        return None, "no OHLCV data (%s)" % str(exc)[:60]
    if rrg.empty:
        return None, "too few sessions"
    if only6:
        end6 = rrg.index[0] + pd.Timedelta(days=WINDOW_DAYS)
        rrg, px = rrg[rrg.index <= end6], px[px.index <= end6]
    return core.replay_realistic(rrg, px, tp, sl, cost, amount), ""
