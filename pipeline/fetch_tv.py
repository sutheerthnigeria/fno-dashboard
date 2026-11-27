"""Fetch TradingView technical data for all 218 F&O stocks and save to data/tv_technicals.json.

This script CANNOT be run unattended in GitHub Actions because the TradingView MCP server
requires interactive authentication. Run it locally (or via Claude with the TradingView MCP
connected) whenever you want to refresh the TV signals, then commit the resulting JSON.

Usage (via Claude / MCP):
  1. Connect the TradingView MCP server in Claude.
  2. Ask Claude to run this procedure, batch-fetching NSE symbols.
  3. Claude will call mcp-tv-get-symbol-data-batch with 50 symbols at a time.
  4. The resulting data/tv_technicals.json is committed and pushed.

Columns fetched per symbol:
  close, RSI, RSI|1W, ADX, MACD.macd, EMA20, EMA50, EMA200,
  Recommend.All, Recommend.MA, Recommend.Other,
  TechRating_1D, MARating_1D, OsRating_1D

Symbol format: NSE:<SYMBOL>  (e.g. NSE:RELIANCE)
Output key:    plain symbol   (e.g. RELIANCE)

TechRating_1D values: StrongBuy | Buy | Neutral | Sell | StrongSell
Recommend.All range:  -1.0 (StrongSell) to +1.0 (StrongBuy)

Merge into site/data/latest.json is done by pipeline/build.py:
  tv_rating  <- TechRating_1D
  tv_ma      <- MARating_1D
  tv_os      <- OsRating_1D
  tv_rec     <- Recommend.All  (numeric -1..+1)
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
LATEST = ROOT / "site" / "data" / "latest.json"
OUT = ROOT / "data" / "tv_technicals.json"

TV_COLUMNS = [
    "close", "RSI", "RSI|1W", "ADX", "MACD.macd",
    "EMA20", "EMA50", "EMA200",
    "Recommend.All", "Recommend.MA", "Recommend.Other",
    "TechRating_1D", "MARating_1D", "OsRating_1D",
]

BATCH_SIZE = 50


def get_symbols() -> list[str]:
    """Return all F&O symbols in NSE:<SYM> format."""
    latest = json.loads(LATEST.read_text())
    return [f"NSE:{r['sym']}" for r in latest]


def batches(syms: list[str]) -> list[list[str]]:
    return [syms[i:i + BATCH_SIZE] for i in range(0, len(syms), BATCH_SIZE)]


if __name__ == "__main__":
    # This is a documentation script; actual fetching is done interactively via Claude MCP.
    syms = get_symbols()
    print(f"Total symbols: {len(syms)}")
    for i, batch in enumerate(batches(syms), 1):
        print(f"Batch {i} ({len(batch)} symbols): {batch[0]} … {batch[-1]}")
    print(f"\nCall mcp-tv-get-symbol-data-batch for each batch with columns={TV_COLUMNS}")
    print(f"Output: {OUT}")
