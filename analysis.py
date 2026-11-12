"""
analysis.py - the per-stock details the help-folder app shows, rebuilt for the 20 IPOs (Daily only):
stock profile, data validation, quadrant periods, up/down cycles, rupee simulation of the strategy,
metrics, and a plain "why profit / loss" explanation (English + Hinglish).
"""
from datetime import datetime, time, timedelta, timezone

import numpy as np
import pandas as pd

from rrg_core import UP, DOWN

IST = timezone(timedelta(hours=5, minutes=30))
SUSPICIOUS_MOVE_PCT = 25.0      # same flag level as the help folder

# sector / industry / city: Yahoo Finance profile (fetched 9 Nov 2026)
PROFILE = {
    "INDOMIM": ("Industrials", "Metal Fabrication", "Bengaluru"),
    "ESDS": ("Technology", "IT Services (cloud & data centres)", "Thane"),
    "OMNI": ("Industrials", "Specialty Industrial Machinery", "Rajkot"),
    "TECHNOCRAF": ("Industrials", "Infrastructure Operations", "Noida"),
    "RAMBHAJO": ("Consumer Cyclical", "Jewellery (Luxury Goods)", "Jaipur"),
    "SHADOWFAX": ("Industrials", "Freight & Logistics", "Bengaluru"),
    "SEDEMAC": ("Consumer Cyclical", "Auto Parts", "Pune"),
    "MILKYMIST": ("Consumer Defensive", "Packaged Foods (Dairy)", "Perundurai"),
    "TONBO": ("Industrials", "Aerospace & Defence", "Bengaluru"),
    "KISSHT": ("Financial Services", "Credit Services (Fintech lending)", "Mumbai"),
    "XTRANET": ("Technology", "IT Services", "Bhopal"),
    "LALITHAA": ("Consumer Cyclical", "Jewellery (Luxury Goods)", "Chennai"),
    "DHOOTTRANS": ("Consumer Cyclical", "Auto Parts", "Aurangabad"),
    "TEMPSENS": ("Technology", "Scientific & Technical Instruments", "Udaipur"),
    "MVELECTRO": ("Industrials", "Electrical Equipment & Parts", "Faridabad"),
    "JSIPL": ("Basic Materials", "Steel", "Hisar"),
    "MOLBIO": ("Healthcare", "Medical Devices (Diagnostics)", "Verna, Goa"),
    "STEAMHOUSE": ("Utilities", "Industrial steam & gas utility", "Surat"),
    "PNGSREVA": ("Consumer Cyclical", "Jewellery (Luxury Goods)", "Pune"),
    "KANOHAR": ("Industrials", "Electrical Equipment & Parts", "Meerut"),
    # Robotics and Automation
    "KAYNES": ("Technology", "Electronic Components (EMS)", "Mysuru"),
    "OBSCP": ("Industrials", "Precision engineered components", "—"),
    "SKFINDUS": ("Industrials", "Bearings & industrial tools", "Pune"),
    "PATILAUTOM": ("Industrials", "Industrial automation", "Pune"),
    "AFFORDABLE": ("Industrials", "Robotics & automation machinery", "Pune"),
    "BONFIG": ("Industrials", "Gearboxes & drives (Specialty Machinery)", "Kanchipuram"),
}
NOTES = {
    "RAMBHAJO": "Advit Jewels trades on NSE as RAMBHAJO (data starts on its 1 Jul 2026 listing day).",
    "TONBO": "Listed 23 Oct 2026 - too few sessions for a Daily RRG yet.",
    "BONFIG": "Listed 23 Oct 2026 - too few sessions for a Daily RRG yet.",
    "KAYNES": "Mainboard IPO, Nov 2022 (issue ₹587).",
    "SKFINDUS": "Not an IPO: listed on 5 Dec 2025 after the demerger from SKF India (1 share per SKF India "
                "share), so there is no issue price.",
    "AFFORDABLE": "IPO on BSE SME, Jun 2018 at ₹85; Yahoo's NSE price history starts 23 Oct 2024, so the RRG "
                  "starts from there.",
    "OBSCP": "NSE SME stock (IPO Oct 2024 at ₹100). Yahoo has no price history for SME stocks - add NSE CSV "
             "files (see below).",
    "PATILAUTOM": "NSE SME stock (IPO Jun 2025 at ₹120). Yahoo has no price history for SME stocks - add NSE CSV "
                  "files (see below).",
}


def sector(sym):
    return PROFILE.get(sym, ("—", "—", "—"))[0]


def search_stocks(symbols, query):
    """Stocks matching a search box: every word must appear in the ticker, name, sector, industry, city or tags
    (case-insensitive). Empty query -> all symbols, in the same order."""
    from rrg_core import INFO
    words = str(query or "").lower().split()
    if not words:
        return list(symbols)

    def text(s):
        i = INFO[s]
        return " ".join([s, i["name"], *PROFILE.get(s, ("", "", "")), *i["tags"]]).lower()

    return [s for s in symbols if all(w in text(s) for w in words)]


# ---- market clock -------------------------------------------------------------
def now_ist():
    return datetime.now(IST)


def market_open(now):
    return now.weekday() < 5 and time(9, 15) <= now.time() <= time(15, 30)


def expected_latest_session(now):
    """Last weekday whose session is complete (after 15:45 IST); NSE holidays not modelled."""
    d = now.date()
    if now.weekday() >= 5 or now.time() < time(15, 45):
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return pd.Timestamp(d)


# ---- validation (same checks as the help folder's pipeline) --------------------
def validate(al, listed):
    s = al["Close"]
    chg = 100 * s.pct_change()
    flagged = [{"Date": d.strftime("%d %b %Y"), "Close": round(s[d], 2), "Move": "%+.2f%%" % v}
               for d, v in chg[chg.abs() > SUSPICIOUS_MOVE_PCT].items()]
    checks = [
        ("Prices positive", bool((al[["Open", "Close"]] > 0).all().all())),
        ("No missing values", not al.isna().any().any()),
        ("No duplicate dates", not al.index.duplicated().any()),
        ("Dates in order", bool(al.index.is_monotonic_increasing)),
        ("No dates before listing", bool(al.index[0] >= listed)),
        ("Latest date not in the future", bool(al.index[-1].date() <= now_ist().date())),
    ]
    # a weekend row is a real special session (e.g. Union Budget Sat 1 Feb 2025) only if NIFTY 50 traded too
    wk = al.index[al.index.dayofweek >= 5]
    checks.append(("Weekend dates only on real sessions", bool(al.loc[wk, "Bench"].notna().all()) if "Bench" in al else len(wk) == 0))
    weekend = [d.strftime("%a %d %b %Y") for d in wk]
    return dict(rows=len(al), first=al.index[0], last=al.index[-1], flagged=flagged, checks=checks,
                weekend=weekend, first_vs_listing=(al.index[0] - listed).days)


# ---- quadrant periods and up/down cycles --------------------------------------
def periods(df):
    """Consecutive runs of the same quadrant, newest first."""
    run = (df["Quadrant"] != df["Quadrant"].shift()).cumsum()
    rows = [{"Quadrant": g["Quadrant"].iloc[0], "From": g.index[0], "To": g.index[-1], "Sessions": len(g)}
            for _, g in df.groupby(run)]
    return pd.DataFrame(rows).iloc[::-1].reset_index(drop=True)


def phases(df):
    """Runs on the same side: up = Improving/Leading, down = Weakening/Lagging."""
    up = df["Quadrant"].isin(UP)
    run = (up != up.shift()).cumsum()
    out = []
    for _, g in df.groupby(run):
        route = [q for i, q in enumerate(g["Quadrant"]) if i == 0 or q != g["Quadrant"].iloc[i - 1]]
        out.append(dict(up=bool(g["Quadrant"].iloc[0] in UP), start=g.index[0], last=g.index[-1],
                        bars=len(g), route=route))
    for a, b in zip(out, out[1:]):
        a["next"] = b["start"]
    if out:
        out[-1]["next"] = None
    return out


def moves(df):
    """Every switch between up and down, oldest first, with the price change until the next switch."""
    ph = phases(df)
    last_close = df["Close"].iloc[-1]
    out = []
    for prev, p in zip(ph, ph[1:]):
        close = df.loc[p["start"], "Close"]
        end_close = df.loc[p["next"], "Close"] if p["next"] is not None else last_close
        out.append(dict(date=p["start"], up=p["up"], frm=prev["route"][-1], to=p["route"][0],
                        route=p["route"], bars=p["bars"], open=p["next"] is None, until=p["next"],
                        close=close, change=100 * (end_close / close - 1)))
    return out


# ---- rupee simulation (same method as the help folder's simulate_single_strategy) ----
def simulate(rrg, trades, capital, cost_pct):
    """Whole shares, charges both sides, daily mark-to-market. -> (book, cash, value, bh_value, bh_shares)"""
    c = cost_pct / 100.0
    close = rrg["Close"]
    cash, book = float(capital), []
    shares_by_day = pd.Series(0, index=close.index)
    for t in trades:
        shares = int(cash // (t["buy_px"] * (1 + c)))
        paid = shares * t["buy_px"] * (1 + c)
        got = shares * t["sell_px"] * (1 - c)
        charges = shares * t["buy_px"] * c + shares * t["sell_px"] * c
        before = cash
        cash = cash - paid + got
        end = t["sell"] if t["sell"] is not None else close.index[-1]
        shares_by_day[(close.index >= t["buy"]) & (close.index < end)] = shares
        if t["sell"] is None:
            shares_by_day[close.index == end] = shares
        book.append(dict(t, shares=shares, paid=paid, got=got, pnl=got - paid,
                         pnl_pct=100.0 * (got - paid) / paid if paid > 0 else 0.0,
                         charges=charges, cash_before=before, cash_after=cash))
    cash_by_day = pd.Series(float(capital), index=close.index)
    for b in book:
        end = b["sell"] if b["sell"] is not None else close.index[-1]
        cash_by_day[(close.index >= b["buy"]) & (close.index < end)] = b["cash_before"] - b["paid"]
        cash_by_day[close.index >= end] = b["cash_after"]
        if b["sell"] is None:
            cash_by_day[close.index == end] = b["cash_before"] - b["paid"]
    value = cash_by_day + shares_by_day * close * (1 - c)
    if book and book[-1]["sell"] is None:
        value.iloc[-1] = book[-1]["cash_after"]
    bh_shares = int(capital // (close.iloc[0] * (1 + c)))
    bh_value = capital - bh_shares * close.iloc[0] * (1 + c) + bh_shares * close * (1 - c)
    return book, cash, value, bh_value, bh_shares


def metrics(book, value, bh_value, capital):
    final = float(value.iloc[-1])
    peak = value.cummax()
    closed = [b for b in book if b["sell"] is not None]
    wins = [b for b in closed if b["pnl"] > 0]
    losses = [b for b in closed if b["pnl"] <= 0]
    gp, gl = sum(b["pnl"] for b in wins), abs(sum(b["pnl"] for b in losses))
    return dict(final=final, pnl=final - capital, ret=100 * (final / capital - 1),
                bh_final=float(bh_value.iloc[-1]), bh_ret=100 * (float(bh_value.iloc[-1]) / capital - 1),
                max_dd=float((100 * (peak - value) / peak).max()),
                closed=len(closed), wins=len(wins), losses=len(losses),
                win_rate=100 * len(wins) / len(closed) if closed else 0.0,
                gross_profit=gp, gross_loss=gl,
                profit_factor=gp / gl if gl > 0 else (999.0 if gp > 0 else 0.0),
                avg_win=float(np.mean([b["pnl_pct"] for b in wins])) if wins else 0.0,
                avg_loss=float(np.mean([b["pnl_pct"] for b in losses])) if losses else 0.0,
                charges=sum(b["charges"] for b in book),
                stops=sum(1 for b in closed if b.get("stop")),
                days_in=sum(b["held"] for b in book), days=len(value))


def trade_reason(b):
    """One-line reason for a single trade's result."""
    if b["sell"] is None:
        return ("Abhi bhi hold: %s %.1f%% (open)" % ("profit" if b["pnl"] >= 0 else "loss", b["pnl_pct"]))
    if b.get("stop"):
        return "Stop-loss laga: price buy se 10%% neeche aaya, loss %.1f%% par kata" % b["pnl_pct"]
    if b["pnl"] > 0:
        return "Daily RRG ne trend pakda, Weakening/Lagging aane par %+.1f%% profit book hua" % b["pnl_pct"]
    if b["held"] <= 3:
        return "Jhoota signal: %d session me hi Daily RRG neeche gaya (%+.1f%%)" % (b["held"], b["pnl_pct"])
    return "Momentum fade hua, exit tak price buy se neeche tha (%+.1f%%)" % b["pnl_pct"]


def explain(book, m, name):
    """Why the strategy made or lost money - English and Hinglish lines."""
    profit = m["pnl"] >= 0
    head = "%s: %+.1f%% (%s₹%s)" % ("PROFIT" if profit else "LOSS", m["ret"], "+" if profit else "-",
                                     format(abs(round(m["pnl"])), ",d"))
    en, hi = [], []
    if not book:
        return dict(headline="No trade yet", profit=True, bullets=[(
            "The Daily RRG never gave a buy signal after the warm-up, so the money stayed in cash.",
            "Warm-up ke baad Daily RRG ne buy signal nahi diya, isliye paisa cash me hi raha.")])
    if m["wins"]:
        en.append("%d winning trade(s) earned ₹%s (average %+.1f%% each)."
                  % (m["wins"], format(round(m["gross_profit"]), ",d"), m["avg_win"]))
        hi.append("%d trade me profit hua, kul ₹%s (har trade avg %+.1f%%)."
                  % (m["wins"], format(round(m["gross_profit"]), ",d"), m["avg_win"]))
    if m["losses"]:
        en.append("%d losing trade(s) cost ₹%s (average %+.1f%% each)."
                  % (m["losses"], format(round(m["gross_loss"]), ",d"), m["avg_loss"]))
        hi.append("%d trade me loss hua, kul ₹%s (har trade avg %+.1f%%)."
                  % (m["losses"], format(round(m["gross_loss"]), ",d"), m["avg_loss"]))
    if m["stops"]:
        en.append("The 10%% stop-loss fired %d time(s), capping those losses near 10%%." % m["stops"])
        hi.append("10%% stop-loss %d baar laga, jisse loss lagbhag 10%% par ruk gaya." % m["stops"])
    quick = [b for b in book if b["sell"] is not None and b["held"] <= 3 and b["pnl"] <= 0]
    if quick:
        en.append("%d trade(s) were whipsaws: the Daily RRG turned down within 3 sessions." % len(quick))
        hi.append("%d trade jhoote signal the: 3 session ke andar hi Daily RRG neeche aa gaya." % len(quick))
    gap = m["ret"] - m["bh_ret"]
    if gap < -5:
        en.append("Buy & hold did %.1f points better: the stock kept rising while the strategy sat in cash "
                  "during Weakening/Lagging spells." % -gap)
        hi.append("Buy & hold %.1f point behtar raha: stock badhta raha jab strategy Weakening/Lagging me "
                  "cash me baithi thi." % -gap)
    elif gap > 5:
        en.append("The strategy beat buy & hold by %.1f points by staying out during weak phases." % gap)
        hi.append("Strategy ne buy & hold ko %.1f point se haraya, kyunki kamzor phase me bahar rahi." % gap)
    en.append("Charges paid: ₹%s." % format(round(m["charges"]), ",d"))
    hi.append("Charges me ₹%s gaye." % format(round(m["charges"]), ",d"))
    open_b = book[-1] if book[-1]["sell"] is None else None
    if open_b:
        en.append("One trade is still open (bought %s), marked at the latest close."
                  % open_b["buy"].strftime("%d %b %Y"))
        hi.append("Ek trade abhi khula hai (%s ko kharida), aaj ke close par gina gaya hai."
                  % open_b["buy"].strftime("%d %b %Y"))
    return dict(headline=head, profit=profit, bullets=list(zip(en, hi)))
