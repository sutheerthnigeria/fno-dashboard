"""
Fetch recent NSE corporate announcements for every F&O stock and write
  site/data/news/<SYM>.json

Uses the public NSE corporate announcements endpoint (no login required).
Run after fetch_nse.py and before build.py, or standalone.

Schema written:
  {sym, fetched_on, items:[{title, date, category, url}]}
"""
import csv, json, pathlib, time, datetime, sys, argparse
import urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
NEWS_DIR = ROOT / "site" / "data" / "news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)

SECTORS_CSV = ROOT / "data" / "sectors.csv"

NSE_ANN_URL = (
    "https://www.nseindia.com/api/top-corp-info"
    "?symbol={sym}&market=equities"
)
# NSE requires browser-like headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nseindia.com/",
    "X-Requested-With": "XMLHttpRequest",
}
SESSION_URL = "https://www.nseindia.com/"
SLEEP_BETWEEN = 0.6   # seconds between stocks to avoid rate-limiting


def _session_cookies(timeout: int = 10) -> str:
    """Warm up NSE session and collect cookies."""
    req = urllib.request.Request(SESSION_URL, headers={
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "text/html",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # collect Set-Cookie headers
            raw = resp.headers.get_all("Set-Cookie") or []
            cookies = "; ".join(
                c.split(";")[0].strip() for c in raw if "=" in c.split(";")[0]
            )
            return cookies
    except Exception:
        return ""


def _fetch_announcements(sym: str, cookies: str, timeout: int = 12):
    url = NSE_ANN_URL.format(sym=urllib.parse.quote(sym))
    hdrs = dict(HEADERS)
    if cookies:
        hdrs["Cookie"] = cookies
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def _parse_announcements(data, sym: str):
    """Extract items from NSE API response."""
    # NSE returns {"corporate": [...]} or {"data": [...]}
    items = []
    raw = []
    if isinstance(data, dict):
        raw = data.get("corporate") or data.get("data") or []
    elif isinstance(data, list):
        raw = data

    for entry in raw[:20]:
        # Different NSE endpoints use different key names
        title = (entry.get("subject") or entry.get("desc") or
                 entry.get("headline") or entry.get("title") or "").strip()
        date  = (entry.get("exchdisstime") or entry.get("bm_timestamp") or
                 entry.get("date") or "").strip()
        # Normalise date to YYYY-MM-DD
        for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                date = datetime.datetime.strptime(date[:len(fmt)], fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                pass
        category = (entry.get("desc") or entry.get("attchmntType") or
                    entry.get("category") or "").strip()
        # Attachment URL for the filing PDF
        attach = (entry.get("attchmntFile") or entry.get("fileUrl") or "").strip()
        if attach and not attach.startswith("http"):
            attach = "https://nsearchives.nseindia.com/corporate/" + attach.lstrip("/")
        if title:
            items.append({"title": title, "date": date, "category": category, "url": attach or None})
    return items


import urllib.parse  # noqa: F811 (already imported implicitly above)


def run(syms: list[str], verbose: bool = False):
    today = datetime.date.today().isoformat()
    cookies = _session_cookies()
    if verbose:
        print(f"Session cookies obtained: {'yes' if cookies else 'no'}")

    for i, sym in enumerate(syms):
        out_path = NEWS_DIR / f"{sym.replace('/', '_')}.json"
        # Skip if already fetched today
        if out_path.exists():
            try:
                cached = json.loads(out_path.read_text())
                if cached.get("fetched_on") == today:
                    if verbose:
                        print(f"  skip {sym} (cached today)")
                    continue
            except Exception:
                pass

        data = _fetch_announcements(sym, cookies)
        items = _parse_announcements(data, sym) if data else []
        out = {"sym": sym, "fetched_on": today, "items": items}
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        if verbose or i % 20 == 0:
            print(f"  {sym}: {len(items)} announcements")
        time.sleep(SLEEP_BETWEEN)

    print(f"News done: {len(syms)} stocks → {NEWS_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sym",  help="Comma-separated symbols (default: all F&O stocks)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.sym:
        syms = [s.strip() for s in args.sym.split(",")]
    else:
        with open(SECTORS_CSV) as f:
            syms = [r["sym"] for r in csv.DictReader(f)]

    run(syms, verbose=args.verbose)
