"""FastAPI route handlers for the Dividend CLI API.

All business logic mirrors the CLI commands but returns structured JSON
instead of formatted terminal output.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, AsyncGenerator, Any
from threading import Thread

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from .. import db, fetch, utils

# ---------------------------------------------------------------------------
# Simple TTL cache
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[float, Any]] = {}  # key -> (expiry_ts, value)

def _cache_get(key: str) -> Any:
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[0]:
        return entry[1]
    _cache.pop(key, None)
    return None

def _cache_set(key: str, value: Any, ttl: int = 300) -> None:
    _cache[key] = (time.monotonic() + ttl, value)

def _cache_clear() -> None:
    _cache.clear()
from .models import (
    DBSummary,
    DividendQualityInfo,
    FilterResult,
    FundamentalsLatest,
    FundamentalsYearly,
    ScreenerResponse,
    SplitRecord,
    DividendRecord,
    StatsResponse,
    TickerSummary,
    TopStock,
    UpdateRequest,
    YearlyDividend,
    CAGRStats,
    YieldCAGR,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Shared CAGR helpers (same logic as cli.py)
# ---------------------------------------------------------------------------

def _get_cagr_for_years(yearly_totals: pd.Series, years: int) -> Optional[float]:
    if len(yearly_totals) < 2:
        return None
    last_year = yearly_totals.index[-1]
    first_dividend_year = yearly_totals.index[0]
    start_year = last_year - years
    if first_dividend_year > start_year:
        return None
    full_range = pd.Series(0.0, index=range(start_year, last_year + 1))
    full_range.update(yearly_totals.astype(float))
    non_zero_vals = full_range[full_range > 0]
    if len(non_zero_vals) < 2:
        return None
    first_val = non_zero_vals.iloc[0]
    first_non_zero_year = non_zero_vals.index[0]
    last_val = full_range.iloc[-1]
    actual_years = last_year - first_non_zero_year
    if actual_years <= 0 or first_val <= 0:
        return None
    return utils.cagr(first_val, last_val, actual_years)


def _get_yield_cagr_for_years(group: pd.DataFrame, years: int) -> Optional[float]:
    if len(group) < 2:
        return None
    current_year = datetime.now().year
    last_year = current_year - 1
    start_year = last_year - years
    yearly_yields = {}
    for yr in range(start_year, current_year + 1):
        yr_divs = group[group["year"] == yr].sort_values("ex_date")
        if len(yr_divs) > 0:
            raw_col = "raw_amount" if "raw_amount" in yr_divs.columns else "amount"
            total_div = yr_divs[raw_col].sum()
            last_div_row = yr_divs.iloc[-1]
            cp = last_div_row.get("close_price") if hasattr(last_div_row, "get") else last_div_row["close_price"]
            if pd.notna(cp) and pd.notna(total_div) and float(cp) > 0:
                yearly_yields[yr] = utils.dividend_yield(float(total_div), float(cp))
    if len(yearly_yields) < 2:
        return None
    sorted_years = sorted(yearly_yields.keys())
    if sorted_years[-1] - sorted_years[0] < years:
        return None
    first_val = yearly_yields[sorted_years[0]]
    last_val = yearly_yields[sorted_years[-1]]
    actual_years = sorted_years[-1] - sorted_years[0]
    if actual_years <= 0 or first_val <= 0:
        return None
    return utils.cagr(first_val, last_val, actual_years)


def _build_adjusted_df(symbol: str):
    """Return (ticker_row, adjusted_df) or raise HTTPException."""
    tickers = db.get_all_tickers()
    ticker = next((t for t in tickers if t["symbol"] == symbol), None)
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found in DB.")
    ticker_id = ticker["id"]
    rows = db.query_dividends("WHERE t.symbol = ?", (symbol,))
    if not rows:
        raise HTTPException(
            status_code=404, detail=f"No dividend data for {symbol}. Run 'update' first."
        )
    splits = db.get_splits(ticker_id)
    df_raw = [dict(r) for r in rows]
    df_adjusted = utils.adjust_dividends(df_raw, [dict(s) for s in splits])
    df = pd.DataFrame(df_adjusted)
    df["ex_date"] = pd.to_datetime(df["ex_date"])
    df["year"] = df["ex_date"].dt.year
    return ticker, df


# ---------------------------------------------------------------------------
# GET /api/summary
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=DBSummary)
def get_summary():
    """Return high-level database statistics."""
    cached = _cache_get("summary")
    if cached is not None:
        return cached

    conn = db.get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]
        with_divs = conn.execute(
            "SELECT COUNT(DISTINCT ticker_id) FROM dividends"
        ).fetchone()[0]
        with_fund = conn.execute(
            "SELECT COUNT(*) FROM screener_latest"
        ).fetchone()[0]
        row = conn.execute(
            "SELECT MAX(last_updated) FROM tickers"
        ).fetchone()
        last_updated = row[0] if row else None
    finally:
        conn.close()

    result = DBSummary(
        total_tickers=total,
        tickers_with_dividends=with_divs,
        tickers_with_fundamentals=with_fund,
        last_updated=last_updated,
        db_path=str(db.DB_PATH),
    )
    _cache_set("summary", result, ttl=60)
    return result


# ---------------------------------------------------------------------------
# GET /api/tickers
# ---------------------------------------------------------------------------

@router.get("/tickers", response_model=List[TickerSummary])
def get_tickers(
    search: Optional[str] = Query(None, description="Filter by symbol or name"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    """Return all tickers, optionally filtered by a search term."""
    # Cache the full unfiltered list; apply search/pagination in Python
    all_rows = _cache_get("tickers:all")
    if all_rows is None:
        all_rows = db.get_all_tickers()
        _cache_set("tickers:all", all_rows, ttl=300)

    results = []
    for r in all_rows:
        r_dict = dict(r)
        if search:
            q = search.lower()
            if q not in (r_dict.get("symbol") or "").lower() and q not in (
                r_dict.get("name") or ""
            ).lower():
                continue
        results.append(
            TickerSummary(
                id=r_dict["id"],
                symbol=r_dict["symbol"],
                name=r_dict.get("name"),
                sector=r_dict.get("sector"),
                current_price=r_dict.get("current_price"),
                face_value=r_dict.get("face_value"),
                last_updated=r_dict.get("last_updated"),
            )
        )
    return results[offset : offset + limit]


# ---------------------------------------------------------------------------
# GET /api/filter
# ---------------------------------------------------------------------------

@router.get("/filter", response_model=List[FilterResult])
def filter_stocks(
    symbol: Optional[str] = None,
    min_yield: Optional[float] = None,
    max_yield: Optional[float] = None,
    div_growth_min: Optional[float] = None,
    div_3yr_min: Optional[float] = None,
    div_5yr_min: Optional[float] = None,
    div_10yr_min: Optional[float] = None,
    years_up: Optional[int] = None,
    years_stalled: Optional[int] = None,
    years_reduced: Optional[int] = None,
    years_stopped: Optional[int] = None,
    min_payout: Optional[float] = None,
    max_payout: Optional[float] = None,
    min_roe: Optional[float] = None,
    min_roce: Optional[float] = None,
    min_div_quality: Optional[float] = None,
    condition: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
):
    """Filter stocks by dividend criteria. Mirrors the `filter` CLI command."""
    sql_filters = []
    params = []
    if symbol:
        sql_filters.append("t.symbol = ?")
        params.append(symbol)
    where_clause = ("WHERE " + " AND ".join(sql_filters)) if sql_filters else ""

    rows = db.query_dividends(where_clause, tuple(params))
    if not rows:
        return []

    split_rows = db.get_all_splits()
    splits_by_ticker = {}
    for s in split_rows:
        tid = s["ticker_id"]
        splits_by_ticker.setdefault(tid, []).append(dict(s))

    screener_data = {}
    conn = db.get_connection()
    try:
        cur = conn.execute("SELECT * FROM screener_latest")
        for row in cur.fetchall():
            screener_data[row["ticker_id"]] = dict(row)
    finally:
        conn.close()

    # Load ticker names
    ticker_names = {}
    for t in db.get_all_tickers():
        ticker_names[t["symbol"]] = t["name"]

    df_raw = [dict(r) for r in rows]
    df_adjusted = []
    for tid in {r["ticker_id"] for r in df_raw}:
        ticker_divs = [r for r in df_raw if r["ticker_id"] == tid]
        ticker_splits = splits_by_ticker.get(tid, [])
        df_adjusted.extend(utils.adjust_dividends(ticker_divs, ticker_splits))

    df = pd.DataFrame(df_adjusted)
    df["ex_date"] = pd.to_datetime(df["ex_date"])
    df["year"] = df["ex_date"].dt.year

    current_year = datetime.now().year
    last_year = current_year - 1

    eval_condition = condition
    if eval_condition:
        for field in ["years-up", "years-stalled", "years-reduced", "years-stopped", "cagr-overall"]:
            eval_condition = eval_condition.replace(field, field.replace("-", "_"))

    results = []

    for sym, group in df.groupby("symbol"):
        ticker_id = group["ticker_id"].iloc[0]
        curr_price = group["current_price"].iloc[0] if "current_price" in group.columns else None
        screener = screener_data.get(ticker_id, {})

        all_splits = splits_by_ticker.get(ticker_id, [])
        final_shares = 1.0
        for s in all_splits:
            final_shares *= s["numerator"] / s["denominator"]

        last_year_divs = group[group["year"] == last_year].sort_values("ex_date")
        last_yield_val = 0.0
        if len(last_year_divs) > 0:
            raw_col = "raw_amount" if "raw_amount" in last_year_divs.columns else "amount"
            total_div = last_year_divs[raw_col].sum()
            last_div_row = last_year_divs.iloc[-1]
            cp = last_div_row.get("close_price") if hasattr(last_div_row, "get") else last_div_row["close_price"]
            if pd.notna(cp) and pd.notna(total_div) and float(cp) > 0:
                last_yield_val = utils.dividend_yield(float(total_div), float(cp))

        if min_yield is not None and last_yield_val < min_yield:
            continue
        if max_yield is not None and last_yield_val > max_yield:
            continue

        payout = screener.get("payout_ratio")
        roe = screener.get("roe")
        roce = screener.get("roce")

        if min_payout is not None and (payout is None or payout < min_payout):
            continue
        if max_payout is not None and (payout is None or payout > max_payout):
            continue
        if min_roe is not None and (roe is None or roe < min_roe):
            continue
        if min_roce is not None and (roce is None or roce < min_roce):
            continue

        yearly_totals = (
            group[group["year"] < current_year].groupby("year")["amount"].sum().sort_index()
        )
        if len(yearly_totals) == 0:
            continue

        min_yr = int(yearly_totals.index.min())
        max_yr = int(yearly_totals.index.max())
        full_year_range = pd.Series(0.0, index=range(min_yr, max_yr + 1))
        full_year_range.update(yearly_totals.astype(float))
        up, stalled, reduced, stopped = utils.classify_years(full_year_range.tolist())

        if years_up is not None and up < years_up:
            continue
        if years_stalled is not None and stalled > years_stalled:
            continue
        if years_reduced is not None and reduced > years_reduced:
            continue
        if years_stopped is not None and stopped > years_stopped:
            continue

        cagr_overall = (
            _get_cagr_for_years(
                yearly_totals,
                yearly_totals.index[-1] - yearly_totals.index[0],
            )
            if len(yearly_totals) >= 2
            else 0.0
        )

        div_mean = div_std = div_cv = None
        if len(yearly_totals) >= 2:
            div_mean = float(yearly_totals.mean())
            div_std = float(yearly_totals.std())
            div_cv = (div_std / div_mean * 100) if div_mean > 0 else None

        quality_info = utils.dividend_quality_score(
            full_year_range.tolist(),
            cagr_overall,
        )

        if min_div_quality is not None:
            score = quality_info["score"] if quality_info else None
            if score is None or score < min_div_quality:
                continue

        if div_growth_min is not None and (cagr_overall or 0) < div_growth_min:
            continue

        c3 = _get_cagr_for_years(yearly_totals, 3)
        c5 = _get_cagr_for_years(yearly_totals, 5)
        c10 = _get_cagr_for_years(yearly_totals, 10)
        c15 = _get_cagr_for_years(yearly_totals, 15)
        c20 = _get_cagr_for_years(yearly_totals, 20)
        c25 = _get_cagr_for_years(yearly_totals, 25)
        c30 = _get_cagr_for_years(yearly_totals, 30)

        if div_3yr_min is not None and (c3 is None or c3 < div_3yr_min):
            continue
        if div_5yr_min is not None and (c5 is None or c5 < div_5yr_min):
            continue
        if div_10yr_min is not None and (c10 is None or c10 < div_10yr_min):
            continue

        if eval_condition:
            eval_vars = {
                "up": up, "years_up": up,
                "stalled": stalled, "years_stalled": stalled,
                "reduced": reduced, "years_reduced": reduced,
                "stopped": stopped, "years_stopped": stopped,
                "yield": last_yield_val, "yld": last_yield_val, "last_yield": last_yield_val,
                "div_growth": cagr_overall or 0, "div_growth_overall": cagr_overall or 0,
                "cagr_overall": cagr_overall or 0,
                "c3": c3 or 0, "div_3yr": c3 or 0,
                "c5": c5 or 0, "div_5yr": c5 or 0,
                "c10": c10 or 0, "div_10yr": c10 or 0,
                "c15": c15 or 0, "div_15yr": c15 or 0,
                "c20": c20 or 0, "div_20yr": c20 or 0,
                "c25": c25 or 0, "div_25yr": c25 or 0,
                "c30": c30 or 0, "div_30yr": c30 or 0,
                "price": curr_price or 0,
                "shares": final_shares,
                "div_mean": div_mean or 0,
                "div_std": div_std or 0,
                "div_cv": div_cv or 0,
                "dq_score": (quality_info or {}).get("score", 0),
                "dividend_quality_score": (quality_info or {}).get("score", 0),
                "dq_rating": (quality_info or {}).get("rating", ""),
                "dividend_quality_rating": (quality_info or {}).get("rating", ""),
                "payout": payout or 0,
                "roe": roe or 0,
                "roce": roce or 0,
            }
            try:
                if not eval(eval_condition, {"__builtins__": {}}, eval_vars):
                    continue
            except Exception:
                continue

        results.append(
            FilterResult(
                symbol=str(sym),
                name=ticker_names.get(str(sym)),
                price=round(float(curr_price), 2) if curr_price is not None else None,
                shares=round(final_shares, 4),
                yield_pct=round(last_yield_val, 4),
                payout_pct=round(payout, 2) if payout is not None else None,
                roe_pct=round(roe, 2) if roe is not None else None,
                roce_pct=round(roce, 2) if roce is not None else None,
                div_mean=round(div_mean, 4) if div_mean is not None else None,
                div_std=round(div_std, 4) if div_std is not None else None,
                div_cv=round(div_cv, 4) if div_cv is not None else None,
                dividend_quality_score=quality_info["score"] if quality_info else None,
                dividend_quality_rating=quality_info["rating"] if quality_info else None,
                years_up=up,
                years_stalled=stalled,
                years_reduced=reduced,
                years_stopped=stopped,
                cagr_overall=round(cagr_overall, 4) if cagr_overall is not None else None,
                cagr_3yr=round(c3, 4) if c3 is not None else None,
                cagr_5yr=round(c5, 4) if c5 is not None else None,
                cagr_10yr=round(c10, 4) if c10 is not None else None,
                cagr_15yr=round(c15, 4) if c15 is not None else None,
                cagr_20yr=round(c20, 4) if c20 is not None else None,
                cagr_25yr=round(c25, 4) if c25 is not None else None,
                cagr_30yr=round(c30, 4) if c30 is not None else None,
            )
        )

        if len(results) >= limit:
            break

    return results


# ---------------------------------------------------------------------------
# GET /api/stats/{symbol}
# ---------------------------------------------------------------------------

@router.get("/stats/{symbol}", response_model=StatsResponse)
def get_stats(symbol: str):
    """Full dividend statistics for a single ticker. Mirrors the `stats` CLI command."""
    cache_key = f"stats:{symbol}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    ticker, df = _build_adjusted_df(symbol)
    ticker_dict = dict(ticker)
    current_year = datetime.now().year
    last_year = current_year - 1

    splits = db.get_splits(ticker_dict["id"])
    split_records = [
        SplitRecord(
            ex_date=s["ex_date"],
            numerator=s["numerator"],
            denominator=s["denominator"],
            ratio=f"{int(s['numerator'])}:{int(s['denominator'])}",
        )
        for s in splits
    ]

    # Yearly totals
    yearly_forward = df.groupby("year")["amount"].sum().sort_index()
    yearly_data_agg = df.groupby("year").agg(
        {"raw_amount": "sum", "splits_at_time": "first", "id": "count"}
    ).sort_index(ascending=True)

    yearly_dividends = [
        YearlyDividend(
            year=int(yr),
            raw_total=round(float(row["raw_amount"]), 4),
            shares=round(float(row["splits_at_time"]), 4),
            consolidated_total=round(float(row["raw_amount"] * row["splits_at_time"]), 4),
            dividend_count=int(row["id"]),
        )
        for yr, row in yearly_data_agg.iterrows()
    ]

    # CAGR stats (exclude current year)
    yearly_complete = yearly_forward[yearly_forward.index < current_year]
    cagr_stats = []
    if len(yearly_complete) > 1:
        overall = _get_cagr_for_years(
            yearly_complete, yearly_complete.index[-1] - yearly_complete.index[0]
        )
        cagr_stats.append(CAGRStats(period="Overall", cagr=round(overall, 4) if overall is not None else None))
        for yrs, label in [(3, "3 Year"), (5, "5 Year"), (10, "10 Year"), (15, "15 Year"), (20, "20 Year"), (30, "30 Year")]:
            v = _get_cagr_for_years(yearly_complete, yrs)
            cagr_stats.append(CAGRStats(period=label, cagr=round(v, 4) if v is not None else None))

    yield_cagr_stats = []

    # Year-over-year classification
    if len(yearly_complete) > 0:
        min_yr = int(yearly_complete.index.min())
        max_yr = int(yearly_complete.index.max())
        full_range = pd.Series(0.0, index=range(min_yr, max_yr + 1))
        full_range.update(yearly_complete.astype(float))
        up, stalled, reduced, stopped = utils.classify_years(full_range.tolist())
    else:
        up = stalled = reduced = stopped = 0

    dividend_quality = None
    if len(yearly_complete) >= 2:
        quality_info = utils.dividend_quality_score(
            full_range.tolist(),
            cagr_stats[0].cagr if cagr_stats else None,
        )
        if quality_info is not None:
            dividend_quality = DividendQualityInfo(**quality_info)

    # Yield: same calculation as dashboard — last complete year raw divs / close_price at last payment
    yield_pct = None
    last_year_divs = df[df["year"] == last_year].sort_values("ex_date")
    if len(last_year_divs) > 0:
        raw_col = "raw_amount" if "raw_amount" in last_year_divs.columns else "amount"
        total_div = last_year_divs[raw_col].sum()
        last_div_row = last_year_divs.iloc[-1]
        cp = last_div_row.get("close_price") if hasattr(last_div_row, "get") else last_div_row["close_price"]
        if pd.notna(cp) and pd.notna(total_div) and float(cp) > 0:
            yield_pct = round(utils.dividend_yield(float(total_div), float(cp)), 4)

    # Recent payments (last 10)
    recent = df.sort_values("ex_date", ascending=False).head(10)
    recent_payments = [
        DividendRecord(
            ex_date=row["ex_date"].strftime("%Y-%m-%d"),
            raw_amount=round(float(row["raw_amount"]), 4),
            forward_amount=round(float(row["amount"]), 4),
            shares_at_time=round(float(row["splits_at_time"]), 4),
            year=int(row["year"]),
        )
        for _, row in recent.iterrows()
    ]

    # Fundamentals
    screener_latest = db.get_screener_latest_by_symbol(symbol)
    screener_yearly = db.get_screener_yearly_by_symbol(symbol)

    fund_latest = None
    if screener_latest:
        d = dict(screener_latest)
        fund_latest = FundamentalsLatest(
            payout_ratio=d.get("payout_ratio"),
            dividend_yield=yield_pct,
            pe_ratio=d.get("pe_ratio"),
            roe=d.get("roe"),
            roce=d.get("roce"),
            book_value=d.get("book_value"),
            face_value=d.get("face_value"),
            market_cap_cr=d.get("market_cap_cr"),
            eps=d.get("eps"),
            revenue_growth=d.get("revenue_growth"),
            profit_growth=d.get("profit_growth"),
            debt_to_equity=d.get("debt_to_equity"),
            last_updated=d.get("last_updated"),
        )

    fund_yearly = []
    if screener_yearly:
        for row in screener_yearly:
            d = dict(row)
            fund_yearly.append(
                FundamentalsYearly(
                    fiscal_year=d.get("fiscal_year", ""),
                    payout_ratio=d.get("payout_ratio"),
                    eps=d.get("eps"),
                    net_profit=d.get("net_profit"),
                    revenue=d.get("revenue"),
                    roe=d.get("roe"),
                    roce=d.get("roce"),
                    div_yield=d.get("div_yield"),
                    book_value=d.get("book_value"),
                    debt_to_equity=d.get("debt_to_equity"),
                )
            )

    result = StatsResponse(
        symbol=symbol,
        name=ticker_dict.get("name"),
        current_price=ticker_dict.get("current_price"),
        yield_pct=yield_pct,
        splits=split_records,
        yearly_dividends=yearly_dividends,
        recent_payments=recent_payments,
        cagr_stats=cagr_stats,
        yield_cagr_stats=yield_cagr_stats,
        dividend_quality=dividend_quality,
        years_up=up,
        years_stalled=stalled,
        years_reduced=reduced,
        years_stopped=stopped,
        fundamentals_latest=fund_latest,
        fundamentals_yearly=fund_yearly,
    )
    _cache_set(cache_key, result, ttl=120)
    return result


# ---------------------------------------------------------------------------
# GET /api/screener/{symbol}
# ---------------------------------------------------------------------------

@router.get("/screener/{symbol}", response_model=ScreenerResponse)
def get_screener(symbol: str):
    """Fundamentals snapshot + yearly data. Mirrors the `screener` CLI command."""
    latest = db.get_screener_latest_by_symbol(symbol)
    yearly = db.get_screener_yearly_by_symbol(symbol)

    if not latest and not yearly:
        raise HTTPException(
            status_code=404,
            detail=f"No fundamentals data for {symbol}. Run 'update --symbol {symbol}' first.",
        )

    fund_latest = None
    if latest:
        d = dict(latest)
        fund_latest = FundamentalsLatest(
            payout_ratio=d.get("payout_ratio"),
            dividend_yield=d.get("dividend_yield"),
            pe_ratio=d.get("pe_ratio"),
            roe=d.get("roe"),
            roce=d.get("roce"),
            book_value=d.get("book_value"),
            face_value=d.get("face_value"),
            market_cap_cr=d.get("market_cap_cr"),
            eps=d.get("eps"),
            revenue_growth=d.get("revenue_growth"),
            profit_growth=d.get("profit_growth"),
            debt_to_equity=d.get("debt_to_equity"),
            last_updated=d.get("last_updated"),
        )

    fund_yearly = []
    if yearly:
        for row in yearly:
            d = dict(row)
            fund_yearly.append(
                FundamentalsYearly(
                    fiscal_year=d.get("fiscal_year", ""),
                    payout_ratio=d.get("payout_ratio"),
                    eps=d.get("eps"),
                    net_profit=d.get("net_profit"),
                    revenue=d.get("revenue"),
                    roe=d.get("roe"),
                    roce=d.get("roce"),
                    div_yield=d.get("div_yield"),
                    book_value=d.get("book_value"),
                    debt_to_equity=d.get("debt_to_equity"),
                )
            )

    return ScreenerResponse(symbol=symbol, latest=fund_latest, yearly=fund_yearly)


# ---------------------------------------------------------------------------
# GET /api/top  (used for dashboard cards)
# ---------------------------------------------------------------------------

@router.get("/top", response_model=dict)
def get_top_stocks(n: int = Query(10, ge=1, le=50)):
    """Return top N stocks by yield and by overall CAGR for the dashboard."""
    cache_key = f"top:{n}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    rows = db.query_dividends("", ())
    if not rows:
        return {"by_yield": [], "by_cagr": []}

    split_rows = db.get_all_splits()
    splits_by_ticker: dict = {}
    for s in split_rows:
        tid = s["ticker_id"]
        splits_by_ticker.setdefault(tid, []).append(dict(s))

    ticker_names = {t["symbol"]: t["name"] for t in db.get_all_tickers()}

    df_raw = [dict(r) for r in rows]
    df_adjusted = []
    for tid in {r["ticker_id"] for r in df_raw}:
        ticker_divs = [r for r in df_raw if r["ticker_id"] == tid]
        df_adjusted.extend(utils.adjust_dividends(ticker_divs, splits_by_ticker.get(tid, [])))

    df = pd.DataFrame(df_adjusted)
    df["ex_date"] = pd.to_datetime(df["ex_date"])
    df["year"] = df["ex_date"].dt.year

    current_year = datetime.now().year
    last_year = current_year - 1
    scored = []

    for sym, group in df.groupby("symbol"):
        ticker_id = group["ticker_id"].iloc[0]
        curr_price = group["current_price"].iloc[0] if "current_price" in group.columns else None

        last_year_divs = group[group["year"] == last_year].sort_values("ex_date")
        last_yield_val = 0.0
        if len(last_year_divs) > 0:
            raw_col = "raw_amount" if "raw_amount" in last_year_divs.columns else "amount"
            total_div = last_year_divs[raw_col].sum()
            last_div_row = last_year_divs.iloc[-1]
            cp = last_div_row.get("close_price") if hasattr(last_div_row, "get") else last_div_row["close_price"]
            if pd.notna(cp) and pd.notna(total_div) and float(cp) > 0:
                last_yield_val = utils.dividend_yield(float(total_div), float(cp))

        yearly_totals = (
            group[group["year"] < current_year].groupby("year")["amount"].sum().sort_index()
        )
        cagr_overall = None
        if len(yearly_totals) >= 2:
            cagr_overall = _get_cagr_for_years(
                yearly_totals, yearly_totals.index[-1] - yearly_totals.index[0]
            )

        up, stalled, reduced, stopped = 0, 0, 0, 0
        quality_info = None
        if len(yearly_totals) > 1:
            min_yr = int(yearly_totals.index.min())
            max_yr = int(yearly_totals.index.max())
            full_range = pd.Series(0.0, index=range(min_yr, max_yr + 1))
            full_range.update(yearly_totals.astype(float))
            up, stalled, reduced, stopped = utils.classify_years(full_range.tolist())
            quality_info = utils.dividend_quality_score(full_range.tolist(), cagr_overall)

        scored.append(
            TopStock(
                symbol=str(sym),
                name=ticker_names.get(str(sym)),
                price=round(float(curr_price), 2) if curr_price is not None else None,
                yield_pct=round(last_yield_val, 4),
                cagr_overall=round(cagr_overall, 4) if cagr_overall is not None else None,
                years_up=up,
                dividend_quality_score=quality_info["score"] if quality_info else None,
                dividend_quality_rating=quality_info["rating"] if quality_info else None,
            )
        )

    by_yield = sorted(
        [s for s in scored if (s.yield_pct or 0) > 0],
        key=lambda x: x.yield_pct or 0,
        reverse=True,
    )[:n]

    by_cagr = sorted(
        [s for s in scored if s.cagr_overall is not None],
        key=lambda x: x.cagr_overall or 0,
        reverse=True,
    )[:n]

    by_quality = sorted(
        [s for s in scored if s.dividend_quality_score is not None],
        key=lambda x: (
            x.dividend_quality_score or 0,
            x.years_up or 0,
            x.cagr_overall or 0,
        ),
        reverse=True,
    )[:n]

    result = {
        "by_yield": [s.model_dump() for s in by_yield],
        "by_cagr": [s.model_dump() for s in by_cagr],
        "by_quality": [s.model_dump() for s in by_quality],
    }
    _cache_set(cache_key, result, ttl=300)
    return result


# ---------------------------------------------------------------------------
# POST /api/update  +  GET /api/update/progress  (SSE)
# ---------------------------------------------------------------------------

# In-memory job store: job_id -> {"status": str, "events": list[str], "done": bool}
_update_jobs: dict = {}


@router.post("/update")
def start_update(req: UpdateRequest):
    """Trigger an update job and return a job ID for SSE progress streaming."""
    job_id = str(uuid.uuid4())
    _update_jobs[job_id] = {"status": "running", "events": [], "done": False, "error": None}

    # Parse comma-separated symbols
    raw_symbols: list[str] = []
    if req.symbol:
        raw_symbols = [s.strip().upper() for s in req.symbol.split(",") if s.strip()]

    def _run():
        job = _update_jobs[job_id]
        try:
            def emit(msg: str):
                job["events"].append(msg)

            if not raw_symbols:
                emit("Updating ticker list from NSE...")
                added = fetch.download_nse_tickers()
                emit(f"Added {added} new tickers.")

            if raw_symbols:
                tickers = []
                for sym in raw_symbols:
                    tid = db.upsert_ticker(sym)
                    tickers.append({
                        "id": tid,
                        "symbol": sym,
                        "last_updated": db.get_ticker_last_updated(tid),
                    })
            else:
                tickers = [dict(t) for t in db.get_all_tickers()]
                if req.limit:
                    tickers = tickers[: req.limit]

            emit(f"Checking data for {len(tickers)} tickers...")
            threshold = datetime.utcnow() - timedelta(days=req.max_age or 7)

            def is_stale(ts):
                if not ts:
                    return True
                try:
                    return datetime.fromisoformat(ts) < threshold
                except ValueError:
                    return True

            conn = db.get_connection()
            try:
                cur = conn.execute("SELECT ticker_id, last_updated FROM screener_latest")
                fund_updated = {row["ticker_id"]: row["last_updated"] for row in cur.fetchall()}
            finally:
                conn.close()

            to_update = []
            for t in tickers:
                sym = t["symbol"]
                tid = t["id"]
                needs_yahoo = req.force or is_stale(t.get("last_updated"))
                needs_fund = req.force or is_stale(fund_updated.get(tid))
                if needs_yahoo or needs_fund:
                    to_update.append((sym, tid, needs_yahoo, needs_fund))

            total = len(to_update)
            if total == 0:
                emit("All data is up to date.")
                job["status"] = "done"
                job["done"] = True
                return

            emit(f"Updating {total} tickers...")
            job["total"] = total

            for i, (sym, tid, needs_yahoo, needs_fund) in enumerate(to_update):
                try:
                    if needs_yahoo:
                        fetch.fetch_dividends(sym)
                    if needs_fund:
                        fetch.fetch_fundamentals(sym, tid)
                    emit(f"[{i + 1}/{total}] {sym} OK")
                except Exception as e:
                    emit(f"[{i + 1}/{total}] {sym} ERROR: {e}")
                job["progress"] = i + 1

            emit("Done!")
            job["status"] = "done"
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
            job["events"].append(f"Fatal error: {e}")
        finally:
            job["done"] = True
            _cache_clear()  # Invalidate all cached data after an update

    thread = Thread(target=_run, daemon=True)
    thread.start()
    return {"job_id": job_id}


@router.get("/update/progress/{job_id}")
async def update_progress(job_id: str):
    """SSE stream of progress events for an update job."""
    if job_id not in _update_jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    async def event_stream() -> AsyncGenerator[str, None]:
        job = _update_jobs[job_id]
        sent = 0
        while True:
            events = job["events"]
            while sent < len(events):
                msg = events[sent]
                done_count = job.get("progress", 0)
                total = job.get("total", 0)
                pct = round(done_count / total * 100) if total else 0
                payload = json.dumps({"log": msg, "progress": pct})
                yield f"data: {payload}\n\n"
                sent += 1
            if job["done"]:
                final = json.dumps({
                    "log": "Update complete." if job["status"] == "done" else f"Error: {job.get('error')}",
                    "progress": 100,
                    "done": True,
                    "error": job.get("error"),
                })
                yield f"data: {final}\n\n"
                break
            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
