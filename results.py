"""
results.py - saved results: the heavy numbers are calculated ONCE (build_cache.py, run by the daily GitHub
Action or the app's "Refresh data now" button) and saved in data/results.pkl.gz. The pages read them instead
of recalculating; any setting that is not saved is calculated live as before.

A saved file is used only if it was built from the same code and the same data (last NIFTY 50 session);
otherwise it is ignored, so a page never shows numbers that do not match the data on screen.
"""
import gzip
import hashlib
import os
import pickle
import time
from datetime import datetime, timedelta, timezone

import rrg_core as core
import compute as cp

ROOT = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(ROOT, "data", "results.pkl.gz")
SMAS = (0, core.SMA_DEFAULT)          # RRG bases saved: daily close and SMA 14
IST = timezone(timedelta(hours=5, minutes=30))
_LOADED = {"mtime": None, "bundle": {}}


def fingerprint():
    """Hash of the code the saved numbers depend on."""
    h = hashlib.sha256()
    for f in ("rrg_core.py", "compute.py", "results.py"):
        with open(os.path.join(ROOT, f), "rb") as fh:
            h.update(fh.read().replace(b"\r\n", b"\n"))      # same hash on Windows (CRLF) and Linux (LF)
    return h.hexdigest()[:16]


def bundle():
    """The saved results if they match this code and data, else {} (read from disk once per file version)."""
    m = os.path.getmtime(PATH) if os.path.exists(PATH) else None
    if m != _LOADED["mtime"]:
        b = {}
        if m is not None:
            try:
                with gzip.open(PATH, "rb") as fh:
                    b = pickle.load(fh)
            except Exception:
                b = {}
        _LOADED.update(mtime=m, bundle=b)
    b = _LOADED["bundle"]
    if not b:
        return {}
    try:                                   # any problem -> no saved results; the pages calculate live instead
        meta = b.get("meta", {})
        if meta.get("fingerprint") != fingerprint() or meta.get("data_through") != core.data_through():
            return {}
    except Exception:
        return {}
    return b


def meta():
    return bundle().get("meta", {})


def saved_meta():
    """Meta of the file on disk even if it no longer matches the code or data ({} if none)."""
    try:
        with gzip.open(PATH, "rb") as fh:
            return pickle.load(fh).get("meta", {})
    except Exception:
        return {}


def get(key, default=None):
    """A saved item, e.g. ("tp", symbol, sma, stop_loss, take_profit) -> dict; default if not saved."""
    return bundle().get("items", {}).get(key, default)


def is_default_cost(cost):
    return abs(float(cost) - core.COST_PCT) < 1e-9


def build(refresh=False, log=print):
    """Optionally refresh all prices, then calculate and save every saved item. -> meta dict"""
    t0 = time.time()
    errors = core.refresh_all(log=log) if refresh else {}
    symbols = [s for s, _ in core.STOCKS]
    items = {}
    cost = core.COST_PCT
    r = cp.REPLAY_DEFAULT
    for i, s in enumerate(symbols, 1):
        for sma in SMAS:
            for sl in core.STOP_LOSS_OPTIONS:
                for tp in cp.EXITS:
                    items[("tp", s, sma, sl, tp)] = cp.tp_stock(s, sma, sl, cost, tp)
            items[("rule", s, sma)] = cp.rule_check_stock(s, sma, cost)
            items[("replay", s, sma)] = cp.replay(s, sma, r["tp"], r["sl"], cost, r["amount"], r["only6"])
        if i % 10 == 0 or i == len(symbols):
            log("calculated %d/%d stocks" % (i, len(symbols)))
    meta = {"fingerprint": fingerprint(), "data_through": core.data_through(), "stocks": len(symbols),
            "built_at": datetime.now(IST).strftime("%d %b %Y %H:%M IST"), "seconds": round(time.time() - t0),
            "download_errors": errors}
    tmp = PATH + ".tmp"
    with gzip.open(tmp, "wb") as fh:
        pickle.dump({"meta": meta, "items": items}, fh, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, PATH)
    _LOADED["mtime"] = None
    log("saved %s (%d items, %.0f KB, %ds)" % (PATH, len(items), os.path.getsize(PATH) / 1024, meta["seconds"]))
    return meta
