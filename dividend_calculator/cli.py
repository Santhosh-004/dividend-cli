"""Command-line interface for dividend_calculator.

Provides sub-commands to update data, filter stocks based on dividend
performance, and view stats for a single ticker.
"""

import sys
import io
import shutil
import subprocess
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import click
import pandas as pd
from tabulate import tabulate
from datetime import datetime, timedelta, timezone
from tqdm import tqdm
from typing import Optional

from . import __version__, db
from . import fetch
from .timeutils import parse_utc_timestamp
from . import utils


def _frontend_build_is_stale(frontend_dir: Path, frontend_dist: Path) -> bool:
    if not frontend_dist.exists():
        return True

    index_file = frontend_dist / "index.html"
    if not index_file.exists():
        return True

    dist_mtime = index_file.stat().st_mtime
    watch_dirs = [frontend_dir / "src", frontend_dir / "static"]
    watch_files = [
        frontend_dir / "package.json",
        frontend_dir / "package-lock.json",
        frontend_dir / "svelte.config.js",
        frontend_dir / "vite.config.ts",
        frontend_dir / "tsconfig.json",
    ]

    for path in watch_files:
        if path.exists() and path.stat().st_mtime > dist_mtime:
            return True

    for directory in watch_dirs:
        if not directory.exists():
            continue
        for item in directory.rglob("*"):
            if item.is_file() and item.stat().st_mtime > dist_mtime:
                return True

    return False


@click.group()
@click.version_option(version=__version__, prog_name="dividend-cli")
def main():
    """Indian Stock Dividend Calculator & Filter CLI."""
    pass


@main.command()
@click.option("--symbol", help="Update a specific ticker symbol.")
@click.option("--force", is_flag=True, help="Force update of all tickers.")
@click.option("--max-age", default=90, help="Maximum age of data in days before refresh.")
@click.option("--limit", default=None, type=int, help="Limit the number of tickers to update (for testing).")
def update(symbol, force, max_age, limit):
    """Refresh ticker list and fetch missing dividend/price and fundamentals data."""
    if not symbol:
        click.echo("Updating ticker list from NSE...")
        added = fetch.download_nse_tickers()
        click.echo(f"Added {added} new tickers.")

    if symbol:
        # Ensure the ticker exists in the DB first
        ticker_id = db.upsert_ticker(symbol)
        tickers = [{"id": ticker_id, "symbol": symbol, "last_updated": db.get_ticker_last_updated(ticker_id)}]
    else:
        tickers = db.get_all_tickers()
        if limit:
            tickers = tickers[:limit]

    click.echo(f"Checking data for {len(tickers)} tickers...")
    
    threshold = datetime.now(timezone.utc) - timedelta(days=max_age)

    def is_stale(timestamp: Optional[str]) -> bool:
        if not timestamp:
            return True
        try:
            return parse_utc_timestamp(timestamp) < threshold
        except ValueError:
            return True

    conn = db.get_connection()
    try:
        cur = conn.execute("SELECT ticker_id, last_updated FROM screener_latest")
        fundamentals_updated = {row["ticker_id"]: row["last_updated"] for row in cur.fetchall()}
    finally:
        conn.close()

    to_update = []
    for ticker in tickers:
        sym = ticker["symbol"]
        ticker_id = ticker["id"]
        needs_yahoo = force or is_stale(ticker["last_updated"])
        needs_fundamentals = force or is_stale(fundamentals_updated.get(ticker_id))
        if needs_yahoo or needs_fundamentals:
            to_update.append((sym, ticker_id, needs_yahoo, needs_fundamentals))

    total_updates = len(to_update)
    
    if total_updates == 0:
        click.echo("All data is up to date.")
        return
    
    click.echo(f"Updating {total_updates} tickers sequentially...")
    
    # Process sequentially
    with tqdm(total=total_updates, desc="Updating") as pbar:
        for sym, ticker_id, needs_yahoo, needs_fundamentals in to_update:
            try:
                if needs_yahoo:
                    fetch.fetch_dividends(sym)
                if needs_fundamentals:
                    fetch.fetch_fundamentals(sym, ticker_id)
            except Exception:
                pass
            pbar.update(1)
    
    click.echo("Done!")


def get_cagr_for_years(yearly_totals: pd.Series, years: int) -> Optional[float]:
    """Helper to calculate CAGR for the last N years.
    
    Fills in any missing years within the period with 0, then calculates CAGR
    from the first non-zero value to the last year. Only returns a value if
    the stock has been paying dividends for at least 'years' number of years.
    """
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


def get_yield_cagr_for_years(group: pd.DataFrame, years: int) -> Optional[float]:
    """Helper to calculate CAGR of dividend yield for the last N years.
    
    Calculates yearly dividend yield (total dividend / price on last dividend date)
    for each year, then calculates CAGR of those yields.
    """
    if len(group) < 2:
        return None
    
    current_year = datetime.now().year
    last_year = current_year - 1
    start_year = last_year - years
    
    yearly_yields = {}
    for yr in range(start_year, current_year + 1):
        yr_divs = group[group['year'] == yr].sort_values('ex_date')
        if len(yr_divs) > 0:
            raw_col = 'raw_amount' if 'raw_amount' in yr_divs.columns else 'amount'
            total_div = yr_divs[raw_col].sum()
            last_div_row = yr_divs.iloc[-1]
            if pd.notna(last_div_row.get('close_price')) and pd.notna(total_div) and float(last_div_row.get('close_price')) > 0:
                yield_val = utils.dividend_yield(float(total_div), float(last_div_row.get('close_price')))
                yearly_yields[yr] = yield_val
    
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


@main.command()
@click.option("--symbol", help="Filter by specific ticker symbol.")
@click.option("--min-yield", type=float, help="Minimum average dividend yield (%).")
@click.option("--max-yield", type=float, help="Maximum average dividend yield (%).")
@click.option("--div-growth-min", type=float, help="Minimum overall dividend growth (%).")
@click.option("--div-3yr-min", type=float, help="Minimum 3Yr dividend growth (%).")
@click.option("--div-5yr-min", type=float, help="Minimum 5Yr dividend growth (%).")
@click.option("--div-10yr-min", type=float, help="Minimum 10Yr dividend growth (%).")
@click.option("--years-up", type=int, help="Minimum number of years with dividend growth.")
@click.option("--years-stalled", type=int, help="Maximum number of years with stalled dividends.")
@click.option("--years-reduced", type=int, help="Maximum number of years with reduced dividends.")
@click.option("--years-stopped", type=int, help="Maximum number of years with stopped dividends.")
@click.option("--min-payout", type=float, help="Minimum payout ratio (%).")
@click.option("--max-payout", type=float, help="Maximum payout ratio (%).")
@click.option("--min-roe", type=float, help="Minimum ROE (%).")
@click.option("--min-roce", type=float, help="Minimum ROCE (%).")
@click.option("--min-div-quality", type=float, help="Minimum dividend quality score (0-100).")
@click.option("--condition", help="Arbitrary Python-style condition (e.g. '(years_stopped + years_stalled) * 2 <= years_up')")
def filter(symbol, min_yield, max_yield, div_growth_min, div_3yr_min, div_5yr_min, div_10yr_min, years_up, years_stalled, years_reduced, years_stopped, min_payout, max_payout, min_roe, min_roce, min_div_quality, condition):
    """Filter stocks based on dividend criteria."""
    # We'll fetch all dividends and group them in Python for complex CAGR/Year logic
    # though simple filters could be done in SQL.
    
    sql_filters = []
    params = []
    if symbol:
        sql_filters.append("t.symbol = ?")
        params.append(symbol)
    
    where_clause = ""
    if sql_filters:
        where_clause = "WHERE " + " AND ".join(sql_filters)
    
    rows = db.query_dividends(where_clause, tuple(params))
    if not rows:
        click.echo("No data found matching initial criteria.")
        return

    # Fetch splits to adjust dividends
    split_rows = db.get_all_splits()
    splits_by_ticker = {}
    for s in split_rows:
        tid = s['ticker_id']
        if tid not in splits_by_ticker:
            splits_by_ticker[tid] = []
        splits_by_ticker[tid].append(dict(s))
    
    # Fetch screener data for all tickers
    screener_data = {}
    conn = db.get_connection()
    try:
        cur = conn.execute("SELECT * FROM screener_latest")
        for row in cur.fetchall():
            screener_data[row['ticker_id']] = dict(row)
    finally:
        conn.close()

    # Process results into a DataFrame
    df_raw = [dict(r) for r in rows]
    
    # Adjust dividends for splits per ticker
    df_adjusted = []
    ticker_ids = {r['ticker_id'] for r in df_raw}
    for tid in ticker_ids:
        ticker_divs = [r for r in df_raw if r['ticker_id'] == tid]
        ticker_splits = splits_by_ticker.get(tid, [])
        df_adjusted.extend(utils.adjust_dividends(ticker_divs, ticker_splits))

    df = pd.DataFrame(df_adjusted)
    df['ex_date'] = pd.to_datetime(df['ex_date'])
    df['year'] = df['ex_date'].dt.year
    
    results = []
    
    # Pre-process condition string: replace hyphens with underscores in names
    eval_condition = condition
    if eval_condition:
        # Simple replacement for common user patterns like years-up -> years_up
        for field in ['years-up', 'years-stalled', 'years-reduced', 'years-stopped', 'cagr-overall']:
            eval_condition = eval_condition.replace(field, field.replace('-', '_'))

    for sym, group in df.groupby('symbol'):
        ticker_id = group['ticker_id'].iloc[0]
        curr_price = group['current_price'].iloc[0] if 'current_price' in group.columns else None
        
        # Get screener data for this ticker
        screener = screener_data.get(ticker_id, {})

        # Calculate final share count based on ALL splits in DB (even after last dividend)
        all_splits = splits_by_ticker.get(ticker_id, [])
        final_shares = 1.0
        for s in all_splits:
            final_shares *= (s['numerator'] / s['denominator'])

        # Calculate yield - total dividend of year / price on last dividend date
        from datetime import datetime
        current_year = datetime.now().year
        last_year = current_year - 1
        
        last_year_divs = group[group['year'] == last_year].sort_values('ex_date')
        
        last_yield = 0
        if len(last_year_divs) > 0:
            raw_col = 'raw_amount' if 'raw_amount' in last_year_divs.columns else 'amount'
            total_div = last_year_divs[raw_col].sum()
            last_div_row = last_year_divs.iloc[-1]
            if pd.notna(last_div_row.get('close_price')) and pd.notna(total_div):
                last_yield = utils.dividend_yield(float(total_div), float(last_div_row.get('close_price')))
        
        if min_yield is not None and last_yield < min_yield:
            continue
        if max_yield is not None and last_yield > max_yield:
            continue
        
        # Filter by screener data
        payout = screener.get('payout_ratio')
        roe = screener.get('roe')
        roce = screener.get('roce')
        
        if min_payout is not None and (payout is None or payout < min_payout):
            continue
        if max_payout is not None and (payout is None or payout > max_payout):
            continue
        if min_roe is not None and (roe is None or roe < min_roe):
            continue
        if min_roce is not None and (roce is None or roce < min_roce):
            continue
            
        # Yearly totals for CAGR and classifications - exclude current year
        from datetime import datetime
        current_year = datetime.now().year
        yearly_totals = group[group['year'] < current_year].groupby('year')['amount'].sum().sort_index()
        
        # Skip if no data
        if len(yearly_totals) == 0:
            continue
        
        # Classification - fill missing years with 0
        min_year = int(yearly_totals.index.min())
        max_year = int(yearly_totals.index.max())
        full_year_range = pd.Series(0.0, index=range(min_year, max_year + 1))
        full_year_range.update(yearly_totals.astype(float))
        yearly_totals_list = full_year_range.tolist()
        
        # Classification
        up, stalled, reduced, stopped = utils.classify_years(yearly_totals_list)
        
        if years_up is not None and up < years_up:
            continue
        if years_stalled is not None and stalled > years_stalled:
            continue
        if years_reduced is not None and reduced > years_reduced:
            continue
        if years_stopped is not None and stopped > years_stopped:
            continue
            
        # CAGRs - use get_cagr_for_years for consistency with stats
        cagr_overall = get_cagr_for_years(yearly_totals, yearly_totals.index[-1] - yearly_totals.index[0]) if len(yearly_totals) >= 2 else 0
        
        # Legacy dispersion metrics kept for backward compatibility in conditions
        if len(yearly_totals) >= 2:
            div_mean = yearly_totals.mean()
            div_std = yearly_totals.std()
            div_cv = (div_std / div_mean * 100) if div_mean > 0 else None
        else:
            div_std = None
            div_cv = None
            
        if div_growth_min is not None and cagr_overall < div_growth_min:
            continue
            
        c3 = get_cagr_for_years(yearly_totals, 3)
        c5 = get_cagr_for_years(yearly_totals, 5)
        c10 = get_cagr_for_years(yearly_totals, 10)
        c15 = get_cagr_for_years(yearly_totals, 15)
        c20 = get_cagr_for_years(yearly_totals, 20)
        c25 = get_cagr_for_years(yearly_totals, 25)
        c30 = get_cagr_for_years(yearly_totals, 30)
        
        if div_3yr_min is not None and (c3 is None or c3 < div_3yr_min):
            continue
        if div_5yr_min is not None and (c5 is None or c5 < div_5yr_min):
            continue
        if div_10yr_min is not None and (c10 is None or c10 < div_10yr_min):
            continue

        quality = utils.dividend_quality_score(yearly_totals_list, cagr_overall)
        dq_score = quality["score"] if quality else None
        dq_rating = quality["rating"] if quality else None

        if min_div_quality is not None and (dq_score is None or dq_score < min_div_quality):
            continue

        # Evaluate arbitrary condition if provided
        if eval_condition:
            eval_vars = {
                'up': up, 'years_up': up,
                'stalled': stalled, 'years_stalled': stalled,
                'reduced': reduced, 'years_reduced': reduced,
                'stopped': stopped, 'years_stopped': stopped,
                'yield': last_yield, 'yld': last_yield, 'last_yield': last_yield,
                'div_growth': cagr_overall, 'div_growth_overall': cagr_overall, 'cagr_overall': cagr_overall,
                'c3': c3 or 0, 'div_3yr': c3 or 0,
                'c5': c5 or 0, 'div_5yr': c5 or 0,
                'c10': c10 or 0, 'div_10yr': c10 or 0,
                'c15': c15 or 0, 'div_15yr': c15 or 0,
                'c20': c20 or 0, 'div_20yr': c20 or 0,
                'c25': c25 or 0, 'div_25yr': c25 or 0,
                'c30': c30 or 0, 'div_30yr': c30 or 0,
                'price': curr_price or 0,
                'shares': final_shares,
                'div_mean': float(div_mean) if div_std is not None else 0,
                'div_std': float(div_std) if div_std is not None else 0,
                'div_cv': float(div_cv) if div_cv is not None else 0,
                'dq_score': float(dq_score) if dq_score is not None else 0,
                'dividend_quality_score': float(dq_score) if dq_score is not None else 0,
                'dq_rating': dq_rating or '',
                'dividend_quality_rating': dq_rating or '',
                'payout': payout or 0,
                'roe': roe or 0,
                'roce': roce or 0,
            }
            try:
                if not eval(eval_condition, {"__builtins__": {}}, eval_vars):
                    continue
            except Exception as e:
                click.echo(f"Error evaluating condition '{condition}' for {sym}: {e}", err=True)
                continue
            
        res = {
            "Symbol": sym,
            "Price": round(curr_price, 2) if curr_price is not None else "N/A",
            "Shares": round(final_shares, 2),
            "Yield (%)": round(last_yield, 2),
            "Payout %": round(payout, 1) if payout is not None else "N/A",
            "ROE %": round(roe, 1) if roe is not None else "N/A",
            "ROCE %": round(roce, 1) if roce is not None else "N/A",
            "Div Quality": round(float(dq_score), 2) if dq_score is not None else "N/A",
            "Quality Band": dq_rating or "N/A",
            "Div Mean": round(float(div_mean), 2) if div_std is not None else "N/A",
            "Div StdDev": round(float(div_std), 2) if div_std is not None else "N/A",
            "CV (%)": round(float(div_cv), 2) if div_cv is not None else "N/A",
            "Yrs Up": up,
            "Yrs Stalled": stalled,
            "Yrs Reduced": reduced,
            "Yrs Stopped": stopped,
            "Div Overall (%)": round(cagr_overall, 2),
            "Div 3Yr (%)": round(c3, 2) if c3 is not None else "N/A",
            "Div 5Yr (%)": round(c5, 2) if c5 is not None else "N/A",
            "Div 10Yr (%)": round(c10, 2) if c10 is not None else "N/A",
            "Div 15Yr (%)": round(c15, 2) if c15 is not None else "N/A",
            "Div 20Yr (%)": round(c20, 2) if c20 is not None else "N/A",
            "Div 25Yr (%)": round(c25, 2) if c25 is not None else "N/A",
            "Div 30Yr (%)": round(c30, 2) if c30 is not None else "N/A",
        }
        results.append(res)
        
    if not results:
        click.echo("No stocks matched all filters.")
    else:
        # Clean up results (handle NaN)
        for res in results:
            for k, v in res.items():
                if pd.isna(v):
                    res[k] = "N/A"

        click.echo(f"Found {len(results)} stocks matching your criteria:\n")

        # Repeat headers every 30 rows for better readability in long lists
        header_interval = 30
        legend_tip = "COLUMNS: CAGR=% Growth, Yrs Up=Increased, Stalled=Unchanged, Reduced=Decreased, Stopped=Zero"
        
        for i in range(0, len(results), header_interval):
            if i > 0:
                click.echo(f"\n{legend_tip}")
            chunk = results[i:i + header_interval]
            click.echo(tabulate(chunk, headers="keys", tablefmt="grid"))

        click.echo("\n" + "="*40)
        click.echo("DETAILED COLUMN LEGEND (FORWARD-ADJUSTED MODEL):")
        click.echo("  Price            : Current market price (raw)")
        click.echo("  Shares           : How many shares 1 original share has become via splits")
        click.echo("  Yield (%)        : Last year's total dividend / price on last dividend date * 100")
        click.echo("  Div Quality      : 0-100 score for stable and growing dividend history")
        click.echo("                     Rewards years-up, growth, smooth trend; penalizes cuts/stops")
        click.echo("  Quality Band     : Elite / Strong / Developing / Fragile")
        click.echo("  Div Mean         : Mean (average) of yearly dividend totals")
        click.echo("  Div StdDev       : Standard deviation of yearly dividend totals (volatility)")
        click.echo("                     Legacy diagnostic only, not the main quality metric")
        click.echo("  Div CV (%)       : Coefficient of Variation = StdDev/Mean*100")
        click.echo("                     Legacy dispersion metric; can misclassify strong growers")
        click.echo("  Yrs Up           : Years where total payout was GREATER than prev year")
        click.echo("  Yrs Stalled      : Years where total payout was EQUAL to prev year")
        click.echo("  Yrs Reduced      : Years where total payout was LOWER than prev year")
        click.echo("  Yrs Stopped      : Years where total payout was ZERO")
        click.echo("  Div Growth Overall (%) : Dividend growth (CAGR) from first year to last year")
        click.echo("  Div 3Yr-30Yr    : Dividend growth (CAGR) for last N years")
        click.echo("  --condition      : Arbitrary Python expression using variables above")
        click.echo("                     Example: '(years_stopped + years_stalled) * 2 <= years_up'")
        click.echo("="*40)


@main.command()
@click.argument("symbol")
def stats(symbol):
    """Show detailed dividend statistics for a single ticker."""
    # Get ticker id first
    tickers = db.get_all_tickers()
    ticker = next((t for t in tickers if t['symbol'] == symbol), None)
    if not ticker:
        click.echo(f"Ticker {symbol} not found in DB.")
        return
    
    ticker_id = ticker['id']
    rows = db.query_dividends("WHERE t.symbol = ?", (symbol,))
    if not rows:
        click.echo(f"No data found for {symbol}. Try running 'update' first.")
        return
        
    splits = db.get_splits(ticker_id)
    df_raw = [dict(r) for r in rows]
    df_adjusted = utils.adjust_dividends(df_raw, [dict(s) for s in splits])

    df = pd.DataFrame(df_adjusted)
    df['ex_date'] = pd.to_datetime(df['ex_date'])
    df['year'] = df['ex_date'].dt.year
    
    click.echo(f"--- {symbol} Dividend Stats (Split-Adjusted) ---")
    
    if splits:
        click.echo("\nStock Splits Found:")
        click.echo(tabulate([(s['ex_date'], f"{s['numerator']}:{s['denominator']}") for s in splits], 
                           headers=["Ex‑Date", "Ratio"], tablefmt="simple"))
    
    # For CAGR and classification, use forward-adjusted to show growth of 1 original share
    yearly_forward = df.groupby('year')['amount'].sum().sort_index()
    
    # Show yearly totals - get raw, shares at time, and count
    yearly_data = df.groupby('year').agg({
        'raw_amount': 'sum',
        'splits_at_time': 'first',
        'id': 'count'
    }).sort_index(ascending=False)
    
    # Calculate consolidated = raw * shares at that time
    yearly_combined = pd.DataFrame({
        'Raw': yearly_data['raw_amount'],
        'Shares': yearly_data['splits_at_time'],
        'Consolidated': yearly_data['raw_amount'] * yearly_data['splits_at_time'],
        'Dividends Announced': yearly_data['id']
    })
    
    click.echo("\nYearly Totals (Consolidated):")
    click.echo(tabulate(yearly_combined, headers="keys", tablefmt="simple"))
    
    # Exclude current year from CAGR calculation (use completed years only)
    from datetime import datetime
    current_year = datetime.now().year
    yearly_forward_complete = yearly_forward[yearly_forward.index < current_year]
    
    click.echo(f"\nCAGR Stats (Forward-Adjusted, excluding {current_year}):")
    cagrs = [
        ("Overall", get_cagr_for_years(yearly_forward_complete, yearly_forward_complete.index[-1] - yearly_forward_complete.index[0]) if len(yearly_forward_complete) > 1 else 0),
        ("3 Year", get_cagr_for_years(yearly_forward_complete, 3)),
        ("5 Year", get_cagr_for_years(yearly_forward_complete, 5)),
        ("10 Year", get_cagr_for_years(yearly_forward_complete, 10)),
        ("15 Year", get_cagr_for_years(yearly_forward_complete, 15)),
        ("20 Year", get_cagr_for_years(yearly_forward_complete, 20)),
        ("30 Year", get_cagr_for_years(yearly_forward_complete, 30)),
    ]
    click.echo(tabulate([(n, f"{v:.2f}%" if v else "N/A") for n, v in cagrs], headers=["Period", "CAGR"], tablefmt="simple"))

    full_year_range = None
    if len(yearly_forward_complete) > 0:
        min_year = yearly_forward_complete.index.min()
        max_year = yearly_forward_complete.index.max()
        full_year_range = pd.Series(0.0, index=range(min_year, max_year + 1))
        full_year_range.update(yearly_forward_complete.astype(float))
    
    if len(yearly_forward_complete) >= 2:
        div_mean = yearly_forward_complete.mean()
        div_std = yearly_forward_complete.std()
        div_cv = (div_std / div_mean * 100) if div_mean > 0 else None
        quality = utils.dividend_quality_score(full_year_range.tolist() if full_year_range is not None else [], cagrs[0][1])

        click.echo(f"\nDividend Quality:")
        if quality is not None:
            click.echo(f"Quality Score:        {quality['score']:.2f}/100")
            click.echo(f"Quality Rating:       {quality['rating']}")
            click.echo(f"Consistency Score:    {quality['consistency_score']:.2f}")
            click.echo(f"Growth Score:         {quality['growth_score']:.2f}")
            click.echo(f"Trend Score:          {quality['trend_score']:.2f}")
            click.echo(f"History Score:        {quality['history_score']:.2f}")
        click.echo(f"Mean Yearly Dividend: ₹{div_mean:.2f}")
        click.echo(f"Std Deviation:        ₹{div_std:.2f}")
        click.echo(f"CV (Legacy):          {div_cv:.2f}%" if div_cv is not None else "CV (Legacy):          N/A")
    else:
        click.echo("\nDividend Quality: Not enough data (need >=2 years)")
    
    click.echo(f"\nYield CAGR (Dividend/Price Growth, excluding {current_year}):")
    yield_cagrs = [
        ("10 Year", get_yield_cagr_for_years(df[df['year'] < current_year], 10)),
        ("15 Year", get_yield_cagr_for_years(df[df['year'] < current_year], 15)),
        ("20 Year", get_yield_cagr_for_years(df[df['year'] < current_year], 20)),
        ("25 Year", get_yield_cagr_for_years(df[df['year'] < current_year], 25)),
        ("30 Year", get_yield_cagr_for_years(df[df['year'] < current_year], 30)),
    ]
    click.echo(tabulate([(n, f"{v:.2f}%" if v else "N/A") for n, v in yield_cagrs], headers=["Period", "Yield CAGR"], tablefmt="simple"))
    
    # Yearly changes classification - fill missing years with 0 for accurate counts
    yearly_forward_complete_list = full_year_range.tolist() if full_year_range is not None else []
    up, stalled, reduced, stopped = utils.classify_years(yearly_forward_complete_list)
    click.echo("\nYear-over-Year Summary:")
    click.echo(f"Years Up:      {up}")
    click.echo(f"Years Stalled: {stalled}")
    click.echo(f"Years Reduced: {reduced}")
    click.echo(f"Years Stopped: {stopped}")
    
    # Recent dividends - show both raw and forward amounts
    click.echo("\nRecent Payments (Raw & Forward-Adjusted):")
    recent = df.sort_values('ex_date', ascending=False).head(10)[['ex_date', 'raw_amount', 'amount', 'splits_at_time']].copy()
    recent['ex_date'] = recent['ex_date'].dt.strftime('%Y-%m-%d')
    recent = recent.rename(columns={'amount': 'forward', 'raw_amount': 'raw', 'splits_at_time': 'shares'})
    recent = recent[['ex_date', 'raw', 'forward', 'shares']]
    click.echo(tabulate(recent, 
                        headers=['Ex‑Date', 'Raw', 'Forward', 'Shares'], tablefmt='simple'))
    
    # Show fundamentals data if available
    screener_latest = db.get_screener_latest_by_symbol(symbol)
    screener_yearly = db.get_screener_yearly_by_symbol(symbol)
    
    if screener_latest or screener_yearly:
        click.echo("\n" + "="*60)
        click.echo("FUNDAMENTALS DATA")
        click.echo("="*60)
        
        if screener_latest:
            click.echo("\nLatest Snapshot:")
            latest_dict = dict(screener_latest)
            for key, value in latest_dict.items():
                if key not in ['ticker_id', 'symbol', 'last_updated'] and value is not None:
                    click.echo(f"  {key}: {value}")
        
        if screener_yearly:
            click.echo("\nYearly Payout Ratios:")
            yearly_payout = []
            for row in screener_yearly:
                row_dict = dict(row)
                yearly_payout.append({
                    'Year': row_dict.get('fiscal_year', ''),
                    'Payout %': row_dict.get('payout_ratio', 'N/A'),
                    'EPS': row_dict.get('eps', 'N/A'),
                    'Net Profit': row_dict.get('net_profit', 'N/A'),
                    'ROE %': row_dict.get('roe', 'N/A'),
                })
            click.echo(tabulate(yearly_payout, headers="keys", tablefmt="simple"))
    
    click.echo("")


@main.command()
@click.argument("symbol")
def screener(symbol):
    """Show fundamentals data for a ticker."""
    ticker_id = db.upsert_ticker(symbol)
    
    # Get latest data
    latest = db.get_screener_latest_by_symbol(symbol)
    
    if not latest:
        click.echo(f"No fundamentals data found for {symbol}.")
        click.echo("Run 'update --symbol {symbol}' to fetch data.")
        return
    
    click.echo(f"--- {symbol} Fundamentals Data ---")
    click.echo("\nLatest Snapshot:")
    
    latest_dict = dict(latest)
    for key, value in latest_dict.items():
        if key not in ['ticker_id', 'symbol'] and value is not None:
            click.echo(f"  {key}: {value}")
    
    # Get yearly data
    yearly = db.get_screener_yearly_by_symbol(symbol)
    
    if yearly:
        click.echo("\nYearly Data:")
        yearly_data = []
        for row in yearly:
            row_dict = dict(row)
            yearly_data.append({
                'Year': row_dict.get('fiscal_year', ''),
                'Payout %': row_dict.get('payout_ratio', 'N/A'),
                'EPS': row_dict.get('eps', 'N/A'),
                'Net Profit': row_dict.get('net_profit', 'N/A'),
                'ROE %': row_dict.get('roe', 'N/A'),
            })
        
        click.echo(tabulate(yearly_data, headers="keys", tablefmt="simple"))
    else:
        click.echo("\nNo yearly data available.")


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind the server to.")
@click.option("--port", default=7788, show_default=True, help="Port to listen on.")
@click.option(
    "--open/--no-open",
    "open_browser",
    default=True,
    show_default=True,
    help="Open the browser automatically when the server starts.",
)
def serve(host, port, open_browser):
    """Start the Dividend CLI web UI server."""
    try:
        import uvicorn
        from .server import app as server_app
    except ImportError:
        click.echo("The web UI server dependencies are missing. Install them with:")
        click.echo("  pip install 'dividend-calculator[web]'")
        raise SystemExit(1)

    project_root = Path(__file__).resolve().parent.parent
    frontend_dir = project_root / "frontend"
    frontend_dist = frontend_dir / "dist"
    frontend_package = frontend_dir / "package.json"
    npm_cmd = shutil.which("npm")

    if frontend_package.exists():
        needs_build = _frontend_build_is_stale(frontend_dir, frontend_dist)

        if npm_cmd is None:
            if needs_build:
                click.echo("The web UI build is missing or stale and npm is not installed or not on PATH.")
                click.echo("Install Node.js/npm, then run:")
                click.echo("  cd frontend && npm install && npm run build")
                raise SystemExit(1)
        elif needs_build:
            click.echo("Preparing local web UI assets...")
            lockfile = frontend_dir / "package-lock.json"
            node_modules = frontend_dir / "node_modules"
            install_cmd = None
            if not node_modules.exists():
                install_cmd = [npm_cmd, "ci"] if lockfile.exists() else [npm_cmd, "install"]

            try:
                if install_cmd is not None:
                    subprocess.run(install_cmd, cwd=frontend_dir, check=True)
                subprocess.run([npm_cmd, "run", "build"], cwd=frontend_dir, check=True)
            except FileNotFoundError:
                click.echo("npm was not found while preparing the frontend build.")
                raise SystemExit(1)
            except subprocess.CalledProcessError as exc:
                click.echo(f"Failed to prepare frontend assets (exit code {exc.returncode}).")
                raise SystemExit(exc.returncode)

    url = f"http://{host}:{port}"
    click.echo(f"Starting Dividend CLI web UI at {url}")
    click.echo("Press Ctrl+C to stop.")

    if open_browser:
        import threading
        import webbrowser
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        server_app,
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
