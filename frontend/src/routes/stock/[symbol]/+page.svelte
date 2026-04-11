<script lang="ts">
	import { page } from '$app/stores';
	import { ArrowLeft, TrendingUp, TrendingDown, ShieldX, Minus } from 'lucide-svelte';
	import { api } from '$lib/api';
	import type { StatsResponse } from '$lib/types';
	import { fmt, fmtPct, fmtCr, dividendQualityLabel, dividendQualityBadgeClass, cagrColor } from '$lib/utils';
	import DividendBarChart from '$lib/components/DividendBarChart.svelte';
	import CAGRChart from '$lib/components/CAGRChart.svelte';

	let symbol = $derived($page.params.symbol);
	let stats = $state<StatsResponse | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	$effect(() => {
		if (symbol) {
			loading = true;
			error = null;
			stats = null;
			api.getStats(symbol)
				.then(s => { stats = s; })
				.catch(e => { error = e instanceof Error ? e.message : String(e); })
				.finally(() => { loading = false; });
		}
	});

	let totalDividendYears = $derived(
		stats ? stats.years_up + stats.years_stalled + stats.years_reduced + stats.years_stopped : 0
	);

	function streakBarWidth(count: number): string {
		if (!totalDividendYears) return '0%';
		return `${Math.max((count / totalDividendYears) * 100, count > 0 ? 4 : 0)}%`;
	}
</script>

<svelte:head>
	<title>{symbol} — Dividend CLI</title>
</svelte:head>

<div class="animate-enter">
	<!-- Breadcrumb -->
	<button
		onclick={() => history.back()}
		class="group inline-flex items-center gap-2 text-xs text-ink-500 hover:text-cream-300 transition-colors mb-6"
	>
		<ArrowLeft class="h-3.5 w-3.5 transition-transform group-hover:-translate-x-1" />
		<span>Back</span>
	</button>

	{#if loading}
		<!-- Skeleton -->
		<div class="space-y-8">
			<div class="space-y-3">
				<div class="skeleton h-10 w-56"></div>
				<div class="skeleton h-5 w-80"></div>
			</div>
			<div class="grid gap-4 sm:grid-cols-4">
				{#each Array(4) as _}<div class="surface p-5"><div class="skeleton h-12 w-full"></div></div>{/each}
			</div>
			<div class="grid gap-6 lg:grid-cols-2">
				{#each Array(2) as _}<div class="surface p-6"><div class="skeleton h-48 w-full"></div></div>{/each}
			</div>
		</div>
	{:else if error}
		<div class="surface p-8" style="border-color: rgba(239, 83, 80, 0.15);">
			<p class="text-signal-red font-semibold">Failed to load {symbol}</p>
			<p class="mt-2 text-sm text-ink-400">{error}</p>
			<button onclick={() => location.reload()} class="mt-4 btn-outline text-sm">Retry</button>
		</div>
	{:else if stats}
		<!-- ═══ Hero Header ═══ -->
		<header class="mb-10">
			<div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
				<div>
					<div class="flex items-center gap-4">
						<h1 class="heading-serif text-4xl sm:text-5xl text-cream-50">{stats.symbol}</h1>
						{#if stats.dividend_quality}
							<span class="badge {dividendQualityBadgeClass(stats.dividend_quality.rating)} text-xs">
								{dividendQualityLabel(stats.dividend_quality.rating)}
							</span>
						{/if}
					</div>
					{#if stats.name}
						<p class="mt-2 text-[15px] text-ink-400">{stats.name}</p>
					{/if}
				</div>

				<!-- Hero metrics -->
				<div class="flex gap-8 shrink-0">
					{#if stats.current_price != null}
						<div class="text-right">
							<span class="label">Price</span>
							<p class="mt-1 text-2xl font-semibold tabular-nums text-cream-50">₹{fmt(stats.current_price)}</p>
						</div>
					{/if}
					{#if stats.yield_pct != null}
						<div class="text-right">
							<span class="label">Yield</span>
							<p class="mt-1 text-2xl font-semibold tabular-nums text-coral-400">{fmtPct(stats.yield_pct)}</p>
						</div>
					{/if}
					{#if stats.fundamentals_latest?.pe_ratio != null}
						<div class="text-right">
							<span class="label">P/E</span>
							<p class="mt-1 text-2xl font-semibold tabular-nums text-cream-50">{fmt(stats.fundamentals_latest.pe_ratio, 1)}x</p>
						</div>
					{/if}
				</div>
			</div>

			<!-- Coral rule -->
			<div class="mt-6 h-[2px] w-full" style="background: linear-gradient(90deg, var(--color-coral-400) 0%, transparent 50%);"></div>
		</header>

		<!-- ═══ Dividend Track Record Strip ═══ -->
		<section class="mb-10">
			<div class="surface p-5 space-y-5">
				{#if stats.dividend_quality}
					<div class="grid gap-3 sm:grid-cols-5">
						<div class="surface-raised p-3.5 sm:col-span-2">
							<span class="label">Dividend Quality</span>
							<div class="mt-2 flex items-end gap-3">
								<p class="text-3xl font-semibold tabular-nums text-cream-50">{stats.dividend_quality.score.toFixed(0)}</p>
								<span class="badge {dividendQualityBadgeClass(stats.dividend_quality.rating)}">{dividendQualityLabel(stats.dividend_quality.rating)}</span>
							</div>
							<p class="mt-1 text-xs text-ink-500">Stable-growth score across full dividend history</p>
						</div>
						<div class="surface-raised p-3.5 text-center">
							<span class="label">Consistency</span>
							<p class="mt-2 text-xl font-semibold tabular-nums text-mint-400">{stats.dividend_quality.consistency_score.toFixed(0)}</p>
						</div>
						<div class="surface-raised p-3.5 text-center">
							<span class="label">Growth</span>
							<p class="mt-2 text-xl font-semibold tabular-nums text-coral-400">{stats.dividend_quality.growth_score.toFixed(0)}</p>
						</div>
						<div class="surface-raised p-3.5 text-center">
							<span class="label">Trend Fit</span>
							<p class="mt-2 text-xl font-semibold tabular-nums text-cream-200">{stats.dividend_quality.trend_score.toFixed(0)}</p>
						</div>
					</div>
				{/if}

				<div class="flex items-center justify-between mb-4">
					<span class="label">Dividend Track Record</span>
					<span class="text-xs font-mono text-ink-500">{totalDividendYears} years</span>
				</div>

				<!-- Stacked bar visual -->
				<div class="flex h-3 rounded-full overflow-hidden bg-ink-800 mb-4">
					<div class="bg-mint-500 transition-all duration-700" style="width: {streakBarWidth(stats.years_up)}"></div>
					<div class="bg-signal-amber transition-all duration-700" style="width: {streakBarWidth(stats.years_stalled)}"></div>
					<div class="bg-coral-400 transition-all duration-700" style="width: {streakBarWidth(stats.years_reduced)}"></div>
					<div class="bg-signal-red transition-all duration-700" style="width: {streakBarWidth(stats.years_stopped)}"></div>
				</div>

				<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
					<div class="flex items-center gap-2.5">
						<TrendingUp class="h-3.5 w-3.5 text-mint-400" />
						<span class="text-xs text-ink-400">Increased</span>
						<span class="ml-auto text-sm font-mono font-semibold text-mint-400">{stats.years_up}</span>
					</div>
					<div class="flex items-center gap-2.5">
						<Minus class="h-3.5 w-3.5 text-signal-amber" />
						<span class="text-xs text-ink-400">Stalled</span>
						<span class="ml-auto text-sm font-mono font-semibold text-signal-amber">{stats.years_stalled}</span>
					</div>
					<div class="flex items-center gap-2.5">
						<TrendingDown class="h-3.5 w-3.5 text-coral-400" />
						<span class="text-xs text-ink-400">Reduced</span>
						<span class="ml-auto text-sm font-mono font-semibold text-coral-400">{stats.years_reduced}</span>
					</div>
					<div class="flex items-center gap-2.5">
						<ShieldX class="h-3.5 w-3.5 text-signal-red" />
						<span class="text-xs text-ink-400">Stopped</span>
						<span class="ml-auto text-sm font-mono font-semibold text-signal-red">{stats.years_stopped}</span>
					</div>
				</div>
			</div>
		</section>

		<!-- ═══ Charts ═══ -->
		<div class="grid gap-6 lg:grid-cols-2 mb-10">
			<!-- Dividends chart -->
			<section>
				<div class="editorial-rule mb-4">
					<h2 class="heading-serif text-xl text-cream-100">Annual Dividends</h2>
					<p class="text-xs text-ink-500 mt-0.5">₹ per share, split-adjusted</p>
				</div>
				<div class="surface p-5">
					{#if stats.yearly_dividends.length > 0}
						<DividendBarChart data={stats.yearly_dividends} />
					{:else}
						<div class="flex items-center justify-center h-40 text-sm text-ink-500">No dividend data available</div>
					{/if}
				</div>
			</section>

			<!-- CAGR chart -->
			<section>
				<div class="editorial-rule mb-4">
					<h2 class="heading-serif text-xl text-cream-100">Dividend CAGR</h2>
					<p class="text-xs text-ink-500 mt-0.5">Compound annual growth by period</p>
				</div>
				<div class="surface p-5">
					{#if stats.cagr_stats.length > 0}
						<CAGRChart data={stats.cagr_stats} />
					{:else}
						<div class="flex items-center justify-center h-40 text-sm text-ink-500">No CAGR data available</div>
					{/if}
				</div>
			</section>
		</div>

		<!-- ═══ CAGR Summary Grid ═══ -->
		{#if stats.cagr_stats.length > 0}
			<section class="mb-10">
				<div class="editorial-rule mb-4">
					<h2 class="heading-serif text-xl text-cream-100">Growth Rates</h2>
				</div>
				<div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5 stagger">
					{#each stats.cagr_stats as c}
						<div class="surface p-3.5 text-center transition-all hover:border-coral-400/20"
							style={c.cagr != null && c.cagr >= 0 ? 'background: rgba(34, 201, 147, 0.03);' : c.cagr != null ? 'background: rgba(239, 83, 80, 0.03);' : ''}>
							<span class="label">{c.period}</span>
							<p class="mt-1.5 text-lg font-semibold tabular-nums {cagrColor(c.cagr)}">{fmtPct(c.cagr)}</p>
						</div>
					{/each}
				</div>
			</section>
		{/if}

		<!-- ═══ Splits + Recent Payments ═══ -->
		<div class="grid gap-6 lg:grid-cols-2 mb-10">
			<!-- Stock splits timeline -->
			{#if stats.splits.length > 0}
				<section>
					<div class="editorial-rule mb-4">
						<h2 class="heading-serif text-xl text-cream-100">Stock Splits</h2>
					</div>
					<div class="surface p-5">
						<div class="relative pl-6">
							<!-- Timeline line -->
							<div class="absolute left-[7px] top-2 h-[calc(100%-1rem)] w-px bg-gradient-to-b from-coral-400/40 via-ink-700 to-transparent"></div>

							{#each stats.splits as split, i}
								<div class="relative mb-5 last:mb-0">
									<!-- Timeline dot -->
									<div class="absolute -left-[17px] top-1.5 h-[9px] w-[9px] rounded-full border-2 border-ink-900 bg-coral-400"></div>
									<span class="text-xs font-mono text-ink-500">{split.ex_date}</span>
									<p class="text-sm font-semibold text-cream-200 mt-0.5">{split.ratio}</p>
									<p class="text-xs text-ink-500">{split.numerator}:{split.denominator}</p>
								</div>
							{/each}
						</div>
					</div>
				</section>
			{/if}

			<!-- Recent dividend payments -->
			{#if stats.recent_payments.length > 0}
				<section>
					<div class="editorial-rule mb-4">
						<h2 class="heading-serif text-xl text-cream-100">Recent Payments</h2>
					</div>
					<div class="surface overflow-hidden">
						<table class="w-full text-[13px]">
							<thead>
								<tr class="border-b border-ink-700/40 text-[10px] uppercase tracking-wider text-ink-500">
									<th class="px-4 py-2.5 text-left font-semibold">Ex-Date</th>
									<th class="px-4 py-2.5 text-right font-semibold">Raw</th>
									<th class="px-4 py-2.5 text-right font-semibold">Adjusted</th>
									<th class="px-4 py-2.5 text-right font-semibold">Shares</th>
								</tr>
							</thead>
							<tbody>
								{#each stats.recent_payments as p}
									<tr class="border-b border-ink-700/20 row-hover">
										<td class="px-4 py-2.5 font-mono text-xs text-ink-400">{p.ex_date}</td>
										<td class="px-4 py-2.5 text-right tabular-nums text-ink-300">₹{fmt(p.raw_amount)}</td>
										<td class="px-4 py-2.5 text-right tabular-nums font-medium text-cream-100">₹{fmt(p.forward_amount)}</td>
										<td class="px-4 py-2.5 text-right tabular-nums text-ink-500">{p.shares_at_time}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</section>
			{/if}
		</div>

		<!-- ═══ Fundamentals Latest ═══ -->
		{#if stats.fundamentals_latest}
			{@const f = stats.fundamentals_latest}
			<section class="mb-10">
				<div class="editorial-rule mb-4">
					<h2 class="heading-serif text-xl text-cream-100">Fundamentals</h2>
					{#if f.last_updated}
						<p class="text-xs text-ink-500 mt-0.5">Updated: {f.last_updated}</p>
					{/if}
				</div>
				<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2.5 stagger">
					{#each [
						['Div Yield', fmtPct(f.dividend_yield)],
						['Payout Ratio', fmtPct(f.payout_ratio)],
						['P/E Ratio', f.pe_ratio != null ? `${fmt(f.pe_ratio, 1)}x` : '—'],
						['ROE', fmtPct(f.roe)],
						['ROCE', fmtPct(f.roce)],
						['EPS', f.eps != null ? `₹${fmt(f.eps)}` : '—'],
						['Book Value', f.book_value != null ? `₹${fmt(f.book_value)}` : '—'],
						['Face Value', f.face_value != null ? `₹${fmt(f.face_value)}` : '—'],
						['Market Cap', fmtCr(f.market_cap_cr)],
						['Debt / Equity', f.debt_to_equity != null ? fmt(f.debt_to_equity) : '—'],
						['Rev Growth', fmtPct(f.revenue_growth)],
						['Profit Growth', fmtPct(f.profit_growth)],
					] as [label, value]}
						<div class="surface p-3.5 transition-all hover:border-coral-400/20">
							<span class="label">{label}</span>
							<p class="mt-1.5 text-[15px] font-semibold tabular-nums text-cream-100">{value}</p>
						</div>
					{/each}
				</div>
			</section>
		{/if}

		<!-- ═══ Yearly Fundamentals Table ═══ -->
		{#if stats.fundamentals_yearly.length > 0}
			<section class="mb-10">
				<div class="editorial-rule mb-4">
					<h2 class="heading-serif text-xl text-cream-100">Yearly Fundamentals</h2>
				</div>
				<div class="surface overflow-hidden">
					<div class="overflow-x-auto">
						<table class="w-full text-[13px]">
							<thead>
								<tr class="border-b border-ink-700/40 text-[10px] uppercase tracking-wider text-ink-500">
									<th class="px-4 py-2.5 text-left font-semibold">FY</th>
									<th class="px-4 py-2.5 text-right font-semibold">EPS</th>
									<th class="px-4 py-2.5 text-right font-semibold">Div Yield</th>
									<th class="px-4 py-2.5 text-right font-semibold">Payout</th>
									<th class="px-4 py-2.5 text-right font-semibold">ROE</th>
									<th class="px-4 py-2.5 text-right font-semibold">ROCE</th>
									<th class="px-4 py-2.5 text-right font-semibold">D/E</th>
								</tr>
							</thead>
							<tbody>
								{#each stats.fundamentals_yearly.slice().reverse() as fy}
									<tr class="border-b border-ink-700/20 row-hover">
										<td class="px-4 py-2.5 font-medium text-cream-200">{fy.fiscal_year}</td>
										<td class="px-4 py-2.5 text-right tabular-nums text-ink-300">{fy.eps != null ? `₹${fmt(fy.eps)}` : '—'}</td>
										<td class="px-4 py-2.5 text-right tabular-nums text-coral-400">{fmtPct(fy.div_yield)}</td>
										<td class="px-4 py-2.5 text-right tabular-nums text-ink-300">{fmtPct(fy.payout_ratio)}</td>
										<td class="px-4 py-2.5 text-right tabular-nums text-ink-300">{fmtPct(fy.roe)}</td>
										<td class="px-4 py-2.5 text-right tabular-nums text-ink-300">{fmtPct(fy.roce)}</td>
										<td class="px-4 py-2.5 text-right tabular-nums text-ink-300">{fy.debt_to_equity != null ? fmt(fy.debt_to_equity) : '—'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			</section>
		{/if}
	{/if}
</div>
