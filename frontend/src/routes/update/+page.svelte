<script lang="ts">
	import { RefreshCw, Terminal, CheckCircle, XCircle, Play, Square, CloudDownload, Zap } from 'lucide-svelte';
	import { api } from '$lib/api';
	import type { UpdateRequest } from '$lib/types';

	let req = $state<UpdateRequest>({
		symbol: '',
		force: false,
		max_age: 7,
		limit: undefined,
	});

	type JobStatus = 'idle' | 'running' | 'done' | 'error';
	let status = $state<JobStatus>('idle');
	let logs = $state<string[]>([]);
	let progress = $state(0);
	let jobId = $state<string | null>(null);
	let errorMsg = $state<string | null>(null);
	let es = $state<EventSource | null>(null);

	let logContainer = $state<HTMLDivElement | undefined>(undefined);

	function scrollToBottom() {
		if (logContainer) logContainer.scrollTop = logContainer.scrollHeight;
	}

	async function startUpdate() {
		if (status === 'running') return;

		logs = [];
		progress = 0;
		errorMsg = null;
		status = 'running';

		const payload: UpdateRequest = {
			force: req.force,
			max_age: req.max_age,
		};
		if (req.symbol?.trim()) payload.symbol = req.symbol.trim().toUpperCase();
		if (req.limit) payload.limit = req.limit;

		try {
			const res = await api.startUpdate(payload);
			jobId = res.job_id;
		} catch (e) {
			errorMsg = e instanceof Error ? e.message : String(e);
			status = 'error';
			return;
		}

		es = api.updateProgress(jobId!);

		es.onmessage = (evt) => {
			try {
				const data = JSON.parse(evt.data);
				if (data.log) {
					logs = [...logs, data.log];
					setTimeout(scrollToBottom, 20);
				}
				if (data.progress != null) progress = data.progress;
				if (data.done) {
					status = data.error ? 'error' : 'done';
					if (data.error) errorMsg = data.error;
					es?.close();
					es = null;
				}
			} catch { /* ignore parse errors */ }
		};

		es.onerror = () => {
			if (status === 'running') {
				status = logs.length > 0 ? 'done' : 'error';
				if (status === 'error') errorMsg = 'Connection to server lost.';
			}
			es?.close();
			es = null;
		};
	}

	function stopUpdate() {
		es?.close();
		es = null;
		if (status === 'running') status = 'idle';
	}

	function statusIcon(s: JobStatus) {
		if (s === 'running') return RefreshCw;
		if (s === 'done') return CheckCircle;
		if (s === 'error') return XCircle;
		return Terminal;
	}

	function statusText(s: JobStatus) {
		if (s === 'running') return 'Running';
		if (s === 'done') return 'Complete';
		if (s === 'error') return 'Failed';
		return 'Idle';
	}
</script>

<svelte:head>
	<title>Update — Dividend CLI</title>
</svelte:head>

<div class="mx-auto max-w-3xl animate-enter">
	<!-- Header -->
	<div class="mb-8">
		<h1 class="heading-serif text-3xl sm:text-4xl text-cream-50">Update Data</h1>
		<p class="mt-2 text-[15px] text-ink-400 max-w-lg leading-relaxed">
			Fetch latest dividend history and fundamentals from NSE / Yahoo Finance.
		</p>
		<div class="mt-5 h-[2px] w-full" style="background: linear-gradient(90deg, var(--color-coral-400) 0%, transparent 40%);"></div>
	</div>

	<!-- Quick actions -->
	<div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8 stagger">
		<button
			onclick={() => { req.symbol = ''; req.limit = 50; req.max_age = 7; req.force = false; startUpdate(); }}
			disabled={status === 'running'}
			class="surface-interactive p-4 text-left disabled:opacity-50 disabled:pointer-events-none group"
		>
			<div class="flex items-center gap-3">
				<div class="flex h-9 w-9 items-center justify-center rounded-lg bg-coral-500/8 group-hover:bg-coral-500/15 transition-colors">
					<Zap class="h-4 w-4 text-coral-400" />
				</div>
				<div>
					<p class="text-sm font-medium text-cream-200">Quick Update</p>
					<p class="text-[11px] text-ink-500">50 oldest tickers</p>
				</div>
			</div>
		</button>

		<button
			onclick={() => { req.symbol = ''; req.limit = undefined; req.max_age = 7; req.force = false; startUpdate(); }}
			disabled={status === 'running'}
			class="surface-interactive p-4 text-left disabled:opacity-50 disabled:pointer-events-none group"
		>
			<div class="flex items-center gap-3">
				<div class="flex h-9 w-9 items-center justify-center rounded-lg bg-coral-500/8 group-hover:bg-coral-500/15 transition-colors">
					<CloudDownload class="h-4 w-4 text-coral-400" />
				</div>
				<div>
					<p class="text-sm font-medium text-cream-200">Full Update</p>
					<p class="text-[11px] text-ink-500">All stale tickers</p>
				</div>
			</div>
		</button>

		<button
			onclick={() => { req.symbol = ''; req.limit = undefined; req.max_age = 0; req.force = true; startUpdate(); }}
			disabled={status === 'running'}
			class="surface-interactive p-4 text-left disabled:opacity-50 disabled:pointer-events-none group"
		>
			<div class="flex items-center gap-3">
				<div class="flex h-9 w-9 items-center justify-center rounded-lg bg-signal-red/8 group-hover:bg-signal-red/15 transition-colors">
					<RefreshCw class="h-4 w-4 text-signal-red" />
				</div>
				<div>
					<p class="text-sm font-medium text-cream-200">Force Refresh</p>
					<p class="text-[11px] text-ink-500">Re-fetch everything</p>
				</div>
			</div>
		</button>
	</div>

	<!-- Custom form -->
	<div class="surface p-6 mb-8">
		<div class="editorial-rule mb-5">
			<h2 class="text-sm font-semibold text-cream-200">Custom Update</h2>
		</div>

		<form
			onsubmit={(e) => { e.preventDefault(); startUpdate(); }}
			class="space-y-5"
		>
			<!-- Symbol -->
			<div>
				<label for="symbol" class="label mb-2 block">
					Symbol <span class="font-normal text-ink-500">(blank = all)</span>
				</label>
				<input
					id="symbol"
					type="text"
					bind:value={req.symbol}
					placeholder="e.g. HDFCBANK.NS, INFY.NS"
					disabled={status === 'running'}
					class="input-field"
				/>
				<p class="mt-1.5 text-[11px] text-ink-500">Separate multiple with commas</p>
			</div>

			<!-- Max age + Limit -->
			<div class="grid grid-cols-2 gap-4">
				<div>
					<label for="max_age" class="label mb-2 block">Max Age <span class="font-normal text-ink-500">(days)</span></label>
					<input
						id="max_age"
						type="number"
						min="0"
						step="1"
						bind:value={req.max_age}
						disabled={status === 'running'}
						class="input-field"
					/>
				</div>
				<div>
					<label for="limit" class="label mb-2 block">Limit <span class="font-normal text-ink-500">(optional)</span></label>
					<input
						id="limit"
						type="number"
						min="1"
						step="1"
						bind:value={req.limit}
						placeholder="all"
						disabled={status === 'running'}
						class="input-field"
					/>
				</div>
			</div>

			<!-- Force checkbox -->
			<label class="group flex items-center gap-3 cursor-pointer surface p-3.5 transition-all hover:border-coral-400/15">
				<input
					type="checkbox"
					bind:checked={req.force}
					disabled={status === 'running'}
					class="h-4 w-4 rounded border-ink-600 bg-transparent accent-coral-500"
				/>
				<div>
					<span class="text-sm font-medium text-cream-200">Force re-fetch</span>
					<p class="text-[11px] text-ink-500">Ignore max age and existing data</p>
				</div>
			</label>

			<!-- Buttons -->
			<div class="flex gap-3 pt-1">
				<button
					type="submit"
					disabled={status === 'running'}
					class="btn-coral"
				>
					{#if status === 'running'}
						<RefreshCw class="h-4 w-4 animate-spin" />
						Running...
					{:else}
						<Play class="h-4 w-4" />
						Start Update
					{/if}
				</button>

				{#if status === 'running'}
					<button
						type="button"
						onclick={stopUpdate}
						class="btn-outline text-signal-red border-signal-red/20 hover:bg-signal-red/8"
					>
						<Square class="h-3.5 w-3.5" />
						Stop
					</button>
				{/if}
			</div>
		</form>
	</div>

	<!-- Progress + Terminal output -->
	{#if status !== 'idle'}
		<div class="surface p-6 animate-enter">
			<!-- Status header -->
			<div class="flex items-center justify-between mb-4">
				<div class="flex items-center gap-2.5">
					{#if status === 'running'}
						<RefreshCw class="h-4 w-4 text-coral-400 animate-spin" />
					{:else if status === 'done'}
						<CheckCircle class="h-4 w-4 text-mint-400" />
					{:else if status === 'error'}
						<XCircle class="h-4 w-4 text-signal-red" />
					{:else}
						<Terminal class="h-4 w-4 text-ink-500" />
					{/if}
					<span class="text-sm font-semibold text-cream-200">{statusText(status)}</span>
				</div>
				<div class="flex items-center gap-3">
					{#if progress > 0}
						<span class="text-sm font-mono font-semibold {status === 'done' ? 'text-mint-400' : status === 'error' ? 'text-signal-red' : 'text-coral-400'}">{progress.toFixed(0)}%</span>
					{/if}
					{#if jobId}
						<span class="font-mono text-[10px] text-ink-500">#{jobId.substring(0, 8)}</span>
					{/if}
				</div>
			</div>

			<!-- Progress bar -->
			{#if status === 'running' || status === 'done'}
				<div class="h-1 rounded-full bg-ink-800 overflow-hidden mb-5">
					<div
						class="h-full rounded-full transition-all duration-500 ease-out"
						style="width: {progress}%; background: {status === 'done' ? 'var(--color-mint-500)' : 'var(--color-coral-400)'};"
					></div>
				</div>
			{/if}

			<!-- Error message -->
			{#if errorMsg}
				<div class="flex items-start gap-3 rounded-lg border border-signal-red/15 bg-signal-red/5 p-4 mb-5 text-sm text-signal-red">
					<XCircle class="mt-0.5 h-4 w-4 shrink-0" />
					<span>{errorMsg}</span>
				</div>
			{/if}

			<!-- Terminal output -->
			{#if logs.length > 0}
				<div class="flex items-center gap-2 border-b border-ink-700/40 pb-2.5 mb-3">
					<Terminal class="h-3.5 w-3.5 text-ink-500" />
					<span class="label">Output</span>
					<span class="ml-auto font-mono text-[10px] text-ink-500">{logs.length} lines</span>
				</div>
				<div
					bind:this={logContainer}
					class="h-72 overflow-y-auto rounded-lg bg-ink-950 p-4 font-mono text-xs leading-relaxed text-ink-300"
				>
					{#each logs as line}
						<p
							class={line.includes('ERROR') || line.includes('error') ? 'text-signal-red' :
								line.includes('WARN') || line.includes('warn') ? 'text-signal-amber' :
								line.includes('\u2713') || line.includes('done') || line.includes('Done') || line.includes('OK') ? 'text-mint-400' : ''}
						>{line}</p>
					{/each}
					{#if status === 'running'}
						<span class="inline-block h-3.5 w-1.5 animate-pulse bg-coral-400 rounded-sm">&nbsp;</span>
					{/if}
				</div>
			{:else if status === 'running'}
				<div class="flex items-center gap-2 text-sm text-ink-500 mt-4">
					<div class="h-1.5 w-1.5 rounded-full bg-coral-400 animate-pulse"></div>
					Waiting for output...
				</div>
			{/if}
		</div>
	{/if}
</div>
