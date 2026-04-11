# dividend-cli v1.1.0 is out

I just released **dividend-cli v1.1.0**.

It started as a CLI for Indian dividend stock research, but this release is the first one that feels like a real product.

## What's new in v1.1.0

- **Local web UI** via `dividend-cli serve`
  - overview page
  - screener
  - stock detail pages
  - in-browser update flow
- **Dividend Quality Score (0-100)**
  - replaces the old volatility-first framing
  - rewards stable and growing annual dividends
  - penalizes cuts and stoppages much more intelligently
- **Split-aware dividend history** is still the foundation
- **Better screening workflow** with presets + custom filters
- **Cleaner stock pages** with annual dividend charts, CAGR, track record, and quality breakdown

## Why I changed the main metric

The old “volatility” approach was using dispersion / CV-style logic.

That turned out to be misleading for dividend investing.

Some stocks with obviously strong long-term dividend histories were being labeled as only moderate or even volatile, just because their dividends had grown a lot over time.

So in v1.1.0 I replaced that with **Dividend Quality**, which looks at:

- years of increases
- flat years
- cuts
- stoppages
- long-term growth
- trend quality across the full annual history

That gives much more sensible results for names like `HDFCBANK.NS`, `INDIGRID.NS`, `PIDILITIND.NS`, etc.

## A few things I care about in this project

- correct split handling
- local/offline-friendly workflow
- no dependence on generic dividend screeners
- making the output actually useful for Indian income investors

## Example commands

```bash
dividend-cli update
dividend-cli serve
dividend-cli stats HDFCBANK.NS
dividend-cli filter --min-div-quality 75
```

## GitHub

Repo: https://github.com/Santhosh-004/dividend-cli

If you try it, I'd genuinely love feedback on:

- the dividend quality metric
- screener ideas/presets
- stocks/REITs/INVITs where the model still feels wrong
- what you'd want in v1.2.0
