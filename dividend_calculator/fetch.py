"""Data fetching utilities for dividend_calculator.

Uses direct calls to Yahoo Finance API for prices and dividends.
Also fetches fundamentals from yfinance to avoid expensive scraping.
"""

import csv
import io
import time
import bisect
import math
import concurrent.futures
from typing import List, Tuple, Optional, Dict, Any

import requests
import yfinance as yf
from . import db
from .timeutils import utc_from_timestamp, utc_now_iso

NSE_CSV_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_SME_CSV_URL = "https://nsearchives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv"
NSE_INVIT_CSV_URL = "https://nsearchives.nseindia.com/content/equities/INVITS_L.csv"
NSE_REIT_CSV_URL = "https://nsearchives.nseindia.com/content/equities/REITS_L.csv"
# We use a long range but stick to 1mo to get historical dividends efficiently.
# For prices, we might need a separate call or just accept 1mo granularity if that's all we get.
# Actually, the chart API with events=div returns ALL dividends in 'max' range.
YAHOO_API_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=max&interval=1mo&events=div%7Csplit"
YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json",
}


def _clean_csv_rows(text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        cleaned = {
            k.strip(): v.strip()
            for k, v in row.items()
            if k is not None and v is not None
        }
        symbol = cleaned.get("SYMBOL", "")
        isin = cleaned.get("ISIN NUMBER") or cleaned.get("ISIN_NUMBER")
        if not symbol or symbol.lower().startswith("note"):
            continue
        if isin is not None and not isin.strip():
            continue
        rows.append(cleaned)
    return rows


def _download_security_rows(url: str) -> List[Dict[str, str]]:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    text = response.content.decode("utf-8", errors="ignore")
    return _clean_csv_rows(text)


def _yahoo_symbol_supported(symbol: str) -> bool:
    url = YAHOO_API_URL.format(symbol=symbol)
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params={"range": "1d", "interval": "1d"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return False
        meta = result[0].get("meta", {})
        return meta.get("exchangeName") == "NSI"
    except Exception:
        return False


def _upsert_ticker_row(row: Dict[str, str], seen_symbols: set[str]) -> bool:
    symbol = row.get("SYMBOL", "")
    if not symbol:
        return False

    yahoo_symbol = f"{symbol}.NS"
    if yahoo_symbol in seen_symbols:
        return False

    ticker_id = db.upsert_ticker(
        yahoo_symbol,
        name=row.get("NAME OF COMPANY") or row.get("NAME_OF_COMPANY"),
    )
    face_value = row.get("FACE VALUE") or row.get("FACE_VALUE")
    try:
        db.update_ticker_face_value(ticker_id, float(face_value) if face_value else None)
    except ValueError:
        db.update_ticker_face_value(ticker_id, None)

    seen_symbols.add(yahoo_symbol)
    return True


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
    """Download NSE tickers from exchange files and validate broader coverage with Yahoo."""
    added = 0
    seen_symbols = {row["symbol"] for row in db.get_all_tickers()}

    try:
        main_rows = _download_security_rows(NSE_CSV_URL)
    except Exception:
        main_rows = []

    main_symbols = {row.get("SYMBOL", "") for row in main_rows if row.get("SYMBOL")}

    for row in main_rows:
        if _upsert_ticker_row(row, seen_symbols):
            added += 1

    for url in (NSE_INVIT_CSV_URL, NSE_REIT_CSV_URL):
        try:
            rows = _download_security_rows(url)
        except Exception:
            rows = []
        for row in rows:
            if _upsert_ticker_row(row, seen_symbols):
                added += 1

    try:
        sme_rows = _download_security_rows(NSE_SME_CSV_URL)
    except Exception:
        sme_rows = []

    sme_candidates = []
    for row in sme_rows:
        symbol = row.get("SYMBOL", "")
        if not symbol or symbol in main_symbols or symbol.endswith("-RE"):
            continue
        sme_candidates.append(row)

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        validations = executor.map(
            lambda row: _yahoo_symbol_supported(f"{row['SYMBOL']}.NS"),
            sme_candidates,
        )
        for row, is_supported in zip(sme_candidates, validations):
            if is_supported and _upsert_ticker_row(row, seen_symbols):
                added += 1

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
            dt = utc_from_timestamp(ts)
            db.insert_split(ticker_id, dt.date().isoformat(), float(numerator), float(denominator))

    if not dividends_data:
        db.update_ticker_timestamp(ticker_id, utc_now_iso())
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
            
        dt = utc_from_timestamp(ts)
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
            
    db.update_ticker_timestamp(ticker_id, utc_now_iso())
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
            latest_data["last_updated"] = utc_now_iso()
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
