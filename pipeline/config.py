"""Shared paths and settings for the F&O dashboard pipeline."""
import os
from pathlib import Path

ROOT = Path(os.environ.get("FNO_ROOT") or Path(__file__).resolve().parent.parent)
RAW = ROOT / "data" / "raw"
STOCKEDGE = ROOT / "data" / "stockedge"      # drop StockEdge Derivative Analytics CSVs here
VALUECHAIN = ROOT / "data" / "valuechain"    # hand-curated inputs/outputs trees (one JSON per symbol)
SITE_DATA = ROOT / "site" / "data"

# How many trading days of history to keep in each stock's JSON file
HISTORY_DAYS = 500

# Benchmark index for beta / relative strength (name as it appears in NSE's ind_close_all file)
BENCHMARK = "Nifty 50"

# OI-trend thresholds
OI_NEUTRAL_PCT = 0.5        # |OI change %| below this = Neutral
AGGRESSIVE_OI_PCT = 5.0     # |OI change %| at or above this = "Aggressive" variant

for p in (RAW, STOCKEDGE, VALUECHAIN, SITE_DATA):
    p.mkdir(parents=True, exist_ok=True)
