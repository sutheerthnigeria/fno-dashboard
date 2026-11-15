"""Download NSE end-of-day files into data/raw/.

Files (all public, from nsearchives.nseindia.com):
  fo/      F&O bhavcopy (UDiFF format)            BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip
  cm/      Cash-market bhavcopy (UDiFF format)    BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip
  deliv/   Full bhavcopy with delivery qty/%      sec_bhavdata_full_DDMMYYYY.csv
  index/   Closing values of all NSE indices      ind_close_all_DDMMYYYY.csv

Usage:
  python pipeline/fetch_nse.py                  # last 10 calendar days
  python pipeline/fetch_nse.py --days 400       # backfill ~16 months
  python pipeline/fetch_nse.py --start 2026-01-01 --end 2026-03-31

Already-downloaded days are skipped; holidays (404) are remembered so they are not retried.
"""
import argparse
import datetime as dt
import json
import sys
import time

import requests

from config import RAW, ROOT

BASE = "https://nsearchives.nseindia.com"
SOURCES = {
    "fo": lambda d: f"{BASE}/content/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip",
    "cm": lambda d: f"{BASE}/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip",
    "deliv": lambda d: f"{BASE}/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv",
    "index": lambda d: f"{BASE}/content/indices/ind_close_all_{d:%d%m%Y}.csv",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}
MISSING_FILE = ROOT / "data" / "missing.json"
DAILY = ROOT / "data" / "daily"


def session():
    s = requests.Session()
    s.headers.update(HEADERS)
    try:  # warm-up for cookies; harmless if it fails
        s.get("https://www.nseindia.com", timeout=10)
    except requests.RequestException:
        pass
    return s


def target_path(kind, d):
    ext = ".csv.zip" if kind in ("fo", "cm") else ".csv"
    return RAW / kind / f"{d:%Y-%m-%d}{ext}"


def fetch_day(s, d, missing):
    got = {}
    if (DAILY / f"{d:%Y-%m-%d}.csv.gz").exists():  # already summarised by build.py
        return got
    for kind, url_fn in SOURCES.items():
        path = target_path(kind, d)
        key = f"{kind}:{d:%Y-%m-%d}"
        if path.exists() or key in missing:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        url = url_fn(d)
        for attempt in range(3):
            try:
                r = s.get(url, timeout=30)
            except requests.RequestException as e:
                print(f"  {kind} {d}: network error ({e}); retry {attempt + 1}")
                time.sleep(2 + attempt * 3)
                continue
            if r.status_code == 200 and len(r.content) > 200:
                path.write_bytes(r.content)
                got[kind] = len(r.content)
                break
            if r.status_code == 404:
                missing.add(key)
                break
            print(f"  {kind} {d}: HTTP {r.status_code}; retry {attempt + 1}")
            time.sleep(2 + attempt * 3)
        time.sleep(0.4)  # be polite
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10, help="calendar days back from today")
    ap.add_argument("--start")
    ap.add_argument("--end")
    a = ap.parse_args()

    today = dt.date.today()
    end = dt.date.fromisoformat(a.end) if a.end else today
    start = dt.date.fromisoformat(a.start) if a.start else end - dt.timedelta(days=a.days)

    missing = set(json.loads(MISSING_FILE.read_text())) if MISSING_FILE.exists() else set()
    # don't remember "missing" for the last 2 days: files may simply not be published yet
    recent = {f"{k}:{(today - dt.timedelta(days=i)):%Y-%m-%d}" for k in SOURCES for i in range(3)}
    missing -= recent

    s = session()
    d, n_ok = start, 0
    while d <= end:
        if d.weekday() < 5:
            got = fetch_day(s, d, missing)
            if got:
                n_ok += 1
                print(f"{d}: " + ", ".join(f"{k} {v // 1024} KB" for k, v in got.items()))
        d += dt.timedelta(days=1)

    MISSING_FILE.parent.mkdir(parents=True, exist_ok=True)
    MISSING_FILE.write_text(json.dumps(sorted(missing)))
    print(f"Done. New trading days downloaded: {n_ok}")
    have_fo = list((RAW / "fo").glob("*.zip")) if (RAW / "fo").exists() else []
    if not have_fo and not list(DAILY.glob("*.csv.gz")):
        print("WARNING: no F&O files present. NSE may be blocking this network.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
