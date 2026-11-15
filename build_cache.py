"""
Calculate the heavy results once and save them in data/results.pkl.gz, so the app only reads them.

    python build_cache.py            # use the saved price copies in data/
    python build_cache.py --refresh  # first download fresh prices for every stock and NIFTY 50

Run daily after the NSE close by the GitHub Action (.github/workflows/refresh-data.yml), or from the app's
"Refresh data now" button. Prints "RESULT: CHANGED" when there is a new session (or new code) to save,
"RESULT: SAME" otherwise; under GitHub Actions it also sets the step output changed=true/false.
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")

import results

if __name__ == "__main__":
    prev = results.saved_meta()
    m = results.build(refresh="--refresh" in sys.argv)
    changed = prev.get("data_through") != m["data_through"] or prev.get("fingerprint") != m["fingerprint"]
    print("data through:", m["data_through"].date() if m["data_through"] is not None else None,
          "| built:", m["built_at"], "| download errors:", len(m["download_errors"]))
    for k, v in list(m["download_errors"].items())[:10]:
        print("  ", k, v)
    print("RESULT:", "CHANGED" if changed else "SAME")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write("changed=%s\n" % ("true" if changed else "false"))
            fh.write("last=%s\n" % (m["data_through"].date() if m["data_through"] is not None else ""))
