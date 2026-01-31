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
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import db

NSE_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=max&interval=1mo&events=div%7Csplit"
YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_session():
    """Create a robust requests session with retries."""
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session

def download_nse_tickers(force: bool = False) -> int:
    """Download the NSE ticker CSV and insert any new symbols."""
    session = get_session()
    response = session.get(NSE_CSV_URL, timeout=30)
    response.raise_for_status()
    text = response.content.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    added = 0
    for row in reader:
        row = {k.strip(): v.strip() for k, v in row.items() if k is not None and v is not None}
        symbol = row.get("SYMBOL")
        if not symbol:
            continue
        series = row.get("SERIES")
        if series != "EQ":
            continue
        yahoo_symbol = f"{symbol}.NS"
        name = row.get("NAME OF COMPANY")
        db.upsert_ticker(yahoo_symbol, name=name)
        added += 1
    return added

NIFTY_500_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"

_industry_mapping = {}

def load_industry_mapping():
    """Load industry mapping from Nifty 500 CSV."""
    global _industry_mapping
    if _industry_mapping:
        return
    try:
        session = get_session()
        r = session.get(NIFTY_500_URL, timeout=15)
        if r.status_code == 200:
            f = io.StringIO(r.text)
            reader = csv.DictReader(f)
            for row in reader:
                symbol = row.get("Symbol")
                industry = row.get("Industry")
                if symbol and industry:
                    _industry_mapping[symbol] = industry
    except Exception:
        pass

def fetch_ticker_metrics(session, symbol: str) -> Dict[str, Any]:
    """Fetch basic info and metrics from Yahoo Finance."""
    # 1. Use Search API for Sector and Industry (Very reliable & free)
    search_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={symbol}&quotesCount=1&newsCount=0"
    metrics = {}
    try:
        r = session.get(search_url, timeout=10)
        if r.status_code == 200:
            quotes = r.json().get("quotes", [])
            if quotes:
                metrics["sector"] = quotes[0].get("sector")
                metrics["industry"] = quotes[0].get("industry")
                metrics["name"] = quotes[0].get("longname")
    except Exception:
        pass
        
    # 2. Enrich Industry from Nifty 500 mapping if missing
    pure_symbol = symbol.replace(".NS", "")
    load_industry_mapping()
    if not metrics.get("industry") and pure_symbol in _industry_mapping:
        metrics["industry"] = _industry_mapping[pure_symbol]
        
    return metrics

def fetch_dividends(symbol: str, fetch_price: bool = True, session=None) -> Tuple[int, int]:
    """Fetch dividend history and metrics for ``symbol``."""
    if session is None:
        session = get_session()
        
    # 1. Fetch Chart Data (Dividends & Splits)
    chart_url = YAHOO_CHART_URL.format(symbol=symbol)
    try:
        response = session.get(chart_url, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return (0, 0)
        
    result = data.get("chart", {}).get("result", [])
    if not result:
        return (0, 0)
    
    meta = result[0].get("meta", {})
    ticker_id = db.upsert_ticker(symbol)
    
    # 2. Fetch Latest Metrics
    metrics = fetch_ticker_metrics(session, symbol)
    # Add current price from chart meta
    metrics["current_price"] = meta.get("regularMarketPrice")
    if metrics:
        db.update_ticker_metrics(ticker_id, metrics)

    events = result[0].get("events", {})
    dividends_data = events.get("dividends", {})
    splits_data = events.get("splits", {})
    
    # 3. Process Splits
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
    
    valid_data = [(ts, price) for ts, price in zip(timestamps, closes) if price is not None]
    valid_data.sort()
    valid_ts = [item[0] for item in valid_data]

    # 4. Process Dividends
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
            idx = bisect.bisect_left(valid_ts, ts)
            closest_price = None
            if idx == 0:
                closest_price = valid_data[0][1]
            elif idx == len(valid_ts):
                closest_price = valid_data[-1][1]
            else:
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

def parallel_update(tickers: List[Dict], workers: int = 5):
    """Update multiple tickers in parallel."""
    session = get_session()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_symbol = {executor.submit(fetch_dividends, t["symbol"], True, session): t["symbol"] for t in tickers}
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                future.result()
            except Exception as exc:
                print(f"{symbol} generated an exception: {exc}")
