<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ArrowRight, ArrowUpRight, TrendingUp, Database, BarChart3, ShieldCheck, X } from 'lucide-svelte';
	import { api } from '$lib/api';
	import type { DBSummary, TopStocksResponse } from '$lib/types';
	import { fmt, fmtPct, relativeTime, dividendQualityLabel, dividendQualityBadgeClass } from '$lib/utils';

	let summary = $state<DBSummary | null>(null);
	let topStocks = $state<TopStocksResponse | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let dismissNoDataModal = $state(false);

	const showNoDataModal = $derived(
		!loading &&
			!error &&
			!dismissNoDataModal &&
			(summary?.tickers_with_dividends ?? 0) === 0,
	);

	onMount(async () => {
		try {
			[summary, topStocks] = await Promise.all([api.getSummary(), api.getTop(10)]);
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>Overview — Dividend CLI</title>
</svelte:head>

{#if loading}
	<div class="space-y-8 animate-enter">
		<!-- Skeleton: hero -->
		<div class="space-y-3">
			<div class="skeleton h-10 w-72"></div>
			<div class="skeleton h-5 w-96"></div>
		</div>
		<!-- Skeleton: stat cards -->
		<div class="grid gap-4 sm:grid-cols-3">
			{#each Array(3) as _}
				<div class="surface p-5">
					<div class="skeleton h-3 w-20 mb-3"></div>
					<div class="skeleton h-8 w-24"></div>
				</div>
			{/each}
		</div>
		<!-- Skeleton: tables -->
		<div class="grid gap-8 lg:grid-cols-2">
			{#each Array(2) as _}
				<div class="surface p-6">
					<div class="skeleton h-5 w-48 mb-6"></div>
					{#each Array(5) as __}
						<div class="skeleton h-10 w-full mb-2"></div>
					{/each}
				</div>
			{/each}
		</div>
	</div>
{:else if error}
	<div class="animate-enter surface p-8" style="border-color: rgba(239, 83, 80, 0.15);">
		<p class="text-signal-red font-semibold">Failed to load dashboard</p>
		<p class="mt-1 text-sm text-ink-400">{error}</p>
		<button
			onclick={() => location.reload()}
			class="mt-4 btn-outline text-sm"
		>
			Retry
		</button>
	</div>
{:else}
	<div class="animate-enter">
		{#if showNoDataModal}
			<div class="fixed inset-0 z-[90] flex items-center justify-center px-4">
				<div class="absolute inset-0 bg-ink-950/82 backdrop-blur-sm animate-fade-in"></div>
				<div class="surface-raised relative z-10 w-full max-w-xl p-6 sm:p-7 animate-enter-scale">
					<button
						type="button"
						onclick={() => (dismissNoDataModal = true)}
						class="absolute right-4 top-4 rounded-md p-1.5 text-ink-500 transition-colors hover:bg-ink-800/60 hover:text-cream-200"
						aria-label="Dismiss setup message"
					>
						<X class="h-4 w-4" />
					</button>

					<div class="editorial-rule pr-8">
						<p class="label text-coral-400">First run</p>
						<h2 class="mt-3 heading-serif text-3xl text-cream-50">Load data before using the dashboard</h2>
						<p class="mt-3 max-w-lg text-sm leading-relaxed text-ink-400">
							This install starts with an empty database. Run your first update to download tickers,
							dividend history, and fundamentals before screening or comparing stocks.
						</p>
					</div>

					<div class="mt-5 grid gap-3 sm:grid-cols-3 text-xs text-ink-400 stagger">
						<div class="surface p-3.5">
							<p class="label">1</p>
							<p class="mt-1 text-cream-200">Open Update</p>
						</div>
						<div class="surface p-3.5">
							<p class="label">2</p>
							<p class="mt-1 text-cream-200">Run Quick or Full Update</p>
						</div>
						<div class="surface p-3.5">
							<p class="label">3</p>
							<p class="mt-1 text-cream-200">Come back to explore results</p>
						</div>
					</div>

					<div class="mt-6 flex flex-wrap gap-3">
						<button type="button" class="btn-coral" onclick={() => goto('/update')}>
							Run first update
							<ArrowRight class="h-4 w-4" />
						</button>
						<button type="button" class="btn-outline" onclick={() => (dismissNoDataModal = true)}>
							Dismiss
						</button>
					</div>
				</div>
			</div>
		{/if}

		<!-- Editorial hero -->
		<div class="mb-10">
			<div class="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
				<div>
					<h1 class="heading-serif text-4xl sm:text-5xl text-cream-50 leading-tight">
						Dividend<br class="sm:hidden" /> Overview
					</h1>
					<p class="mt-3 text-[15px] text-ink-400 max-w-md leading-relaxed">
						Indian equity dividend analytics. Track yields, growth rates, and dividend quality across your universe of stocks.
					</p>
				</div>
				<div class="flex gap-3 shrink-0">
					<a href="/screener" class="btn-coral group text-sm">
						<BarChart3 class="h-4 w-4" />
						Screener
						<ArrowRight class="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
					</a>
				</div>
			</div>

			<!-- Coral accent rule -->
			<div class="mt-6 h-[2px] w-full" style="background: linear-gradient(90deg, var(--color-coral-400) 0%, transparent 60%);"></div>
		</div>

		<!-- Stats strip -->
		<div class="grid gap-4 sm:grid-cols-3 mb-12 stagger">
			<!-- Total tickers -->
			<div class="surface-interactive p-5 group">
				<div class="flex items-center justify-between mb-3">
					<span class="label">Universe</span>
					<Database class="h-3.5 w-3.5 text-ink-500 group-hover:text-coral-400 transition-colors" />
				</div>
				<p class="text-3xl font-semibold tabular-nums text-cream-50">{summary?.total_tickers?.toLocaleString() ?? '—'}</p>
				<p class="mt-1.5 text-xs text-ink-500">NSE listed equities tracked</p>
			</div>

			<!-- With dividends -->
			<div class="surface-interactive p-5 group">
				<div class="flex items-center justify-between mb-3">
					<span class="label">Dividend Payers</span>
					<TrendingUp class="h-3.5 w-3.5 text-ink-500 group-hover:text-mint-400 transition-colors" />
				</div>
				<div class="flex items-baseline gap-2">
					<p class="text-3xl font-semibold tabular-nums text-cream-50">{summary?.tickers_with_dividends?.toLocaleString() ?? '—'}</p>
					{#if summary && summary.total_tickers > 0}
						<span class="text-sm font-mono text-mint-400">{((summary.tickers_with_dividends / summary.total_tickers) * 100).toFixed(0)}%</span>
					{/if}
				</div>
				{#if summary && summary.total_tickers > 0}
					<div class="mt-3 h-1 rounded-full bg-ink-800 overflow-hidden">
						<div
							class="h-full rounded-full bg-mint-500 transition-all duration-700"
							style="width: {((summary.tickers_with_dividends / summary.total_tickers) * 100).toFixed(1)}%"
						></div>
					</div>
				{/if}
			</div>

			<!-- Last updated -->
			<div class="surface-interactive p-5 group">
				<div class="flex items-center justify-between mb-3">
					<span class="label">Last Sync</span>
				</div>
				<p class="text-2xl font-semibold text-cream-50">{relativeTime(summary?.last_updated ?? null)}</p>
				{#if summary?.last_updated}
					<p class="mt-1.5 text-xs text-ink-500">
						{new Date(summary.last_updated).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
					</p>
				{:else}
					<a href="/update" class="mt-1.5 inline-flex items-center gap-1 text-xs text-coral-400 hover:text-coral-300 transition-colors">
						Run first update <ArrowRight class="h-3 w-3" />
					</a>
				{/if}
			</div>
		</div>

		<!-- Leaderboard section -->
		<div class="grid gap-8 lg:grid-cols-2">
			<!-- Top by Yield -->
			<section class="min-w-0">
				<div class="editorial-rule mb-5">
					<h2 class="heading-serif text-2xl text-cream-100">Top Yields</h2>
					<p class="mt-1 text-xs text-ink-500">Highest dividend yield in database</p>
				</div>

				<div class="surface overflow-hidden">
					{#if topStocks?.by_yield?.length}
						<table class="w-full text-[13px]">
							<thead>
								<tr class="border-b border-ink-700/40 text-[10px] uppercase tracking-wider text-ink-500">
									<th class="px-4 py-2.5 text-left font-semibold w-8">#</th>
									<th class="px-4 py-2.5 text-left font-semibold">Stock</th>
									<th class="px-4 py-2.5 text-right font-semibold">Yield</th>
									<th class="px-4 py-2.5 text-right font-semibold hidden sm:table-cell">Quality</th>
								</tr>
							</thead>
							<tbody>
								{#each topStocks.by_yield as stock, i}
									<tr
										class="cursor-pointer border-b border-ink-700/20 row-hover group"
										onclick={() => goto(`/stock/${encodeURIComponent(stock.symbol)}`)}
									>
										<td class="px-4 py-3 font-mono text-xs text-ink-500">{i + 1}</td>
										<td class="px-4 py-3">
											<div class="flex items-center gap-3">
												<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-ink-800 font-mono text-[10px] font-bold text-ink-400 group-hover:text-coral-400 group-hover:bg-coral-500/8 transition-colors">
													{stock.symbol.substring(0, 2)}
												</div>
												<div class="min-w-0">
													<span class="font-medium text-cream-200 group-hover:text-cream-50 transition-colors">{stock.symbol}</span>
													{#if stock.name}
														<p class="truncate text-[11px] text-ink-500 max-w-[130px] 2xl:max-w-[110px]">{stock.name}</p>
													{/if}
												</div>
											</div>
										</td>
										<td class="px-4 py-3 text-right">
											<span class="badge badge-mint tabular-nums">{fmtPct(stock.yield_pct)}</span>
										</td>
										<td class="px-4 py-3 text-right hidden sm:table-cell">
										<span class="badge {dividendQualityBadgeClass(stock.dividend_quality_rating)}">{dividendQualityLabel(stock.dividend_quality_rating)}</span>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					{:else}
						<div class="flex flex-col items-center justify-center py-12 gap-3 text-ink-500">
							<Database class="h-6 w-6 opacity-40" />
							<p class="text-sm">No data yet</p>
							<a href="/update" class="text-xs text-coral-400 hover:text-coral-300">Run an update <ArrowRight class="inline h-3 w-3" /></a>
						</div>
					{/if}
				</div>

				{#if topStocks?.by_yield?.length}
					<a href="/screener" class="inline-flex items-center gap-1.5 mt-3 text-xs text-ink-400 hover:text-coral-400 transition-colors group">
						View all in Screener <ArrowUpRight class="h-3 w-3 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
					</a>
				{/if}
			</section>

			<!-- Top by Quality -->
			<section class="min-w-0">
				<div class="editorial-rule mb-5">
					<h2 class="heading-serif text-2xl text-cream-100">Best Quality</h2>
					<p class="mt-1 text-xs text-ink-500">Highest dividend quality score</p>
				</div>

				<div class="surface overflow-hidden">
					{#if topStocks?.by_quality?.length}
						<table class="w-full text-[13px]">
							<thead>
								<tr class="border-b border-ink-700/40 text-[10px] uppercase tracking-wider text-ink-500">
									<th class="px-4 py-2.5 text-left font-semibold w-8">#</th>
									<th class="px-4 py-2.5 text-left font-semibold">Stock</th>
									<th class="px-4 py-2.5 text-right font-semibold">Score</th>
									<th class="px-4 py-2.5 text-right font-semibold hidden sm:table-cell">Band</th>
								</tr>
							</thead>
							<tbody>
								{#each topStocks.by_quality as stock, i}
									<tr
										class="cursor-pointer border-b border-ink-700/20 row-hover group"
										onclick={() => goto(`/stock/${encodeURIComponent(stock.symbol)}`)}
									>
										<td class="px-4 py-3 font-mono text-xs text-ink-500">{i + 1}</td>
										<td class="px-4 py-3">
											<div class="flex items-center gap-3">
												<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-ink-800 font-mono text-[10px] font-bold text-ink-400 group-hover:text-coral-400 group-hover:bg-coral-500/8 transition-colors">
													{stock.symbol.substring(0, 2)}
												</div>
												<div class="min-w-0">
													<span class="font-medium text-cream-200 group-hover:text-cream-50 transition-colors">{stock.symbol}</span>
													{#if stock.name}
														<p class="truncate text-[11px] text-ink-500 max-w-[130px] 2xl:max-w-[110px]">{stock.name}</p>
													{/if}
												</div>
											</div>
										</td>
										<td class="px-4 py-3 text-right">
											<span class="badge badge-mint tabular-nums">{stock.dividend_quality_score != null ? stock.dividend_quality_score.toFixed(0) : '—'}</span>
										</td>
										<td class="px-4 py-3 text-right hidden sm:table-cell">
											<span class="badge {dividendQualityBadgeClass(stock.dividend_quality_rating)}">{dividendQualityLabel(stock.dividend_quality_rating)}</span>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					{:else}
						<div class="flex flex-col items-center justify-center py-12 gap-3 text-ink-500">
							<ShieldCheck class="h-6 w-6 opacity-40" />
							<p class="text-sm">No data yet</p>
						</div>
					{/if}
				</div>

				{#if topStocks?.by_quality?.length}
					<a href="/screener" class="inline-flex items-center gap-1.5 mt-3 text-xs text-ink-400 hover:text-coral-400 transition-colors group">
						View all in Screener <ArrowUpRight class="h-3 w-3 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
					</a>
				{/if}
			</section>

			<!-- Top by CAGR -->
		</div>
	</div>
{/if}
