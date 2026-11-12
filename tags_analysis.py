"""
Tags analysis tab (own page in the top navigation of app.py), laid out like the help folder app's Tags tab.

For every stock in a tag: the Daily RRG strategy's closed trades since the stock's first RRG session, each
with a fixed amount invested (whole shares), profit % per trade, days held, and daily profit %
(= sum of profit % / sum of calendar days held). The tag's figure is the simple average of daily profit %
over the stocks that had a closed trade. A comparison grid shows the same for Daily-close vs SMA-price RRG
at 10% and 15% stop-loss. Everything is driven by rrg_core.TAGS, so new tags appear here automatically.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis as an
import rrg_core as core
from rrg_core import INFO

TRADE_AMOUNT = 100000.0
FROM_DEFAULT = "2026-04-01"
QUAD_COLOR = {"Leading": "#2e8b57", "Weakening": "#e6a700", "Lagging": "#c0392b", "Improving": "#2a6fdb"}


# ---- data -------------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def stock_rrg(symbol, sma, token):
    """(status, aligned prices, rrg) for one stock. status '' = ok."""
    try:
        al, _ = core.aligned(symbol)
    except Exception:
        return ("NSE SME stock — add NSE CSV files" if INFO[symbol]["source"] == "nse_csv" else "No data"), None, None
    rrg, _ = core.daily_rrg(al, sma)
    if rrg.empty:
        return "Only %d sessions — too few for RRG" % len(al), al, None
    return "", al, rrg


@st.cache_data(show_spinner=False)
def stock_trades(symbol, sma, stop_loss, token, since=None):
    """(status, first RRG date, closed trades bought on/after `since`) for one stock."""
    status, _, rrg = stock_rrg(symbol, sma, token)
    if status:
        return status, None, []
    trades, _, _ = core.run_strategy(rrg, stop_loss, 0.0)       # charges applied below, per fixed amount
    closed = [t for t in trades if not t["open"] and (since is None or t["buy"] >= since)]
    return "", rrg.index[0], closed


def profit_pct(t, cost):
    """Profit % of one trade with TRADE_AMOUNT invested: whole shares at the buy price, sold at the sell price."""
    c = cost / 100.0
    shares = int(TRADE_AMOUNT // (t["buy_px"] * (1 + c)))
    if shares == 0:
        return 0.0
    paid, got = shares * t["buy_px"] * (1 + c), shares * t["sell_px"] * (1 - c)
    return 100.0 * (got - paid) / paid


def tag_report(tag, sma, stop_loss, cost, token, since=None):
    rows, left_out = {}, {}
    for s in members:
        status, first, trades = stock_trades(s, sma, stop_loss, token, since)
        if status:
            left_out[s] = status
            continue
        profits = [profit_pct(t, cost) for t in trades]
        days = [int((t["sell"] - t["buy"]).days) for t in trades]
        rows[s] = dict(first=first, trades=trades, profits=profits, days=days, profit_sum=sum(profits),
                       days_sum=sum(days), daily=sum(profits) / sum(days) if sum(days) > 0 else None)
    daily = [r["daily"] for r in rows.values() if r["daily"] is not None]
    n = sum(len(r["trades"]) for r in rows.values())
    return dict(rows=rows, left_out=left_out, tickers=len(rows), trades=n, with_trades=len(daily),
                avg_daily=sum(daily) / len(daily) if daily else None,
                avg_days=sum(r["days_sum"] for r in rows.values()) / n if n else None)


# ---- page -------------------------------------------------------------------------------------
st.title("🏷️ Tags analysis")
st.caption("Profitability of Strategy 2 · Version 3 rules on the **Daily** RRG for every stock in a tag, "
           "from each IPO's first RRG session.")
token = st.session_state.get("token", 0)

c1, c2, c3, c4, c5, c6 = st.columns([2.2, 1.6, 0.9, 1.2, 1, 1.2])
tag = c1.selectbox("Tag", ["All"] + core.TAGS, key="tags_page_tag",
                   format_func=lambda g: "%s (%d stocks)" % (g, len(core.stocks_for_tag(g))))
basis = c2.radio("RRG built on", ["Daily close", "SMA price"], horizontal=True, key="tags_basis")
sma = int(c3.number_input("SMA days", 2, 200, core.SMA_DEFAULT, 1, key="tags_sma",
                          disabled=basis != "SMA price")) if basis == "SMA price" else 0
stop_loss = c4.radio("Stop-loss", core.STOP_LOSS_OPTIONS, horizontal=True, key="tags_sl",
                     format_func=lambda v: "%g%%" % v)
cost = c5.number_input("Charges / side (%)", 0.0, 1.0, core.COST_PCT, 0.01, key="tags_cost")
since = pd.Timestamp(c6.date_input("From", value=pd.Timestamp(FROM_DEFAULT).date(), key="tags_from"))
basis_txt = "SMA %d price" % sma if sma else "daily close"
tag_name = "All stocks" if tag == "All" else tag
q = st.text_input("🔍 Search stock", key="tags_search", placeholder="name, ticker, sector, city or tag — leave empty for the whole tag",
                  help="Every word must match, e.g. 'kaynes', 'jewel', 'technology'. Averages and charts below then use only "
                       "the matching stocks.")
members = an.search_stocks(core.stocks_for_tag(tag), q)
if q and not members:
    st.warning("No stock in %s matches “%s”." % (tag_name, q))
    st.stop()
if q:
    st.caption("🔍 %d of %d stocks match “%s”: %s" % (len(members), len(core.stocks_for_tag(tag)), q, ", ".join(members)))
    tag_name = "%s · search “%s”" % (tag_name, q)

st.markdown("### Tag: %s · %s to %s" % (tag_name, since.strftime("%d %b %Y"), "now"))
st.caption("Trades bought on or after **%s** (the RRG itself uses the whole history for its warm-up). "
           % since.strftime("%d %b %Y") +
           "Daily RRG built on **%s**, **%g%%** stop-loss. Buy the day after the Daily RRG turns Improving/Leading, "
           "sell the day after it turns Weakening/Lagging, both at (open + close) ÷ 2; stop-loss sells at that day's close. "
           "Each trade assumes ₹%s invested (whole shares), charges %g%% per side. Only closed trades count; "
           "days held are calendar days." % (basis_txt, stop_loss, format(TRADE_AMOUNT, ",.0f"), cost))

with st.spinner("Running the strategy for every stock in the tag..."):
    rep = tag_report(tag, sma, stop_loss, cost, token, since)
if rep["left_out"]:
    st.caption("Not included: " + " · ".join("%s (%s)" % (s, why) for s, why in rep["left_out"].items()))

k1, k2, k3, k4 = st.columns(4)
k1.metric("Tickers", rep["tickers"])
k2.metric("Closed trades", rep["trades"])
k3.metric("Average daily profit % (simple)", "%.4f%%" % rep["avg_daily"] if rep["avg_daily"] is not None else "—",
          help="Simple average of 'Daily profit %' over the tickers that had at least one closed trade.")
k4.metric("Avg days held per trade", "%.1f" % rep["avg_days"] if rep["avg_days"] is not None else "—")

table = pd.DataFrame([{
    "Ticker": s, "Stock": INFO[s]["name"], "Sector": an.sector(s), "RRG from": r["first"].strftime("%d %b %Y"),
    "Number of trades": len(r["trades"]),
    "Profit % per trade": ", ".join("%.2f" % p for p in r["profits"]) or "—",
    "Days held per trade": ", ".join(str(d) for d in r["days"]) or "—",
    "Sum of profit %": round(r["profit_sum"], 2), "Sum of days held": r["days_sum"],
    "Daily profit %": round(r["daily"], 4) if r["daily"] is not None else None,
} for s, r in rep["rows"].items()])
if not table.empty:
    st.dataframe(table, hide_index=True, width="stretch", height=38 + 35 * len(table),
                 column_config={"Profit % per trade": st.column_config.TextColumn(width="large"),
                                "Days held per trade": st.column_config.TextColumn(width="medium"),
                                "Daily profit %": st.column_config.NumberColumn(format="%.4f"),
                                "Sum of profit %": st.column_config.NumberColumn(format="%.2f")})
    if rep["with_trades"] < rep["tickers"]:
        st.caption("%d ticker(s) had no closed trade, so they have no daily profit %% and are left out of the average."
                   % (rep["tickers"] - rep["with_trades"]))

    # ---- one stock's trades ----
    st.markdown("#### Individual stock — every closed trade")
    pick = st.selectbox("Stock", list(rep["rows"]), key="tags_stock",
                        format_func=lambda s: "%s — %s" % (s, INFO[s]["name"]))
    r = rep["rows"][pick]
    if r["trades"]:
        st.dataframe(pd.DataFrame([{
            "#": i + 1, "Buy date": t["buy"].strftime("%d %b %Y"), "Buy ₹": round(t["buy_px"], 2),
            "Sell date": t["sell"].strftime("%d %b %Y"), "Sell ₹": round(t["sell_px"], 2),
            "Exit": "Stop-loss" if t.get("stop") else "Daily RRG", "Days held": d, "Profit %": round(p, 2),
        } for i, (t, p, d) in enumerate(zip(r["trades"], r["profits"], r["days"]))]),
            hide_index=True, width="stretch")
    else:
        st.info("No closed trade for %s." % INFO[pick]["name"])
else:
    st.warning("No stock in this tag has enough history yet.")

# ---- static time view: every stock in the tag, from `since` to now -------------------------------
st.markdown("---")
st.markdown("### Static time view · %s · %s to now" % (tag_name, since.strftime("%d %b %Y")))
st.caption("No slider — the whole period in one picture. Daily RRG built on **%s**. A stock listed after %s starts "
           "on its first RRG session." % (basis_txt, since.strftime("%d %b %Y")))
views = {}
for s in members:
    status, al, rrg = stock_rrg(s, sma, token)
    if status:
        continue
    r = rrg[rrg.index >= since]
    a = al[al.index >= since]
    if len(r) and len(a):
        views[s] = (a, r)
if not views:
    st.info("No stock in this tag has RRG data in this period.")
else:
    order = sorted(views, key=lambda s: views[s][1].index[0])
    t1, t2, t3 = st.tabs(["Quadrant timeline", "RRG trails (static)", "Price % change"])
    with t1:   # one row per stock, one coloured cell per session
        dates = sorted(set().union(*[set(views[s][1].index) for s in order]))
        code = {q: i for i, q in enumerate(core.ORDER)}
        z = [[code.get(views[s][1]["Quadrant"].get(d), None) for d in dates] for s in order]
        txt = [[views[s][1]["Quadrant"].get(d, "") for d in dates] for s in order]
        cs = []
        for i, q in enumerate(core.ORDER):
            cs += [[i / 4, QUAD_COLOR[q]], [(i + 1) / 4, QUAD_COLOR[q]]]
        hm = go.Figure(go.Heatmap(z=z, x=dates, y=order, text=txt, zmin=-0.5, zmax=3.5, colorscale=cs,
                                  showscale=False, xgap=0, ygap=2,
                                  hovertemplate="<b>%{y}</b> · %{x|%d %b %Y}<br>%{text}<extra></extra>"))
        hm.update_layout(height=80 + 26 * len(order), margin=dict(l=10, r=10, t=10, b=10),
                         yaxis=dict(autorange="reversed"), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb")
        st.plotly_chart(hm, width="stretch", key="tv_heat")
        st.markdown(" ".join("<span style='background:%s;color:white;padding:2px 8px;border-radius:4px;"
                             "font-size:0.85rem'>%s</span>" % (QUAD_COLOR[q], q) for q in core.ORDER),
                    unsafe_allow_html=True)
        now_q = pd.DataFrame([{"Ticker": s, "Stock": INFO[s]["name"], "RRG from": views[s][1].index[0].strftime("%d %b %Y"),
                               **{q: int((views[s][1]["Quadrant"] == q).sum()) for q in core.ORDER},
                               "Now": views[s][1]["Quadrant"].iloc[-1]} for s in order])
        st.caption("Sessions in each quadrant during the period, and the quadrant on the latest session:")
        st.dataframe(now_q, hide_index=True, width="stretch")
    with t2:   # every stock's full trail over the period, end point labelled
        fig = go.Figure()
        pal = ["#2a78d6", "#eb6834", "#2e9e83", "#9b59b6", "#c0392b", "#16a085", "#d35400", "#7f8c8d", "#8e44ad",
               "#27ae60", "#e67e22", "#34495e", "#1abc9c", "#f39c12", "#2980b9", "#b03a2e", "#6c5ce7", "#00897b",
               "#795548", "#5d6d7e", "#ad1457", "#558b2f", "#0277bd", "#ff8f00", "#4e342e", "#283593"]
        allx, ally = [], []
        for i, s in enumerate(order):
            r = views[s][1]; c = pal[i % len(pal)]
            allx += list(r["RS_Ratio"]); ally += list(r["RS_Momentum"])
            fig.add_trace(go.Scatter(x=r["RS_Ratio"], y=r["RS_Momentum"], mode="lines", line=dict(color=c, width=1.4),
                                     opacity=0.55, name=s, legendgroup=s, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=r["RS_Ratio"].iloc[-1:], y=r["RS_Momentum"].iloc[-1:], mode="markers+text",
                                     text=[s], textposition="top center", marker=dict(size=10, color=c,
                                     line=dict(color="white", width=1)), legendgroup=s, showlegend=False,
                                     hovertemplate="<b>%s</b><br>%s<br>%s<br>RS-Ratio %%{x:.2f}<br>RS-Momentum %%{y:.2f}"
                                                   "<extra></extra>" % (INFO[s]["name"], r.index[-1].strftime("%d %b %Y"),
                                                                        r["Quadrant"].iloc[-1])))
            fig.add_trace(go.Scatter(x=r["RS_Ratio"].iloc[:1], y=r["RS_Momentum"].iloc[:1], mode="markers",
                                     marker=dict(size=6, color=c, symbol="circle-open"), legendgroup=s,
                                     showlegend=False, hovertemplate="%s start %s<extra></extra>"
                                     % (s, r.index[0].strftime("%d %b %Y"))))
        lo_x, hi_x = min(allx + [100]), max(allx + [100]); lo_y, hi_y = min(ally + [100]), max(ally + [100])
        px, py = (hi_x - lo_x) * 0.05, (hi_y - lo_y) * 0.05
        for q, (x0, x1, y0, y1) in {"Improving": (lo_x - px, 100, 100, hi_y + py), "Leading": (100, hi_x + px, 100, hi_y + py),
                                    "Lagging": (lo_x - px, 100, lo_y - py, 100), "Weakening": (100, hi_x + px, lo_y - py, 100)}.items():
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=QUAD_COLOR[q], opacity=0.07,
                          line_width=0, layer="below")
            fig.add_annotation(x=x0 if x0 < 100 else x1, y=y1 if y1 > 100 else y0, text="<b>%s</b>" % q, showarrow=False,
                               xanchor="left" if x0 < 100 else "right", yanchor="top" if y1 > 100 else "bottom",
                               font=dict(color=QUAD_COLOR[q]))
        fig.add_hline(y=100, line_color="#999", line_width=1); fig.add_vline(x=100, line_color="#999", line_width=1)
        fig.update_layout(height=640, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="RS-Ratio",
                          yaxis_title="RS-Momentum", xaxis=dict(range=[lo_x - px, hi_x + px]),
                          yaxis=dict(range=[lo_y - py, hi_y + py]), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
                          legend=dict(font=dict(size=10)))
        st.plotly_chart(fig, width="stretch", key="tv_rrg")
        st.caption("Each line is one stock's whole path from its start (open circle) to the latest session (labelled dot). "
                   "Click a name in the legend to hide it, double-click to show only that stock.")
    with t3:   # % change of the close since each stock's first session in the period
        fig = go.Figure()
        perf = []
        for i, s in enumerate(order):
            a = views[s][0]; pctc = 100 * (a["Close"] / a["Close"].iloc[0] - 1)
            perf.append((s, pctc.iloc[-1], a.index[0]))
            fig.add_trace(go.Scatter(x=pctc.index, y=pctc, mode="lines", name=s, line=dict(width=1.6, color=pal[i % len(pal)]),
                                     hovertemplate="<b>%s</b> %%{x|%%d %%b %%Y}<br>%%{y:+.1f}%%<extra></extra>" % s))
        bench = None
        for s in order:
            b = views[s][0]["Bench"]
            if bench is None or b.index[0] < bench.index[0]:
                bench = b
        fig.add_trace(go.Scatter(x=bench.index, y=100 * (bench / bench.iloc[0] - 1), mode="lines", name=core.BENCH,
                                 line=dict(color="black", width=2.5, dash="dash")))
        fig.add_hline(y=0, line_color="#999", line_width=1)
        fig.update_layout(height=560, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="% change", hovermode="closest",
                          plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb", legend=dict(font=dict(size=10)))
        st.plotly_chart(fig, width="stretch", key="tv_perf")
        st.caption("Close-price change from each stock's first session in the period (its listing day if it listed later); "
                   "dashed black = %s." % core.BENCH)
        st.dataframe(pd.DataFrame([{"Ticker": s, "Stock": INFO[s]["name"], "From": d.strftime("%d %b %Y"),
                                    "Change %": round(v, 2)} for s, v, d in sorted(perf, key=lambda x: -x[1])]),
                     hide_index=True, width="stretch")

# ---- comparison: price basis x stop-loss --------------------------------------------------------
st.markdown("---")
st.markdown("### Daily close vs SMA %d price, by stop-loss" % (sma or core.SMA_DEFAULT))
n_cmp = sma or core.SMA_DEFAULT
combos = [("Daily close", 0, sl) for sl in core.STOP_LOSS_OPTIONS] + \
         [("SMA %d price" % n_cmp, n_cmp, sl) for sl in core.STOP_LOSS_OPTIONS]
st.caption("Same tag, same rules and charges; only the RRG price basis and the stop-loss change. "
           "Bars = average daily profit % of the tag; the table shows each stock's sum of profit % per setup.")
with st.spinner("Comparing setups..."):
    reps = {(b, sl): tag_report(tag, n, sl, cost, token, since) for b, n, sl in combos}
fig = go.Figure()
for sl, color in zip(core.STOP_LOSS_OPTIONS, ["#2a78d6", "#e65100"]):
    xs = [b for b, n, s in combos if s == sl]
    ys = [reps[(b, sl)]["avg_daily"] or 0 for b in xs]
    fig.add_trace(go.Bar(x=xs, y=ys, name="%g%% stop-loss" % sl, marker_color=color,
                         text=["%.4f%%" % y for y in ys], textposition="outside",
                         hovertemplate="%{x} · " + "%g%%" % sl + " stop-loss<br>Avg daily profit %{y:.4f}%<extra></extra>"))
fig.update_layout(barmode="group", height=360, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="Avg daily profit %",
                  legend=dict(orientation="h", y=1.12), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb")
st.plotly_chart(fig, width="stretch", key="tags_cmp")

cmp_rows = []
for s in members:
    row = {"Ticker": s, "Stock": INFO[s]["name"]}
    for b, n, sl in combos:
        rr = reps[(b, sl)]["rows"].get(s)
        row["%s · %g%% SL" % (b, sl)] = round(rr["profit_sum"], 2) if rr else None
    cmp_rows.append(row)
cmp = pd.DataFrame(cmp_rows)
summary = {"Ticker": "AVG daily %", "Stock": "tag average"}
summary.update({"%s · %g%% SL" % (b, sl): round(reps[(b, sl)]["avg_daily"], 4) if reps[(b, sl)]["avg_daily"] is not None
                else None for b, n, sl in combos})
st.dataframe(pd.concat([cmp, pd.DataFrame([summary])], ignore_index=True), hide_index=True, width="stretch",
             height=38 + 35 * (len(cmp) + 1))
st.caption("Sum of profit % of closed trades per stock (empty = no data / too short). Historical test, not advice.")
