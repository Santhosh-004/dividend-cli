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
        
        # Calculate 5-year average yield
        five_yr_ago = current_year - 5
        
        five_yr_yield = 0
        yearly_yields = []
        for yr in range(five_yr_ago, current_year):
            yr_divs = group[group['year'] == yr].sort_values('ex_date')
            if len(yr_divs) > 0:
                raw_col = 'raw_amount' if 'raw_amount' in yr_divs.columns else 'amount'
                total_div = yr_divs[raw_col].sum()
                last_div_row = yr_divs.iloc[-1]
                if pd.notna(last_div_row.get('close_price')) and pd.notna(total_div):
                    yearly_yields.append(utils.dividend_yield(float(total_div), float(last_div_row.get('close_price'))))
        if yearly_yields:
            five_yr_yield = sum(yearly_yields) / len(yearly_yields)
        
        if min_yield is not None and last_yield < min_yield:
            continue
        if max_yield is not None and last_yield > max_yield:
            continue
            
        # Yearly totals for CAGR and classifications - exclude current year
        from datetime import datetime
        current_year = datetime.now().year
        yearly_totals = group[group['year'] < current_year].groupby('year')['amount'].sum().sort_index()
        
        # Classification - fill missing years with 0
        min_year = yearly_totals.index.min()
        max_year = yearly_totals.index.max()
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
                'yield': last_yield, 'last_yield': last_yield,
                'yield_5yr': five_yr_yield, 'five_yr_yield': five_yr_yield,
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
            "Yield (%)": round(last_yield, 2),
            "Yield 5Yr (%)": round(five_yr_yield, 2),
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
        click.echo("  Yield (%)        : Last year's total dividend / price on last dividend date * 100")
        click.echo("  Yield 5Yr (%)   : Average yearly yield over last 5 years (total dividend / price on last dividend date)")
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
    
    # Yearly changes classification - fill missing years with 0 for accurate counts
    min_year = yearly_forward_complete.index.min()
    max_year = yearly_forward_complete.index.max()
    full_year_range = pd.Series(0.0, index=range(min_year, max_year + 1))
    full_year_range.update(yearly_forward_complete.astype(float))
    yearly_forward_complete_list = full_year_range.tolist()
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
