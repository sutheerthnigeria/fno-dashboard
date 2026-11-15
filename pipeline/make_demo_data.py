"""Generate FAKE NSE-format files so the pipeline and website can be tested without NSE access.

Prices are random walks anchored to the StockEdge snapshot closes. NOT real market data.
Usage:  FNO_ROOT=/tmp/demo python pipeline/make_demo_data.py --days 300
"""
import argparse
import io
import zipfile

import numpy as np
import pandas as pd

from config import RAW
from build import read_stockedge


def last_tuesday(y, m):
    d = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)
    while d.weekday() != 1:
        d -= pd.Timedelta(days=1)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=300)
    a = ap.parse_args()
    se = read_stockedge()
    base = se.sort_values("date").drop_duplicates("sym", keep="last")
    base = base[base["se_close"] > 0]
    end = se["date"].max()
    days = pd.bdate_range(end=end, periods=a.days)
    rng = np.random.default_rng(7)
    n = len(base)
    vol = rng.uniform(0.012, 0.03, n)
    rets = rng.normal(0.0003, 1, (len(days), n)) * vol
    mkt = rng.normal(0.0003, 0.009, len(days))
    rets += mkt[:, None] * rng.uniform(0.6, 1.4, n)
    lvl = np.exp(np.cumsum(rets[::-1], axis=0))[::-1]
    closes = base["se_close"].values * lvl / lvl[-1]
    oi_base = base["se_oi"].fillna(1e6).clip(lower=1e5).values
    lots = base["se_lot"].fillna(500).values
    bench = 25000 * np.exp(np.cumsum(mkt[::-1]))[::-1]
    bench = bench / bench[-1] * 25144

    for k in ("fo", "cm", "deliv", "index"):
        (RAW / k).mkdir(parents=True, exist_ok=True)
    oi = oi_base.copy()
    for t, d in enumerate(days):
        exps = []
        y, m = d.year, d.month
        for i in range(4):
            e = last_tuesday(y + (m - 1 + i) // 12, (m - 1 + i) % 12 + 1)
            if e >= d:
                exps.append(e)
        exps = exps[:3]
        oi = oi * np.exp(rng.normal(0, 0.03, n))
        c = closes[t]
        prev = closes[t - 1] if t else c
        fo, cm, dl = [], [], []
        for j, sym in enumerate(base["sym"]):
            dte = (exps[0] - d).days
            w = [0.8, 0.17, 0.03] if dte > 4 else [0.35, 0.6, 0.05]
            for e, wt in zip(exps, w):
                fo.append(dict(TradDt=f"{d:%Y-%m-%d}", FinInstrmTp="STF", TckrSymb=sym,
                               XpryDt=f"{e:%Y-%m-%d}", StrkPric="", OptnTp="",
                               ClsPric=round(c[j] * (1 + 0.0004 * (e - d).days / 30), 2),
                               SttlmPric=round(c[j], 2), UndrlygPric=round(c[j], 2),
                               OpnIntrst=int(oi[j] * wt), ChngInOpnIntrst=0,
                               TtlTradgVol=int(rng.integers(1000, 50000)), TtlTrfVal=0,
                               NewBrdLotQty=int(lots[j])))
            step = 10 ** max(0, int(np.log10(c[j])) - 1) * (2.5 if c[j] > 1000 else 5)
            atm = round(c[j] / step) * step
            for s in range(-8, 9):
                k = atm + s * step
                if k <= 0:
                    continue
                for opt in ("CE", "PE"):
                    otm = (k - c[j]) if opt == "CE" else (c[j] - k)
                    oi_o = max(0, oi[j] * 0.04 * np.exp(-abs(s) / 4) * (1.3 if otm > 0 else 0.7) * rng.uniform(0.5, 1.5))
                    fo.append(dict(TradDt=f"{d:%Y-%m-%d}", FinInstrmTp="STO", TckrSymb=sym,
                                   XpryDt=f"{exps[0]:%Y-%m-%d}", StrkPric=k, OptnTp=opt,
                                   ClsPric=round(max(0.05, -otm) + c[j] * 0.02, 2), SttlmPric=0,
                                   UndrlygPric=round(c[j], 2), OpnIntrst=int(oi_o),
                                   ChngInOpnIntrst=0, TtlTradgVol=int(rng.integers(100, 5000)),
                                   TtlTrfVal=0, NewBrdLotQty=int(lots[j])))
            hi, lo = max(c[j], prev[j]) * (1 + rng.uniform(0, .01)), min(c[j], prev[j]) * (1 - rng.uniform(0, .01))
            v = int(rng.lognormal(13, 0.5))
            cm.append(dict(TckrSymb=sym, SctySrs="EQ", OpnPric=round(prev[j], 2), HghPric=round(hi, 2),
                           LwPric=round(lo, 2), ClsPric=round(c[j], 2), PrvsClsgPric=round(prev[j], 2),
                           TtlTradgVol=v, TtlTrfVal=v * c[j]))
            dq = int(v * rng.uniform(0.25, 0.7))
            dl.append({"SYMBOL": sym, " SERIES": " EQ", " DATE1": f" {d:%d-%b-%Y}",
                       " PREV_CLOSE": prev[j], " OPEN_PRICE": prev[j], " HIGH_PRICE": hi,
                       " LOW_PRICE": lo, " LAST_PRICE": c[j], " CLOSE_PRICE": c[j],
                       " AVG_PRICE": c[j], " TTL_TRD_QNTY": v, " TURNOVER_LACS": 0,
                       " NO_OF_TRADES": 0, " DELIV_QTY": dq, " DELIV_PER": round(dq / v * 100, 2)})

        def zipcsv(df, name, path):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr(name, df.to_csv(index=False))
            path.write_bytes(buf.getvalue())
        zipcsv(pd.DataFrame(fo), "fo.csv", RAW / "fo" / f"{d:%Y-%m-%d}.csv.zip")
        zipcsv(pd.DataFrame(cm), "cm.csv", RAW / "cm" / f"{d:%Y-%m-%d}.csv.zip")
        pd.DataFrame(dl).to_csv(RAW / "deliv" / f"{d:%Y-%m-%d}.csv", index=False)
        pd.DataFrame({"Index Name": ["Nifty 50"], "Index Date": [f"{d:%d-%m-%Y}"],
                      "Closing Index Value": [round(bench[t], 2)]}).to_csv(
            RAW / "index" / f"{d:%Y-%m-%d}.csv", index=False)
    print(f"Demo files written for {len(days)} days, {n} symbols")


if __name__ == "__main__":
    main()
