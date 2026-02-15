"""Command‑line interface for dividend_calculator.

Provides sub‑commands to update data, filter stocks based on dividend
performance, and view stats for a single ticker.
"""

import click
import pandas as pd
from tabulate import tabulate
from datetime import datetime, timedelta
from tqdm import tqdm
from typing import Optional

from . import db
from . import fetch
from . import utils

__version__ = "1.0.0"


@click.group()
@click.version_option(version=__version__, prog_name="dividend-cli")
def main():
    """Indian Stock Dividend Calculator & Filter CLI."""
    pass


@main.command()
@click.option("--force", is_flag=True, help="Force update of all tickers.")
@click.option("--max-age", default=90, help="Maximum age of data in days before refresh.")
@click.option("--limit", default=None, type=int, help="Limit the number of tickers to update (for testing).")
def update(force, max_age, limit):
    """Refresh ticker list and fetch missing dividend/price data."""
    click.echo("Updating ticker list from NSE...")
    added = fetch.download_nse_tickers()
    click.echo(f"Added {added} new tickers.")

    tickers = db.get_all_tickers()
    if limit:
        tickers = tickers[:limit]

    click.echo(f"Checking data for {len(tickers)} tickers...")
    
    threshold = datetime.utcnow() - timedelta(days=max_age)

    for ticker in tqdm(tickers, desc="Updating data"):
        symbol = ticker["symbol"]
        last_updated_str = ticker["last_updated"]
        
        should_update = force or not last_updated_str
        if not should_update and last_updated_str:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated < threshold:
                should_update = True
        
        if should_update:
            try:
                new_div, new_price = fetch.fetch_dividends(symbol)
                # fetch.fetch_dividends already updates the timestamp in DB
            except Exception as e:
                click.echo(f"\nError fetching data for {symbol}: {e}", err=True)


def get_cagr_for_years(yearly_totals: pd.Series, years: int) -> Optional[float]:
    """Helper to calculate CAGR for the last N years.
    
    Finds the first year with non-zero dividend data within the last N years
    and calculates CAGR from that year to the last year.
    """
    if len(yearly_totals) < 2:
        return None
    
    last_year = yearly_totals.index[-1]
    start_year = last_year - years
    
    # Find the first year >= start_year that has data
    valid_years = yearly_totals[yearly_totals.index >= start_year]
    
    if len(valid_years) < 2:
        return None
    
    first_val = valid_years.iloc[0]
    first_year = valid_years.index[0]
    last_val = valid_years.iloc[-1]
    actual_years = last_year - first_year
    
    if actual_years <= 0 or first_val <= 0:
        return None
    
    return utils.cagr(first_val, last_val, actual_years)


@main.command()
@click.option("--symbol", help="Filter by specific ticker symbol.")
@click.option("--min-yield", type=float, help="Minimum average dividend yield (%).")
@click.option("--max-yield", type=float, help="Maximum average dividend yield (%).")
@click.option("--cagr-min", type=float, help="Minimum overall dividend CAGR (%).")
@click.option("--cagr-3yr-min", type=float, help="Minimum 3Yr CAGR (%).")
@click.option("--cagr-5yr-min", type=float, help="Minimum 5Yr CAGR (%).")
@click.option("--cagr-10yr-min", type=float, help="Minimum 10Yr CAGR (%).")
@click.option("--years-up", type=int, help="Minimum number of years with dividend growth.")
@click.option("--years-stalled", type=int, help="Maximum number of years with stalled dividends.")
@click.option("--years-reduced", type=int, help="Maximum number of years with reduced dividends.")
@click.option("--years-stopped", type=int, help="Maximum number of years with stopped dividends.")
@click.option("--condition", help="Arbitrary Python-style condition (e.g. '(years_stopped + years_stalled) * 2 <= years_up')")
def filter(symbol, min_yield, max_yield, cagr_min, cagr_3yr_min, cagr_5yr_min, cagr_10yr_min, years_up, years_stalled, years_reduced, years_stopped, condition):
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
        for field in ['years-up', 'years-stalled', 'years-reduced', 'years-stopped', 'avg-yield', 'cagr-overall']:
            eval_condition = eval_condition.replace(field, field.replace('-', '_'))

    for sym, group in df.groupby('symbol'):
        ticker_id = group['ticker_id'].iloc[0]
        curr_price = group['current_price'].iloc[0] if 'current_price' in group.columns else None

        # Calculate final share count based on ALL splits in DB (even after last dividend)
        all_splits = splits_by_ticker.get(ticker_id, [])
        final_shares = 1.0
        for s in all_splits:
            final_shares *= (s['numerator'] / s['denominator'])

        # Calculate yield using raw amounts (raw dividend / raw price)
        group['yield'] = group.apply(
            lambda r: utils.dividend_yield(r.get('raw_amount', r['amount']), r['close_price']) if r['close_price'] else 0, 
            axis=1
        )
        avg_yield = group['yield'].mean()
        
        if min_yield is not None and avg_yield < min_yield:
            continue
        if max_yield is not None and avg_yield > max_yield:
            continue
            
        # Yearly totals for CAGR and classifications
        yearly_totals = group.groupby('year')['amount'].sum().sort_index()
        
        # Classification
        up, stalled, reduced, stopped = utils.classify_years(yearly_totals.tolist())
        
        if years_up is not None and up < years_up:
            continue
        if years_stalled is not None and stalled > years_stalled:
            continue
        if years_reduced is not None and reduced > years_reduced:
            continue
        if years_stopped is not None and stopped > years_stopped:
            continue
            
        # CAGRs
        cagr_overall = 0.0
        if len(yearly_totals) >= 2:
            first_val = yearly_totals.iloc[0]
            last_val = yearly_totals.iloc[-1]
            num_years = yearly_totals.index[-1] - yearly_totals.index[0]
            if num_years > 0:
                cagr_overall = utils.cagr(first_val, last_val, num_years)
        
        if cagr_min is not None and cagr_overall < cagr_min:
            continue
            
        c3 = get_cagr_for_years(yearly_totals, 3)
        c5 = get_cagr_for_years(yearly_totals, 5)
        c10 = get_cagr_for_years(yearly_totals, 10)
        c15 = get_cagr_for_years(yearly_totals, 15)
        c20 = get_cagr_for_years(yearly_totals, 20)
        c30 = get_cagr_for_years(yearly_totals, 30)
        
        if cagr_3yr_min is not None and (c3 is None or c3 < cagr_3yr_min):
            continue
        if cagr_5yr_min is not None and (c5 is None or c5 < cagr_5yr_min):
            continue
        if cagr_10yr_min is not None and (c10 is None or c10 < cagr_10yr_min):
            continue

        # Evaluate arbitrary condition if provided
        if eval_condition:
            eval_vars = {
                'up': up, 'years_up': up,
                'stalled': stalled, 'years_stalled': stalled,
                'reduced': reduced, 'years_reduced': reduced,
                'stopped': stopped, 'years_stopped': stopped,
                'yield': avg_yield, 'avg_yield': avg_yield,
                'cagr': cagr_overall, 'cagr_overall': cagr_overall,
                'c3': c3 or 0, 'c5': c5 or 0, 'c10': c10 or 0,
                'c15': c15 or 0, 'c20': c20 or 0, 'c30': c30 or 0,
                'price': curr_price or 0,
                'shares': final_shares
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
            "Avg Yield (%)": round(avg_yield, 2),
            "CAGR Overall (%)": round(cagr_overall, 2),
            "3Yr": round(c3, 2) if c3 is not None else "N/A",
            "5Yr": round(c5, 2) if c5 is not None else "N/A",
            "10Yr": round(c10, 2) if c10 is not None else "N/A",
            "15Yr": round(c15, 2) if c15 is not None else "N/A",
            "20Yr": round(c20, 2) if c20 is not None else "N/A",
            "30Yr": round(c30, 2) if c30 is not None else "N/A",
            "Yrs Up": up,
            "Yrs Stalled": stalled,
            "Yrs Reduced": reduced,
            "Yrs Stopped": stopped
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
        click.echo("  Avg Yield (%)    : Average of (Raw Dividend / Raw Price * 100)")
        click.echo("  CAGR Overall (%) : Growth of total payout from 1 original share")
        click.echo("  3Yr, 5Yr, etc    : Growth rate of total payout for last N years")
        click.echo("  Yrs Up           : Years where total payout was GREATER than prev year")
        click.echo("  Yrs Stalled      : Years where total payout was EQUAL to prev year")
        click.echo("  Yrs Reduced      : Years where total payout was LOWER than prev year")
        click.echo("  Yrs Stopped      : Years where total payout was ZERO")
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
    
    # Yearly summary - use raw_amount for display
    yearly_series = df.groupby('year')['raw_amount'].sum().sort_index()
    yearly = df.groupby('year').agg({
        'raw_amount': 'sum',
        'id': 'count'
    }).rename(columns={'raw_amount': 'amount', 'id': 'count'}).sort_index(ascending=False)
    
    click.echo("\nYearly Totals (Raw - what was actually paid):")
    click.echo(tabulate(yearly, headers="keys", tablefmt="simple"))
    
    # For CAGR and classification, use forward-adjusted to show growth of 1 original share
    yearly_forward = df.groupby('year')['amount'].sum().sort_index()
    
    # Show forward-adjusted yearly totals
    yearly_forward_df = df.groupby('year').agg({
        'amount': 'sum',
        'id': 'count'
    }).rename(columns={'amount': 'forward_amount', 'id': 'count'}).sort_index(ascending=False)
    
    # Merge with raw amounts
    yearly_combined = yearly_forward_df.copy()
    yearly_combined['raw_amount'] = yearly['amount']
    yearly_combined = yearly_combined[['raw_amount', 'forward_amount', 'count']]
    yearly_combined.columns = ['Raw', 'Forward (1 share)', 'Count']
    
    click.echo("\nYearly Totals (Forward-Adjusted - total from 1 original share):")
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
    
    # Yearly changes classification - use forward-adjusted for growth tracking (exclude current year)
    yearly_forward_complete_list = yearly_forward_complete.tolist()
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

if __name__ == "__main__":
    main()
