# F&O Research Dashboard

A free website covering every NSE stock-futures stock: market pulse, OI buildup map, screener, sector view, and a page per stock (derivatives, price statistics, charts, goods-and-services tree).

## How it works

```
NSE end-of-day files ──► pipeline/fetch_nse.py ──► data/raw/        (not kept)
                                   │
StockEdge CSVs (optional) ─────────┤
                                   ▼
                         pipeline/build.py ──► data/daily/*.csv.gz  (one small summary per day, kept)
                                   │
                                   ▼
                         site/data/*.json  ──► site/ (index.html, app.js) ──► GitHub Pages
```

A GitHub Actions job (`.github/workflows/daily.yml`) runs at 19:10 and 22:10 IST on weekdays, downloads that day's NSE files, rebuilds the JSON and redeploys the site. Nothing has to run on your laptop.

### NSE files used (all public)
| Folder | File | Gives |
|---|---|---|
| fo | `BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip` | Futures and options OI, prices, expiries, lot sizes |
| cm | `BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip` | Cash-market OHLC, volume |
| deliv | `sec_bhavdata_full_DDMMYYYY.csv` | Delivery quantity and % |
| index | `ind_close_all_DDMMYYYY.csv` | Nifty 50 close (for beta and relative strength) |

### Metrics computed per stock per day
Futures OI (all expiries), OI change, OI trend (Long Buildup / Short Buildup / Short Covering / Long Unwinding / Neutral, "Agg." when |OI change| ≥ 5%), rollover %, basis %, days to expiry, call OI, put OI, PCR, max pain and highest call/put OI strikes (near expiry), volume and delivery vs 20-day average, returns (1W–1Y), 50/200-DMA, RSI(14), 20-day annualised volatility, 120-day beta vs Nifty, 1-month return vs Nifty, distance from 52-week high/low.

## One-time setup (free)

1. Create a free account at github.com.
2. Create a new **public** repository (e.g. `fno-dashboard`). GitHub Pages is free only for public repositories; the data in it is public NSE data.
3. Upload the contents of this folder to it (GitHub web: *Add file → Upload files*, drag everything in; or use GitHub Desktop).
   Then add the daily job: *Add file → Create new file*, name it `.github/workflows/daily.yml`, and paste in the contents of `daily-workflow.yml`.
4. In the repo: **Settings → Pages → Source: GitHub Actions**.
5. **Settings → Actions → General → Workflow permissions: Read and write**.
6. **Actions tab → Daily data update → Run workflow**, set days to `400` the first time to backfill ~16 months. Later runs are automatic.
7. The site appears at `https://<your-username>.github.io/fno-dashboard/`.

If NSE blocks GitHub's servers (the job will say "no F&O files present"), use the laptop route below and push the result.

## Run on your laptop instead

```
pip install -r requirements.txt
run_local.bat 400      # first time: backfill; later just run_local.bat
```
Opens the site at http://localhost:8765.

## StockEdge files
Put Derivative Analytics CSVs in `data/stockedge/`. They add sector, industry, market-cap category and StockEdge's own OI-trend label. They are git-ignored so your paid data is never published; only a small `data/sectors.csv` (symbol → sector) is kept so the cloud build has sector names.

## Goods-and-services trees
One JSON file per stock in `data/valuechain/` (see `MARUTI.json`). Each item can have `weight`, `driver` (price to track), `fno` (linked F&O symbols) and `other` (non-F&O companies), and `children` for the next level.

## Testing without NSE
```
FNO_ROOT=/tmp/demo python pipeline/make_demo_data.py --days 300   # simulated files
FNO_ROOT=/tmp/demo python pipeline/build.py --demo                 # site shows a DEMO banner
```
