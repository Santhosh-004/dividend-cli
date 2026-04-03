"""Data fetching utilities for dividend_calculator.

Uses direct calls to Yahoo Finance API instead of yfinance to avoid
connectivity issues in restricted environments.
"""

import csv
import io
import time
import bisect
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any

import requests
from . import db

NSE_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
# We use a long range but stick to 1mo to get historical dividends efficiently.
# For prices, we might need a separate call or just accept 1mo granularity if that's all we get.
# Actually, the chart API with events=div returns ALL dividends in 'max' range.
YAHOO_API_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=max&interval=1mo&events=div%7Csplit"
YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json",
}

def download_nse_tickers(force: bool = False) -> int:
    """Download all NSE ticker symbols including stocks, INVITs, and REITs.
    
    Sources:
    1. NSE CSV for EQ/BE/BZ series stocks
    2. Yahoo Finance search for INVITs and REITs (not in NSE CSV)
    """
    added = 0
    seen_symbols = set()
    
    # 1. Download EQ/BE/BZ series from NSE CSV
    try:
        response = requests.get(NSE_CSV_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        text = response.content.decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        
        for row in reader:
            row = {k.strip(): v.strip() for k, v in row.items() if k is not None and v is not None}
            symbol = row.get("SYMBOL")
            if not symbol:
                continue
            series = row.get("SERIES")
            # Include all equity-like series (EQ, BE, BZ)
            if series not in ("EQ", "BE", "BZ"):
                continue
            yahoo_symbol = f"{symbol}.NS"
            if yahoo_symbol not in seen_symbols:
                name = row.get("NAME OF COMPANY")
                db.upsert_ticker(yahoo_symbol, name=name)
                seen_symbols.add(yahoo_symbol)
                added += 1
    except Exception as e:
        pass
    
    # 2. Search Yahoo Finance for INVITs and REITs (not in NSE CSV)
    # Search for INVITs and REITs, then try to find dividend-paying versions
    search_terms = ["INVIT", "REIT", "Infrastructure Investment Trust", "Real Estate Investment Trust"]
    
    for term in search_terms:
        try:
            params = {
                "q": term,
                "quotesCount": 100,
                "newsCount": 0,
            }
            response = requests.get(YAHOO_SEARCH_URL, headers=HEADERS, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            for quote in data.get("quotes", []):
                if quote.get("exchange") != "NSI":  # NSE only
                    continue
                
                symbol = quote.get("symbol", "")
                if not symbol.endswith(".NS"):
                    continue
                
                # Check if it's an INVIT or REIT
                symbol_upper = symbol.upper()
                name = quote.get("shortname", quote.get("longname", ""))
                name_upper = name.upper() if name else ""
                
                is_invit_reit = (
                    "-IV.NS" in symbol or "-RR.NS" in symbol or "-BL.NS" in symbol or
                    any(x in symbol_upper or x in name_upper for x in [
                        "INVIT", "REIT", "INFRASTRUCTURE TRUST", "REAL ESTATE TRUST"
                    ])
                )
                
                if not is_invit_reit:
                    continue
                
                # Try to find the dividend-paying version
                # Yahoo has two versions: with suffix (-IV, -RR) and without
                # Only the version WITHOUT suffix typically has dividend data
                base_symbol = symbol
                for suffix in ["-IV.NS", "-RR.NS", "-BL.NS"]:
                    if suffix in symbol:
                        base_symbol = symbol.replace(suffix, ".NS")
                        break
                
                # Add the base symbol (without suffix) if not already added
                if base_symbol not in seen_symbols:
                    db.upsert_ticker(base_symbol, name=name)
                    seen_symbols.add(base_symbol)
                    added += 1
                
                # Also add the suffixed version (might be useful for some users)
                if symbol not in seen_symbols:
                    db.upsert_ticker(symbol, name=name)
                    seen_symbols.add(symbol)
            
            time.sleep(0.3)  # Be nice to Yahoo
            
        except Exception as e:
            pass
    
    return added

def fetch_dividends(symbol: str, fetch_price: bool = True) -> Tuple[int, int]:
    """Fetch dividend history for ``symbol`` using Yahoo's chart API."""
    url = YAHOO_API_URL.format(symbol=symbol)
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    
    data = response.json()
    result = data.get("chart", {}).get("result", [])
    if not result:
        return (0, 0)
    
    events = result[0].get("events", {})
    dividends_data = events.get("dividends", {})
    
    meta = result[0].get("meta", {})
    current_price = meta.get("regularMarketPrice")
    events = result[0].get("events", {})
    dividends_data = events.get("dividends", {})
    splits_data = events.get("splits", {})
    
    ticker_id = db.upsert_ticker(symbol)
    if current_price is not None:
        db.update_ticker_price(ticker_id, float(current_price))
    
    # Process splits first
    for _, split in splits_data.items():
        ts = split.get("date")
        numerator = split.get("numerator")
        denominator = split.get("denominator")
        if ts and numerator and denominator:
            dt = datetime.utcfromtimestamp(ts)
            db.insert_split(ticker_id, dt.date().isoformat(), float(numerator), float(denominator))

    if not dividends_data:
        db.update_ticker_timestamp(ticker_id, datetime.utcnow().isoformat())
        return (0, 0)
    
    new_div = 0
    new_price = 0
    
    # Get available prices and their timestamps
    timestamps = result[0].get("timestamp", [])
    quotes = result[0].get("indicators", {}).get("quote", [{}])[0]
    closes = quotes.get("close", [])
    
    # Filter out None values and keep sorted for bisect
    valid_data = [(ts, price) for ts, price in zip(timestamps, closes) if price is not None]
    valid_data.sort()
    
    valid_ts = [item[0] for item in valid_data]

    for _, div in dividends_data.items():
        amount = div.get("amount")
        ts = div.get("date")
        if amount is None or ts is None:
            continue
            
        dt = datetime.utcfromtimestamp(ts)
        date_str = dt.date().isoformat()
        
        db.insert_dividend(ticker_id, date_str, float(amount))
        new_div += 1
        
        if fetch_price and valid_ts:
            # Find the closest price timestamp
            idx = bisect.bisect_left(valid_ts, ts)
            
            # Check neighbors
            closest_price = None
            if idx == 0:
                closest_price = valid_data[0][1]
            elif idx == len(valid_ts):
                closest_price = valid_data[-1][1]
            else:
                # Pick the one with smallest time diff
                before = valid_data[idx-1]
                after = valid_data[idx]
                if abs(ts - before[0]) <= abs(ts - after[0]):
                    closest_price = before[1]
                else:
                    closest_price = after[1]
            
            if closest_price is not None:
                db.insert_price(ticker_id, date_str, float(closest_price))
                new_price += 1
            
    db.update_ticker_timestamp(ticker_id, datetime.utcnow().isoformat())
    return (new_div, new_price)
