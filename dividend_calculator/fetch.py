"""Data fetching utilities for dividend_calculator.

Uses direct calls to Yahoo Finance API for prices and dividends.
Also fetches fundamentals from yfinance to avoid expensive scraping.
"""

import csv
import io
import time
import bisect
import math
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

import requests
import yfinance as yf
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


def _to_float(value: Any) -> Optional[float]:
    """Convert a value to float when possible."""
    if value is None:
        return None
    try:
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _pick_statement_row(df, candidates: List[str]):
    """Return the first matching row from a yfinance statement DataFrame."""
    if df is None or getattr(df, "empty", True):
        return None
    for key in candidates:
        if key in df.index:
            return df.loc[key]
    return None


def _annual_statement(ticker: yf.Ticker, getter_names: List[str]):
    """Fetch annual statement data using the first available yfinance method."""
    last_err = None
    for name in getter_names:
        getter = getattr(ticker, name, None)
        if getter is None:
            continue
        try:
            result = getter(freq="yearly") if callable(getter) else getter
            if result is not None and not getattr(result, "empty", True):
                return result
        except Exception as exc:
            last_err = exc
            continue
    if last_err:
        raise last_err
    return None

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
                ticker_id = db.upsert_ticker(yahoo_symbol, name=name)
                face_value = row.get("FACE VALUE")
                try:
                    db.update_ticker_face_value(ticker_id, float(face_value) if face_value else None)
                except ValueError:
                    db.update_ticker_face_value(ticker_id, None)
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
                    ticker_id = db.upsert_ticker(base_symbol, name=name)
                    seen_symbols.add(base_symbol)
                    added += 1
                
                # Also add the suffixed version (might be useful for some users)
                if symbol not in seen_symbols:
                    ticker_id = db.upsert_ticker(symbol, name=name)
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


def fetch_fundamentals(symbol: str, ticker_id: int) -> Optional[Dict[str, Any]]:
    """Fetch fundamentals from yfinance and store them in the DB."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        income_df = _annual_statement(ticker, ["get_income_stmt", "income_stmt"])
        balance_df = _annual_statement(ticker, ["get_balance_sheet", "balance_sheet"])
        cashflow_df = _annual_statement(ticker, ["get_cashflow", "cashflow"])

        latest_col = None
        if income_df is not None and not getattr(income_df, "empty", True):
            latest_col = income_df.columns[0]

        common_equity_row = _pick_statement_row(balance_df, ["StockholdersEquity", "CommonStockEquity", "TotalEquityGrossMinorityInterest"])
        net_income_row = _pick_statement_row(income_df, ["NetIncome", "NetIncomeCommonStockholders", "NetIncomeIncludingNoncontrollingInterests"])
        eps_row = _pick_statement_row(income_df, ["DilutedEPS", "BasicEPS"])
        ebit_row = _pick_statement_row(income_df, ["EBIT"])
        current_liab_row = _pick_statement_row(balance_df, ["CurrentLiabilities"])
        total_assets_row = _pick_statement_row(balance_df, ["TotalAssets"])
        dividends_paid_row = _pick_statement_row(cashflow_df, ["CashDividendsPaid", "CommonStockDividendPaid"])
        shares_row = _pick_statement_row(balance_df, ["OrdinarySharesNumber", "ShareIssued"])

        latest_net_income = _to_float(net_income_row.get(latest_col)) if net_income_row is not None and latest_col is not None else None
        latest_equity = _to_float(common_equity_row.get(latest_col)) if common_equity_row is not None and latest_col is not None else None
        latest_eps_stmt = _to_float(eps_row.get(latest_col)) if eps_row is not None and latest_col is not None else None
        latest_ebit = _to_float(ebit_row.get(latest_col)) if ebit_row is not None and latest_col is not None else None
        latest_total_assets = _to_float(total_assets_row.get(latest_col)) if total_assets_row is not None and latest_col is not None else None
        latest_current_liab = _to_float(current_liab_row.get(latest_col)) if current_liab_row is not None and latest_col is not None else None
        latest_dividends_paid = _to_float(dividends_paid_row.get(latest_col)) if dividends_paid_row is not None and latest_col is not None else None
        latest_shares_outstanding = _to_float(shares_row.get(latest_col)) if shares_row is not None and latest_col is not None else None

        current_price = _to_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        shares_outstanding = _to_float(info.get("sharesOutstanding")) or latest_shares_outstanding

        latest_data: Dict[str, Any] = {}

        payout_ratio = _to_float(info.get("payoutRatio"))
        if payout_ratio is None and latest_net_income not in (None, 0) and latest_dividends_paid is not None and latest_net_income > 0:
            payout_ratio = (abs(latest_dividends_paid) / latest_net_income) * 100.0
        if payout_ratio is not None:
            latest_data["payout_ratio"] = payout_ratio * 100.0 if payout_ratio <= 1 else payout_ratio

        dividend_yield = _to_float(info.get("dividendYield"))
        if dividend_yield is None:
            dividend_rate = _to_float(info.get("dividendRate"))
            if dividend_rate is not None and current_price not in (None, 0):
                dividend_yield = (dividend_rate / current_price) * 100.0
        if dividend_yield is not None:
            latest_data["dividend_yield"] = dividend_yield * 100.0 if dividend_yield <= 1 else dividend_yield

        pe_ratio = _to_float(info.get("trailingPE"))
        if pe_ratio is None and current_price not in (None, 0) and latest_eps_stmt not in (None, 0):
            pe_ratio = current_price / latest_eps_stmt
        if pe_ratio is not None:
            latest_data["pe_ratio"] = pe_ratio

        roe = _to_float(info.get("returnOnEquity"))
        if roe is None and latest_net_income is not None and latest_equity not in (None, 0):
            roe = (latest_net_income / latest_equity) * 100.0
        if roe is not None:
            latest_data["roe"] = roe * 100.0 if roe <= 1 else roe

        roce = None
        if latest_ebit is not None and latest_total_assets is not None and latest_current_liab is not None:
            capital_employed = latest_total_assets - latest_current_liab
            if capital_employed not in (None, 0) and capital_employed > 0:
                roce = (latest_ebit / capital_employed) * 100.0
        if roce is not None:
            latest_data["roce"] = roce

        book_value = _to_float(info.get("bookValue"))
        if book_value is None and latest_equity is not None and shares_outstanding not in (None, 0):
            book_value = latest_equity / shares_outstanding
        if book_value is not None:
            latest_data["book_value"] = book_value

        eps = _to_float(info.get("trailingEps"))
        if eps is None:
            eps = latest_eps_stmt
        if eps is not None:
            latest_data["eps"] = eps

        market_cap = _to_float(info.get("marketCap"))
        if market_cap is None and current_price is not None and shares_outstanding not in (None, 0):
            market_cap = current_price * shares_outstanding
        if market_cap is not None:
            latest_data["market_cap_cr"] = market_cap / 10000000.0

        face_value = db.get_ticker_face_value(ticker_id)
        if face_value is not None:
            latest_data["face_value"] = face_value

        if latest_data:
            latest_data["last_updated"] = datetime.utcnow().isoformat()
            db.upsert_screener_latest(ticker_id, latest_data)

        if income_df is not None and not getattr(income_df, "empty", True):
            for col in income_df.columns:
                year_val = getattr(col, "year", None)
                fiscal_year = f"Mar {year_val}" if year_val is not None else str(col)

                year_data: Dict[str, Any] = {}

                if eps_row is not None:
                    year_eps = _to_float(eps_row.get(col))
                    if year_eps is not None:
                        year_data["eps"] = year_eps

                if net_income_row is not None:
                    net_income = _to_float(net_income_row.get(col))
                    if net_income is not None:
                        year_data["net_profit"] = net_income

                if net_income_row is not None and common_equity_row is not None:
                    net_income = _to_float(net_income_row.get(col))
                    equity = _to_float(common_equity_row.get(col))
                    if net_income is not None and equity not in (None, 0):
                        year_data["roe"] = (net_income / equity) * 100.0

                if ebit_row is not None and total_assets_row is not None and current_liab_row is not None:
                    ebit = _to_float(ebit_row.get(col))
                    total_assets = _to_float(total_assets_row.get(col))
                    current_liab = _to_float(current_liab_row.get(col))
                    capital_employed = None
                    if total_assets is not None and current_liab is not None:
                        capital_employed = total_assets - current_liab
                    if ebit is not None and capital_employed not in (None, 0):
                        year_data["roce"] = (ebit / capital_employed) * 100.0

                if dividends_paid_row is not None and net_income_row is not None:
                    dividends_paid = _to_float(dividends_paid_row.get(col))
                    net_income = _to_float(net_income_row.get(col))
                    if dividends_paid is not None and net_income not in (None, 0) and net_income > 0:
                        year_data["payout_ratio"] = (abs(dividends_paid) / net_income) * 100.0

                if year_data:
                    db.upsert_screener_yearly(ticker_id, fiscal_year, year_data)

        time.sleep(0.3)
        return latest_data if latest_data else None
    except Exception:
        return None
