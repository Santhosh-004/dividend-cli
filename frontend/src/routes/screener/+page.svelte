<script lang="ts">
	import { goto } from '$app/navigation';
	import { ChevronUp, ChevronDown, ChevronsUpDown, Download, X, Search, SlidersHorizontal, Loader2 } from 'lucide-svelte';
	import { api } from '$lib/api';
	import type { FilterResult, FilterParams } from '$lib/types';
	import { fmt, fmtPct, cagrColor } from '$lib/utils';

	let params = $state<FilterParams>({
		min_yield: undefined, max_yield: undefined,
		div_growth_min: undefined, div_3yr_min: undefined,
		div_5yr_min: undefined, div_10yr_min: undefined,
		years_up: undefined, years_stalled: undefined,
		years_reduced: undefined, years_stopped: undefined,
		min_payout: undefined, max_payout: undefined,
		min_roe: undefined, min_roce: undefined, min_div_quality: undefined,
		condition: undefined, limit: 200,
	});

	let results = $state<FilterResult[]>([]);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let hasSearched = $state(false);
	let filtersExpanded = $state(false);

	type SortKey = keyof FilterResult;
	let sortKey = $state<SortKey>('yield_pct');
	let sortAsc = $state(false);

	let page = $state(0);
	const pageSize = 50;
	const defaultLimit = 200;
	const emptyParams: FilterParams = {
		min_yield: undefined, max_yield: undefined,
		div_growth_min: undefined, div_3yr_min: undefined,
		div_5yr_min: undefined, div_10yr_min: undefined,
		years_up: undefined, years_stalled: undefined,
		years_reduced: undefined, years_stopped: undefined,
		min_payout: undefined, max_payout: undefined,
		min_roe: undefined, min_roce: undefined, min_div_quality: undefined,
		condition: undefined, limit: defaultLimit,
	};

	let sorted = $derived(
		[...results].sort((a, b) => {
			const av = a[sortKey] ?? (sortAsc ? Infinity : -Infinity);
			const bv = b[sortKey] ?? (sortAsc ? Infinity : -Infinity);
			if (av < bv) return sortAsc ? -1 : 1;
			if (av > bv) return sortAsc ? 1 : -1;
			return 0;
		})
	);

	let paged = $derived(sorted.slice(page * pageSize, (page + 1) * pageSize));
	let totalPages = $derived(Math.ceil(sorted.length / pageSize));

	function setSort(key: SortKey) {
		if (sortKey === key) { sortAsc = !sortAsc; }
		else { sortKey = key; sortAsc = false; }
	}

	function normalizeLimit(value: number | undefined): number {
		if (!Number.isFinite(value ?? NaN)) return 200;
		const v = Math.round(Number(value));
		return Math.max(10, Math.min(2000, v));
	}

	type Preset = {
		label: string;
		filters: FilterParams;
	};

	const presets: Preset[] = [
		{
			label: 'High Yield',
			filters: { ...emptyParams, min_yield: 4, years_stopped: 1, min_div_quality: 45 },
		},
		{
			label: 'Growers',
			filters: {
				...emptyParams,
				div_growth_min: 10,
				div_3yr_min: 8,
				years_up: 5,
				years_reduced: 1,
				years_stopped: 0,
				min_div_quality: 60,
			},
		},
		{
			label: 'Quality',
			filters: {
				...emptyParams,
				min_div_quality: 75,
				min_roe: 15,
				max_payout: 70,
				years_reduced: 1,
				years_stopped: 0,
			},
		},
		{
			label: 'Conservative',
			filters: {
				...emptyParams,
				min_yield: 1,
				max_payout: 60,
				years_reduced: 0,
				years_stopped: 0,
				min_div_quality: 70,
			},
		},
	];

	function paramsEqual(a: FilterParams, b: FilterParams): boolean {
		const keys = Object.keys(emptyParams) as (keyof FilterParams)[];
		return keys.every((key) => (a[key] ?? undefined) === (b[key] ?? undefined));
	}

	let activePresetLabel = $derived(
		presets.find((preset) => paramsEqual(params, preset.filters))?.label ?? null
	);

	async function applyPreset(preset: Preset) {
		params = { ...preset.filters };
		filtersExpanded = true;
		await runFilter();
	}

	async function runFilter() {
		loading = true;
		error = null;
		page = 0;
		try {
			results = await api.filterStocks({ ...params, limit: normalizeLimit(params.limit) });
			params.limit = normalizeLimit(params.limit);
			hasSearched = true;
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	}

	function resetFilters() {
		params = { ...emptyParams };
	}

	function exportCsv() {
		const headers: (keyof FilterResult)[] = [
			'symbol', 'name', 'price', 'yield_pct', 'cagr_overall', 'cagr_3yr', 'cagr_5yr',
			'cagr_10yr', 'years_up', 'years_stalled', 'years_reduced', 'years_stopped',
			'dividend_quality_score', 'dividend_quality_rating', 'payout_pct', 'roe_pct', 'roce_pct', 'div_cv',
		];
		const csv = [
			headers.join(','),
			...sorted.map(r =>
				headers.map(h => {
					const v = r[h];
					if (v == null) return '';
					if (typeof v === 'string' && v.includes(',')) return `"${v}"`;
					return String(v);
				}).join(',')
			),
		].join('\n');
		const blob = new Blob([csv], { type: 'text/csv' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = 'dividend-screener.csv';
		a.click();
		URL.revokeObjectURL(url);
	}

	type Col = { key: SortKey; label: string; align: 'left' | 'right' };
	const columns: Col[] = [
		{ key: 'symbol', label: 'Symbol', align: 'left' },
		{ key: 'price', label: 'Price', align: 'right' },
		{ key: 'yield_pct', label: 'Yield', align: 'right' },
		{ key: 'dividend_quality_score', label: 'Quality', align: 'right' },
		{ key: 'cagr_overall', label: 'CAGR', align: 'right' },
		{ key: 'cagr_3yr', label: '3yr', align: 'right' },
		{ key: 'cagr_5yr', label: '5yr', align: 'right' },
		{ key: 'cagr_10yr', label: '10yr', align: 'right' },
		{ key: 'years_up', label: 'Up', align: 'right' },
		{ key: 'years_reduced', label: 'Red', align: 'right' },
		{ key: 'payout_pct', label: 'Payout', align: 'right' },
		{ key: 'roe_pct', label: 'ROE', align: 'right' },
		{ key: 'roce_pct', label: 'ROCE', align: 'right' },
	];

	// Check if any filters are active
	let hasActiveFilters = $derived(
		params.min_yield != null || params.max_yield != null ||
		params.div_growth_min != null || params.div_3yr_min != null ||
		params.div_5yr_min != null || params.div_10yr_min != null ||
		params.years_up != null || params.years_stalled != null ||
		params.years_reduced != null || params.years_stopped != null ||
		params.min_payout != null || params.max_payout != null ||
		params.min_roe != null || params.min_roce != null || params.min_div_quality != null ||
		(params.condition != null && params.condition !== '')
	);
</script>

<svelte:head>
	<title>Screener — Dividend CLI</title>
</svelte:head>

<div class="animate-enter">
	<!-- Header -->
	<div class="mb-8">
		<div class="flex flex-wrap items-end justify-between gap-4">
			<div>
				<h1 class="heading-serif text-3xl sm:text-4xl text-cream-50">Screener</h1>
				<p class="mt-1 text-sm text-ink-400">
					{#if hasSearched}
						{results.length} stock{results.length !== 1 ? 's' : ''} matched
					{:else}
						Filter and discover dividend stocks
					{/if}
				</p>
			</div>
			<div class="flex gap-2">
				{#if results.length > 0}
					<button onclick={exportCsv} class="btn-outline text-xs py-1.5 px-3">
						<Download class="h-3.5 w-3.5" />
						CSV
					</button>
				{/if}
			</div>
		</div>
		<div class="mt-4 h-[2px] w-full" style="background: linear-gradient(90deg, var(--color-coral-400) 0%, transparent 40%);"></div>
	</div>

	<!-- Quick presets + filter controls -->
	<div class="mb-6">
		<div class="flex flex-wrap items-center gap-2">
			<!-- Presets -->
			{#each presets as preset}
				<button
					onclick={() => applyPreset(preset)}
					class="rounded-md border px-3 py-1.5 text-xs font-medium transition-all {activePresetLabel === preset.label ? 'border-coral-400/40 bg-coral-500/10 text-coral-300 shadow-[inset_0_0_0_1px_rgba(255,123,97,0.08)]' : 'border-ink-700/40 bg-ink-900/50 text-ink-300 hover:border-coral-400/30 hover:text-coral-400 hover:bg-coral-500/5'}"
				>
					{preset.label}
				</button>
			{/each}

			<span class="text-ink-700 mx-1">|</span>

			<!-- Toggle advanced filters -->
			<button
				onclick={() => (filtersExpanded = !filtersExpanded)}
				class="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors
				{filtersExpanded ? 'text-coral-400 bg-coral-500/8' : 'text-ink-400 hover:text-cream-300'}"
			>
				<SlidersHorizontal class="h-3.5 w-3.5" />
				Filters
				{#if hasActiveFilters}
					<span class="h-1.5 w-1.5 rounded-full bg-coral-400"></span>
				{/if}
			</button>

			{#if hasActiveFilters}
				<button onclick={() => { resetFilters(); }} class="text-xs text-ink-500 hover:text-signal-red transition-colors">
					<X class="h-3.5 w-3.5 inline" /> Clear
				</button>
			{/if}
		</div>

		<!-- Expanded filter panel -->
		{#if filtersExpanded}
			<div class="mt-4 surface p-5 animate-enter">
				<form onsubmit={(e) => { e.preventDefault(); runFilter(); }} class="space-y-5">
					<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
						<!-- Yield range -->
						<div>
							<span class="label block mb-1.5">Min Yield %</span>
							<input type="number" step="0.1" bind:value={params.min_yield} placeholder="0" class="input-field text-xs" />
						</div>
						<div>
							<span class="label block mb-1.5">Max Yield %</span>
							<input type="number" step="0.1" bind:value={params.max_yield} placeholder="any" class="input-field text-xs" />
						</div>

						<!-- CAGR -->
						<div>
							<span class="label block mb-1.5">Min CAGR %</span>
							<input type="number" step="0.1" bind:value={params.div_growth_min} placeholder="any" class="input-field text-xs" />
						</div>
						<div>
							<span class="label block mb-1.5">Min 3yr CAGR</span>
							<input type="number" step="0.1" bind:value={params.div_3yr_min} placeholder="any" class="input-field text-xs" />
						</div>
						<div>
							<span class="label block mb-1.5">Min 5yr CAGR</span>
							<input type="number" step="0.1" bind:value={params.div_5yr_min} placeholder="any" class="input-field text-xs" />
						</div>
						<div>
							<span class="label block mb-1.5">Min 10yr CAGR</span>
							<input type="number" step="0.1" bind:value={params.div_10yr_min} placeholder="any" class="input-field text-xs" />
						</div>

						<!-- History -->
						<div>
							<span class="label block mb-1.5">Min Yrs Up</span>
							<input type="number" step="1" min="0" bind:value={params.years_up} placeholder="any" class="input-field text-xs" />
						</div>
						<div>
							<span class="label block mb-1.5">Max Stalled</span>
							<input type="number" step="1" min="0" bind:value={params.years_stalled} placeholder="any" class="input-field text-xs" />
						</div>
						<div>
							<span class="label block mb-1.5">Max Reduced</span>
							<input type="number" step="1" min="0" bind:value={params.years_reduced} placeholder="any" class="input-field text-xs" />
						</div>
						<div>
							<span class="label block mb-1.5">Max Stopped</span>
							<input type="number" step="1" min="0" bind:value={params.years_stopped} placeholder="any" class="input-field text-xs" />
						</div>

						<!-- Payout -->
						<div>
							<span class="label block mb-1.5">Min Payout %</span>
							<input type="number" step="1" bind:value={params.min_payout} placeholder="0" class="input-field text-xs" />
						</div>
						<div>
							<span class="label block mb-1.5">Max Payout %</span>
							<input type="number" step="1" bind:value={params.max_payout} placeholder="any" class="input-field text-xs" />
						</div>

						<!-- Returns -->
						<div>
							<span class="label block mb-1.5">Min ROE %</span>
							<input type="number" step="1" bind:value={params.min_roe} placeholder="any" class="input-field text-xs" />
						</div>
						<div>
							<span class="label block mb-1.5">Min ROCE %</span>
							<input type="number" step="1" bind:value={params.min_roce} placeholder="any" class="input-field text-xs" />
						</div>

						<div>
							<span class="label block mb-1.5">Min Quality</span>
							<input type="number" step="1" min="0" max="100" bind:value={params.min_div_quality} placeholder="any" class="input-field text-xs" />
						</div>

						<!-- Expression -->
						<div class="col-span-2 sm:col-span-3 lg:col-span-2">
							<span class="label block mb-1.5">Expression</span>
							<input type="text" bind:value={params.condition} placeholder='yield > 5 and c3 > 10' class="input-field text-xs font-mono" />
						</div>
					</div>

					<div class="flex items-center gap-3 pt-1">
						<button type="submit" class="btn-coral text-xs py-2 px-5" disabled={loading}>
							{loading ? 'Scanning...' : 'Run Screener'}
						</button>
						<div class="flex items-center gap-2 text-xs text-ink-500">
							<span class="label">Limit</span>
							<input type="number" step="1" min="10" max="2000" bind:value={params.limit} onchange={() => { params.limit = normalizeLimit(params.limit); }} class="input-field w-20 text-xs" />
						</div>
					</div>
				</form>
			</div>
		{/if}
	</div>

	<!-- Results -->
	{#if error}
		<div class="surface p-5 text-sm text-signal-red" style="border-color: rgba(239, 83, 80, 0.15);">{error}</div>
	{:else if loading}
		<div class="flex h-64 items-center justify-center">
			<div class="flex flex-col items-center gap-3">
				<Loader2 class="h-6 w-6 animate-spin text-coral-400" />
				<p class="text-sm text-ink-400">Scanning stocks...</p>
			</div>
		</div>
	{:else if !hasSearched}
		<div class="flex h-56 flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-ink-700/40">
			<Search class="h-6 w-6 text-ink-600" />
			<div class="text-center">
				<p class="text-sm font-medium text-ink-400">Ready to screen</p>
				<p class="mt-1 text-xs text-ink-500">Pick a preset above or expand filters</p>
			</div>
		</div>
	{:else if results.length === 0}
		<div class="flex h-48 flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-ink-700/40">
			<p class="text-sm text-ink-400">No stocks matched. Try relaxing your filters.</p>
		</div>
	{:else}
		<!-- Data table -->
		<div class="overflow-x-auto surface">
			<table class="w-full text-[13px]">
				<thead>
					<tr class="border-b border-ink-700/40 text-[10px] uppercase tracking-wider text-ink-500">
						{#each columns as col}
							<th
								class="cursor-pointer select-none px-3 py-2.5 font-semibold transition-colors hover:text-cream-300 {col.align === 'right' ? 'text-right' : 'text-left'} {sortKey === col.key ? 'text-coral-400' : ''}"
								onclick={() => setSort(col.key)}
							>
								<span class="inline-flex items-center gap-0.5">
									{col.label}
									{#if sortKey === col.key}
										{#if sortAsc}<ChevronUp class="h-3 w-3" />{:else}<ChevronDown class="h-3 w-3" />{/if}
									{:else}
										<ChevronsUpDown class="h-2.5 w-2.5 opacity-20" />
									{/if}
								</span>
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each paged as row}
						<tr
							class="cursor-pointer border-b border-ink-700/15 row-hover group"
							onclick={() => goto(`/stock/${encodeURIComponent(row.symbol)}`)}
						>
							<td class="px-3 py-2.5">
								<div class="flex items-center gap-2.5">
									<div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-ink-800 font-mono text-[10px] font-bold text-ink-400 group-hover:text-coral-400 group-hover:bg-coral-500/8 transition-colors">
										{row.symbol.substring(0, 2)}
									</div>
									<div class="min-w-0">
										<span class="font-medium text-cream-200 group-hover:text-cream-50 transition-colors">{row.symbol}</span>
										{#if row.name}
											<p class="truncate text-[11px] text-ink-500 max-w-[140px]">{row.name}</p>
										{/if}
									</div>
								</div>
							</td>
							<td class="px-3 py-2.5 text-right tabular-nums text-cream-300">{row.price != null ? `₹${fmt(row.price)}` : '—'}</td>
							<td class="px-3 py-2.5 text-right">
								<span class="badge badge-mint tabular-nums">{fmtPct(row.yield_pct)}</span>
							</td>
							<td class="px-3 py-2.5 text-right tabular-nums text-cream-200">{row.dividend_quality_score != null ? row.dividend_quality_score.toFixed(0) : '—'}</td>
							<td class="px-3 py-2.5 text-right tabular-nums {cagrColor(row.cagr_overall)}">{fmtPct(row.cagr_overall)}</td>
							<td class="px-3 py-2.5 text-right tabular-nums {cagrColor(row.cagr_3yr)}">{fmtPct(row.cagr_3yr)}</td>
							<td class="px-3 py-2.5 text-right tabular-nums {cagrColor(row.cagr_5yr)}">{fmtPct(row.cagr_5yr)}</td>
							<td class="px-3 py-2.5 text-right tabular-nums {cagrColor(row.cagr_10yr)}">{fmtPct(row.cagr_10yr)}</td>
							<td class="px-3 py-2.5 text-right tabular-nums text-cream-300">{row.years_up}</td>
							<td class="px-3 py-2.5 text-right tabular-nums {row.years_reduced > 0 ? 'text-signal-red' : 'text-ink-500'}">{row.years_reduced}</td>
							<td class="px-3 py-2.5 text-right tabular-nums text-ink-300">{fmtPct(row.payout_pct)}</td>
							<td class="px-3 py-2.5 text-right tabular-nums text-ink-300">{fmtPct(row.roe_pct)}</td>
							<td class="px-3 py-2.5 text-right tabular-nums text-ink-300">{fmtPct(row.roce_pct)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<!-- Pagination -->
		{#if totalPages > 1}
			<div class="mt-4 flex items-center justify-between text-xs text-ink-400">
				<span class="tabular-nums">
					{page * pageSize + 1}–{Math.min((page + 1) * pageSize, sorted.length)} of {sorted.length}
				</span>
				<div class="flex gap-1.5">
					<button
						onclick={() => page = Math.max(0, page - 1)}
						disabled={page === 0}
						class="btn-outline text-xs py-1 px-3 disabled:opacity-30"
					>
						Prev
					</button>
					<button
						onclick={() => page = Math.min(totalPages - 1, page + 1)}
						disabled={page >= totalPages - 1}
						class="btn-outline text-xs py-1 px-3 disabled:opacity-30"
					>
						Next
					</button>
				</div>
			</div>
		{/if}
	{/if}
</div>
