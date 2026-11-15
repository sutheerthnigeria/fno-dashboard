"""Turn raw NSE files (+ StockEdge CSVs) into the JSON files the website reads.

Steps
  1. Summarise each trading day's raw files into one row per F&O stock (cached in data/daily/).
  2. Stack the days into a panel and compute rolling metrics per stock.
  3. Merge StockEdge sector / industry / OI-trend labels.
  4. Write site/data/*.json.

If no NSE files exist yet, the site is built from StockEdge CSVs alone (fewer fields).
Run:  python pipeline/build.py
"""
import io
import json
import math
import re
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from config import (AGGRESSIVE_OI_PCT, BENCHMARK, HISTORY_DAYS, OI_NEUTRAL_PCT, RAW,
                    ROOT, SITE_DATA, STOCKEDGE, VALUECHAIN)

DAILY = ROOT / "data" / "daily"
DAILY.mkdir(parents=True, exist_ok=True)
SUMMARY_VERSION = 2  # bump to force re-summarising cached days

# --------------------------------------------------------------------------- raw readers
FO_COLS = {  # UDiFF (Jul-2024 onwards) and legacy names -> ours
    "TradDt": "date", "TIMESTAMP": "date",
    "FinInstrmTp": "inst", "INSTRUMENT": "inst",
    "TckrSymb": "sym", "SYMBOL": "sym",
    "XpryDt": "expiry", "EXPIRY_DT": "expiry",
    "StrkPric": "strike", "STRIKE_PR": "strike",
    "OptnTp": "opt", "OPTION_TYP": "opt",
    "ClsPric": "close", "CLOSE": "close",
    "SttlmPric": "settle", "SETTLE_PR": "settle",
    "UndrlygPric": "und",
    "OpnIntrst": "oi", "OPEN_INT": "oi",
    "ChngInOpnIntrst": "doi", "CHG_IN_OI": "doi",
    "TtlTradgVol": "vol", "CONTRACTS": "vol",
    "TtlTrfVal": "val", "VAL_INLAKH": "val",
    "NewBrdLotQty": "lot",
}
INST_MAP = {"FUTSTK": "STF", "OPTSTK": "STO", "FUTIDX": "IDF", "OPTIDX": "IDO"}


def _read_csv_any(path: Path) -> pd.DataFrame:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
            raw = z.read(name)
    else:
        raw = path.read_bytes()
    df = pd.read_csv(io.BytesIO(raw), skipinitialspace=True, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def read_fo(path):
    df = _read_csv_any(path).rename(columns=FO_COLS)
    df["inst"] = df["inst"].astype(str).str.strip().replace(INST_MAP)
    df = df[df["inst"].isin(["STF", "STO", "IDF", "IDO"])].copy()
    df["sym"] = df["sym"].astype(str).str.strip()
    df["expiry"] = pd.to_datetime(df["expiry"], errors="coerce", dayfirst=False, format="mixed")
    if "opt" in df:
        df["opt"] = df["opt"].astype(str).str.strip()
    for c in ("strike", "close", "settle", "und", "oi", "doi", "vol", "val", "lot"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def read_cm(path):
    df = _read_csv_any(path)
    df = df.rename(columns={"TckrSymb": "sym", "SctySrs": "series", "ClsPric": "close",
                            "PrvsClsgPric": "prev", "OpnPric": "open", "HghPric": "high",
                            "LwPric": "low", "TtlTradgVol": "volume", "TtlTrfVal": "value",
                            "SYMBOL": "sym", "SERIES": "series", "CLOSE": "close",
                            "PREVCLOSE": "prev", "OPEN": "open", "HIGH": "high", "LOW": "low",
                            "TOTTRDQTY": "volume", "TOTTRDVAL": "value"})
    df["series"] = df["series"].astype(str).str.strip()
    df = df[df["series"] == "EQ"].copy()
    df["sym"] = df["sym"].astype(str).str.strip()
    for c in ("close", "prev", "open", "high", "low", "volume", "value"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[["sym", "open", "high", "low", "close", "prev", "volume", "value"]]


def read_deliv(path):
    df = _read_csv_any(path)
    df.columns = [c.strip().upper() for c in df.columns]
    df["SERIES"] = df["SERIES"].astype(str).str.strip()
    df = df[df["SERIES"] == "EQ"].copy()
    out = pd.DataFrame({"sym": df["SYMBOL"].astype(str).str.strip()})
    for src, dst in (("OPEN_PRICE", "d_open"), ("HIGH_PRICE", "d_high"), ("LOW_PRICE", "d_low"),
                     ("CLOSE_PRICE", "d_close"), ("PREV_CLOSE", "d_prev"),
                     ("TTL_TRD_QNTY", "d_volume"), ("DELIV_QTY", "deliv_qty"),
                     ("DELIV_PER", "deliv_pct")):
        out[dst] = pd.to_numeric(df[src].astype(str).str.strip().replace("-", None), errors="coerce").values
    return out


def read_index(path):
    df = _read_csv_any(path)
    df.columns = [c.strip() for c in df.columns]
    name = df["Index Name"].astype(str).str.strip()
    return dict(zip(name, pd.to_numeric(df["Closing Index Value"], errors="coerce")))


# --------------------------------------------------------------------------- daily summary
def max_pain(chain: pd.DataFrame):
    if chain.empty:
        return np.nan
    g = chain.pivot_table(index="strike", columns="opt", values="oi", aggfunc="sum").fillna(0)
    k = g.index.values.astype(float)
    ce = g["CE"].values if "CE" in g else np.zeros(len(k))
    pe = g["PE"].values if "PE" in g else np.zeros(len(k))
    pain = [(ce * np.maximum(0, K - k)).sum() + (pe * np.maximum(0, k - K)).sum() for K in k]
    return float(k[int(np.argmin(pain))])


def summarise_day(day: pd.Timestamp) -> pd.DataFrame:
    fo = read_fo(RAW / "fo" / f"{day:%Y-%m-%d}.csv.zip")
    fut = fo[fo["inst"] == "STF"]
    opt = fo[fo["inst"] == "STO"]
    rows = []
    opt_by = dict(tuple(opt.groupby("sym")))
    empty = opt.iloc[0:0]
    for sym, g in fut.groupby("sym"):
        g = g.sort_values("expiry")
        near = g.iloc[0]
        r = {"sym": sym, "fut_oi": g["oi"].sum(), "near_oi": near["oi"],
             "next_oi": g["oi"].iloc[1] if len(g) > 1 else 0,
             "fut_close": near["close"], "spot_fo": near.get("und", np.nan),
             "fut_vol": g["vol"].sum(), "lot": near.get("lot", np.nan),
             "expiry": near["expiry"]}
        o = opt_by.get(sym, empty)
        if len(o):
            r["call_oi"] = o.loc[o["opt"] == "CE", "oi"].sum()
            r["put_oi"] = o.loc[o["opt"] == "PE", "oi"].sum()
            ne = o["expiry"].min()
            chain = o[o["expiry"] == ne]
            r["max_pain"] = max_pain(chain)
            ce = chain[chain["opt"] == "CE"]
            pe = chain[chain["opt"] == "PE"]
            r["top_ce"] = float(ce.loc[ce["oi"].idxmax(), "strike"]) if len(ce) and ce["oi"].max() > 0 else np.nan
            r["top_pe"] = float(pe.loc[pe["oi"].idxmax(), "strike"]) if len(pe) and pe["oi"].max() > 0 else np.nan
        rows.append(r)
    out = pd.DataFrame(rows)
    cm_p = RAW / "cm" / f"{day:%Y-%m-%d}.csv.zip"
    if cm_p.exists():
        out = out.merge(read_cm(cm_p), on="sym", how="left")
    dl_p = RAW / "deliv" / f"{day:%Y-%m-%d}.csv"
    if dl_p.exists():
        out = out.merge(read_deliv(dl_p), on="sym", how="left")
        for c in ("open", "high", "low", "close", "prev", "volume"):
            if c not in out:
                out[c] = np.nan
            out[c] = out[c].fillna(out["d_" + c])
        out = out.drop(columns=[c for c in out if c.startswith("d_")])
    if "close" not in out:  # no cash file: fall back to the futures file's spot
        out["close"] = out["spot_fo"]
    out["close"] = out["close"].fillna(out["spot_fo"])
    ix_p = RAW / "index" / f"{day:%Y-%m-%d}.csv"
    out["bench"] = read_index(ix_p).get(BENCHMARK, np.nan) if ix_p.exists() else np.nan
    out["date"] = day
    out["v"] = SUMMARY_VERSION
    return out


def load_nse_panel() -> pd.DataFrame:
    """Use the cached daily summary when valid; otherwise summarise from raw files.
    Raw files can be deleted after summarising (the cache is what gets committed)."""
    raw_days = {f.name[:10] for f in (RAW / "fo").glob("*.csv.zip")} if (RAW / "fo").exists() else set()
    cached = {f.name[:10] for f in DAILY.glob("*.csv.gz")}
    frames = []
    for ds in sorted(raw_days | cached):
        day = pd.Timestamp(ds)
        cache = DAILY / f"{ds}.csv.gz"
        df = None
        if cache.exists():
            df = pd.read_csv(cache, parse_dates=["date", "expiry"])
            stale = df.get("v", pd.Series([0])).iloc[0] != SUMMARY_VERSION
            gained_deliv = "deliv_pct" not in df and (RAW / "deliv" / f"{ds}.csv").exists()
            if (stale or gained_deliv) and ds in raw_days:
                df = None
        if df is None:
            try:
                df = summarise_day(day)
            except Exception as e:  # a corrupt/partial download should not kill the build
                print(f"  skip {ds}: {e}")
                continue
            df.to_csv(cache, index=False)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# --------------------------------------------------------------------------- StockEdge
def read_stockedge() -> pd.DataFrame:
    frames = []
    for f in sorted(STOCKEDGE.glob("*.csv")):
        lines = f.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        hdr = next((i for i, l in enumerate(lines) if l.startswith("Date,Stock Name")), None)
        if hdr is None:
            continue
        df = pd.read_csv(io.StringIO("\n".join(lines[hdr:])))
        df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = df.rename(columns={"Stock Name": "name", "Symbol": "sym", "Lot Size": "se_lot",
                            "Sector Name": "sector", "Industry Name": "industry",
                            "MCap Category": "mcap_cat", "Close": "se_close", "Chg %": "se_chg",
                            "Cumulative Future OI": "se_oi", "OI Chg %": "se_oi_chg",
                            "Volume (Times)": "se_vol_mult", "Delivery (Times)": "se_deliv_mult",
                            "Cumulative Call OI": "se_call_oi", "Cumulative Put OI": "se_put_oi",
                            "Put Call Ratio (PCR)": "se_pcr", "PCR Change 1D": "se_pcr_chg",
                            "OI Trend": "se_oi_trend"})
    df["date"] = pd.to_datetime(df["Date"], format="%d-%b-%y", errors="coerce")
    df["sym"] = df["sym"].astype(str).str.strip()
    # "AggressiveShortCover" -> "Agg. Short Cover"
    df["se_oi_trend"] = (df["se_oi_trend"].astype(str)
                         .str.replace("Aggressive", "Agg. ", regex=False)
                         .str.replace(r"(?<=[a-z])(?=[A-Z])", " ", regex=True)
                         .replace("nan", None))
    keep = ["date", "sym", "name", "sector", "industry", "mcap_cat", "se_lot", "se_close", "se_chg",
            "se_oi", "se_oi_chg", "se_vol_mult", "se_deliv_mult", "se_call_oi", "se_put_oi",
            "se_pcr", "se_pcr_chg", "se_oi_trend"]
    return df[keep].drop_duplicates(["date", "sym"], keep="last")


# --------------------------------------------------------------------------- metrics
def classify(chg, oi_chg):
    if pd.isna(chg) or pd.isna(oi_chg):
        return None
    if abs(oi_chg) < OI_NEUTRAL_PCT:
        return "Neutral"
    agg = "Agg. " if abs(oi_chg) >= AGGRESSIVE_OI_PCT else ""
    if oi_chg > 0:
        return agg + ("Long Buildup" if chg >= 0 else "Short Buildup")
    return agg + ("Short Covering" if chg >= 0 else "Long Unwinding")


def rsi(close: pd.Series, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn)


def add_metrics(p: pd.DataFrame) -> pd.DataFrame:
    p = p.sort_values(["sym", "date"]).reset_index(drop=True)
    g = p.groupby("sym", group_keys=False)
    prev_close = g["close"].shift(1)
    if "prev" in p:
        prev_close = p["prev"].where(p["prev"] > 0, prev_close)
    p["chg"] = (p["close"] / prev_close - 1) * 100
    p["oi_chg"] = (p["fut_oi"] / g["fut_oi"].shift(1) - 1) * 100
    p["oi_trend"] = [classify(a, b) for a, b in zip(p["chg"], p["oi_chg"])]
    if "call_oi" in p:
        p["pcr"] = p["put_oi"] / p["call_oi"].replace(0, np.nan)
        p["pcr_chg"] = p.groupby("sym")["pcr"].diff()
    p["roll"] = (p["fut_oi"] - p["near_oi"]) / p["fut_oi"].replace(0, np.nan) * 100
    p["basis_pct"] = (p["fut_close"] / p["close"] - 1) * 100
    p["dte"] = (pd.to_datetime(p["expiry"]) - p["date"]).dt.days
    if "volume" in p:
        p["vol_mult"] = p["volume"] / g["volume"].transform(lambda s: s.shift(1).rolling(20, min_periods=5).mean())
    if "deliv_qty" in p:
        p["deliv_mult"] = p["deliv_qty"] / g["deliv_qty"].transform(lambda s: s.shift(1).rolling(20, min_periods=5).mean())
    for n, lab in ((5, "r_1w"), (21, "r_1m"), (63, "r_3m"), (126, "r_6m"), (252, "r_1y")):
        p[lab] = (p["close"] / g["close"].shift(n) - 1) * 100
    for n in (20, 50, 200):
        p[f"sma{n}"] = g["close"].transform(lambda s: s.rolling(n, min_periods=n).mean())
    p["rsi"] = g["close"].transform(rsi)
    lr = np.log(p["close"] / g["close"].shift(1))
    p["_lr"] = lr
    p["rv20"] = p.groupby("sym")["_lr"].transform(lambda s: s.rolling(20, min_periods=15).std()) * math.sqrt(252) * 100
    hi = p["high"] if "high" in p else p["close"]
    lo = p["low"] if "low" in p else p["close"]
    p["hi52"] = hi.groupby(p["sym"]).transform(lambda s: s.rolling(252, min_periods=20).max())
    p["lo52"] = lo.groupby(p["sym"]).transform(lambda s: s.rolling(252, min_periods=20).min())
    # beta vs benchmark over 120 days
    if "bench" in p and p["bench"].notna().any():
        b = p.drop_duplicates("date").set_index("date")["bench"].sort_index()
        br = np.log(b / b.shift(1))
        p["_br"] = p["date"].map(br)

        def beta(df):
            cov = df["_lr"].rolling(120, min_periods=60).cov(df["_br"])
            var = df["_br"].rolling(120, min_periods=60).var()
            return cov / var
        p["beta"] = p.groupby("sym", group_keys=False)[["_lr", "_br"]].apply(beta)
        p["rs_1m"] = p["r_1m"] - p["date"].map((b / b.shift(21) - 1) * 100)
    return p.drop(columns=[c for c in p if c.startswith("_")])


def panel_from_stockedge(se: pd.DataFrame) -> pd.DataFrame:
    p = pd.DataFrame({"date": se["date"], "sym": se["sym"], "close": se["se_close"],
                      "chg": se["se_chg"], "fut_oi": se["se_oi"], "oi_chg": se["se_oi_chg"],
                      "call_oi": se["se_call_oi"], "put_oi": se["se_put_oi"],
                      "pcr": se["se_pcr"], "pcr_chg": se["se_pcr_chg"],
                      "vol_mult": se["se_vol_mult"], "deliv_mult": se["se_deliv_mult"],
                      "lot": se["se_lot"]})
    p["oi_trend"] = [classify(a, b) for a, b in zip(p["chg"], p["oi_chg"])]
    g = p.sort_values(["sym", "date"]).groupby("sym")
    for n, lab in ((5, "r_1w"), (21, "r_1m")):
        p[lab] = (p["close"] / g["close"].shift(n) - 1) * 100
    return p


# --------------------------------------------------------------------------- export helpers
def clean(v, nd=2):
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else round(float(v), nd)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), default=str))


LATEST_FIELDS = ["sym", "name", "sector", "industry", "mcap_cat", "lot", "close", "chg", "fut_oi",
                 "oi_chg", "oi_trend", "se_oi_trend", "oi_val_cr", "pcr", "pcr_chg", "vol_mult",
                 "deliv_pct", "deliv_mult", "roll", "basis_pct", "dte", "expiry", "max_pain",
                 "top_ce", "top_pe", "r_1w", "r_1m", "r_3m", "r_6m", "r_1y", "rsi", "rv20",
                 "beta", "rs_1m", "above_sma50", "above_sma200", "dist_hi52", "dist_lo52",
                 "hi52", "lo52", "oi_streak"]
HIST_FIELDS = ["close", "high", "low", "chg", "fut_oi", "oi_chg", "pcr", "deliv_pct",
               "vol_mult", "roll", "basis_pct", "sma20", "sma50", "sma200", "rsi", "oi_trend"]


SECTOR_MAP = ROOT / "data" / "sectors.csv"


def main(demo=False):
    se = read_stockedge()
    if not se.empty:  # keep a small symbol -> sector map so the cloud build works without StockEdge files
        se.sort_values("date").drop_duplicates("sym", keep="last")[
            ["sym", "name", "sector", "industry", "mcap_cat"]].sort_values("sym").to_csv(SECTOR_MAP, index=False)
    nse = load_nse_panel()
    source = "nse" if not nse.empty else ("stockedge" if not se.empty else None)
    if source is None:
        raise SystemExit("No data: put NSE files in data/raw (run fetch_nse.py) or StockEdge CSVs in data/stockedge.")
    p = add_metrics(nse) if source == "nse" else panel_from_stockedge(se)

    # names / sectors: StockEdge rows if present, else the saved sector map
    meta = None
    if not se.empty:
        meta = se.sort_values("date").drop_duplicates("sym", keep="last").set_index("sym")[
            ["name", "sector", "industry", "mcap_cat"]]
    elif SECTOR_MAP.exists():
        meta = pd.read_csv(SECTOR_MAP).set_index("sym")
    if meta is not None:
        p = p.merge(meta, left_on="sym", right_index=True, how="left")
    if not se.empty:
        p = p.merge(se[["date", "sym", "se_oi_trend"]], on=["date", "sym"], how="left")
    for c in ("name", "sector", "industry", "mcap_cat", "se_oi_trend"):
        if c not in p:
            p[c] = None
    p["name"] = p["name"].fillna(p["sym"])
    p["sector"] = p["sector"].fillna("Unclassified")

    last = p["date"].max()
    cur = p[p["date"] == last].copy()
    cur["oi_val_cr"] = cur["fut_oi"] * cur["close"] / 1e7
    for n in (50, 200):
        if f"sma{n}" in cur:
            cur[f"above_sma{n}"] = cur["close"] > cur[f"sma{n}"]
    if "hi52" in cur:
        cur["dist_hi52"] = (cur["close"] / cur["hi52"] - 1) * 100
        cur["dist_lo52"] = (cur["close"] / cur["lo52"] - 1) * 100

    # OI streak: consecutive days with the same base OI trend (ignores Agg. prefix)
    if "oi_trend" in p.columns:
        def _streak(group):
            trends = group.sort_values("date")["oi_trend"].fillna("Neutral")
            base = trends.str.replace("Agg. ", "", regex=False)
            streak = 1
            last = base.iloc[-1] if len(base) else "Neutral"
            for t in reversed(base.tolist()[:-1]):
                if t == last:
                    streak += 1
                else:
                    break
            return streak
        streak_map = {sym: _streak(g) for sym, g in hp.groupby("sym")}
        cur["oi_streak"] = cur["sym"].map(streak_map)

    latest = [{f: clean(r.get(f)) for f in LATEST_FIELDS if f in cur.columns}
              for r in cur.sort_values("sym").to_dict("records")]

    # per-stock history
    hist_dir = SITE_DATA / "history"
    if hist_dir.exists():
        shutil.rmtree(hist_dir)
    dates_all = sorted(p["date"].unique())[-HISTORY_DAYS:]
    hp = p[p["date"].isin(dates_all)]
    for sym, g in hp.groupby("sym"):
        g = g.sort_values("date")
        h = {"dates": [d.strftime("%Y-%m-%d") for d in g["date"]]}
        for f in HIST_FIELDS:
            if f in g:
                h[f] = [clean(v) for v in g[f]]
        dump(hist_dir / f"{re.sub(r'[^A-Za-z0-9_-]', '_', sym)}.json", h)

    # sectors
    sectors = []
    for sec, g in cur.groupby("sector"):
        trends = g["oi_trend"].fillna("n/a").str.replace("Agg. ", "", regex=False).value_counts().to_dict()
        sectors.append({"sector": sec, "n": len(g), "chg": clean(g["chg"].mean()),
                        "oi_chg": clean(g["oi_chg"].mean()),
                        "adv": int((g["chg"] > 0).sum()), "dec": int((g["chg"] < 0).sum()),
                        "r_1w": clean(g["r_1w"].mean()) if "r_1w" in g else None,
                        "r_1m": clean(g["r_1m"].mean()) if "r_1m" in g else None,
                        "above_sma50": clean(g["above_sma50"].mean() * 100) if "above_sma50" in g else None,
                        "pcr": clean(g["pcr"].median()) if "pcr" in g else None,
                        "trends": trends, "syms": sorted(g["sym"].tolist())})
    sectors.sort(key=lambda s: -(s["chg"] or -99))

    # benchmark history
    bench = None
    if "bench" in p and p["bench"].notna().any():
        b = p.drop_duplicates("date").sort_values("date").tail(HISTORY_DAYS)
        bench = {"name": BENCHMARK, "dates": [d.strftime("%Y-%m-%d") for d in b["date"]],
                 "close": [clean(v) for v in b["bench"]]}

    trend_counts = cur["oi_trend"].fillna("n/a").str.replace("Agg. ", "", regex=False).value_counts().to_dict()
    market = {"date": last.strftime("%Y-%m-%d"), "source": source, "demo": demo, "n": len(cur),
              "adv": int((cur["chg"] > 0).sum()), "dec": int((cur["chg"] < 0).sum()),
              "trend_counts": trend_counts,
              "pcr_median": clean(cur["pcr"].median()) if "pcr" in cur else None,
              "expiry": clean(cur["expiry"].dropna().min()) if "expiry" in cur else None,
              "dte": clean(cur["dte"].min()) if "dte" in cur else None,
              "n_days": len(dates_all), "first_date": dates_all[0].strftime("%Y-%m-%d"),
              "bench": bench}

    # F&O ban list
    ban_file = ROOT / "data" / "banlist.json"
    banned_syms = []
    if ban_file.exists():
        try:
            ban_data = json.loads(ban_file.read_text())
            banned_syms = ban_data.get("banned", [])
        except Exception:
            pass
    market["banned"] = banned_syms

    # value chains
    vc_out = SITE_DATA / "valuechain"
    if vc_out.exists():
        shutil.rmtree(vc_out)
    vc_out.mkdir(parents=True)
    vc_index = []
    for f in sorted(VALUECHAIN.glob("*.json")):
        shutil.copy(f, vc_out / f.name)
        vc_index.append(f.stem)
    market["valuechain"] = vc_index

    # business profiles
    prof_src = ROOT / "data" / "profiles"
    prof_out = SITE_DATA / "profiles"
    if prof_out.exists():
        shutil.rmtree(prof_out)
    prof_out.mkdir(parents=True)
    if prof_src.exists():
        for f in sorted(prof_src.glob("*.json")):
            shutil.copy(f, prof_out / f.name)

    # news (written by fetch_news.py directly into site/data/news – nothing to copy)

    dump(SITE_DATA / "latest.json", latest)
    dump(SITE_DATA / "sectors.json", sectors)
    dump(SITE_DATA / "market.json", market)
    print(f"Built site data for {last:%Y-%m-%d}: {len(latest)} stocks, {len(dates_all)} days, source={source}")


def prune_raw():
    """Delete raw NSE files whose day is already summarised in data/daily (saves space)."""
    n = 0
    for f in DAILY.glob("*.csv.gz"):
        ds = f.name[:10]
        for kind, ext in (("fo", ".csv.zip"), ("cm", ".csv.zip"), ("deliv", ".csv"), ("index", ".csv")):
            r = RAW / kind / f"{ds}{ext}"
            if r.exists():
                r.unlink(); n += 1
    print(f"Pruned {n} raw files")


if __name__ == "__main__":
    import sys
    main(demo="--demo" in sys.argv)
    if "--prune-raw" in sys.argv:
        prune_raw()
