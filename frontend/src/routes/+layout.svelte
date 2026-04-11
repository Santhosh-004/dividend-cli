<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { Search, X, ArrowRight, Settings, Menu } from 'lucide-svelte';
	import { tickerList, ensureTickersLoaded } from '$lib/tickerStore';
	import type { TickerSummary } from '$lib/types';

	let { children } = $props();

	// Command palette state
	let cmdOpen = $state(false);
	let cmdQuery = $state('');
	let cmdActiveIndex = $state(-1);
	let cmdInput = $state<HTMLInputElement | undefined>(undefined);

	// Mobile nav
	let mobileMenuOpen = $state(false);

	const navLinks = [
		{ href: '/', label: 'Overview' },
		{ href: '/screener', label: 'Screener' },
	];

	onMount(() => {
		ensureTickersLoaded();

		function handleGlobalKeydown(e: KeyboardEvent) {
			if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !isInputFocused())) {
				e.preventDefault();
				openCmd();
			}
			if (e.key === 'Escape') {
				if (cmdOpen) closeCmd();
				if (mobileMenuOpen) mobileMenuOpen = false;
			}
		}
		document.addEventListener('keydown', handleGlobalKeydown);
		return () => document.removeEventListener('keydown', handleGlobalKeydown);
	});

	function isInputFocused() {
		const el = document.activeElement;
		return el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement;
	}

	function openCmd() {
		cmdOpen = true;
		cmdQuery = '';
		cmdActiveIndex = -1;
		setTimeout(() => cmdInput?.focus(), 50);
	}

	function closeCmd() {
		cmdOpen = false;
		cmdQuery = '';
		cmdActiveIndex = -1;
	}

	let cmdSuggestions = $derived.by(() => {
		const q = cmdQuery.trim().toLowerCase();
		if (!q) return [] as TickerSummary[];
		const all = $tickerList;
		const bySymbol = all.filter(t => t.symbol.toLowerCase().includes(q));
		const byName = all.filter(
			t => !t.symbol.toLowerCase().includes(q) && (t.name ?? '').toLowerCase().includes(q),
		);
		return [...bySymbol, ...byName].slice(0, 10);
	});

	function navigate(symbol: string) {
		goto(`/stock/${encodeURIComponent(symbol)}`);
		closeCmd();
	}

	function handleCmdKeydown(e: KeyboardEvent) {
		const items = cmdSuggestions;
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			cmdActiveIndex = Math.min(cmdActiveIndex + 1, items.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			cmdActiveIndex = Math.max(cmdActiveIndex - 1, -1);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			if (cmdActiveIndex >= 0 && items[cmdActiveIndex]) {
				navigate(items[cmdActiveIndex].symbol);
			} else if (cmdQuery.trim()) {
				navigate(cmdQuery.trim().toUpperCase());
			}
		} else if (e.key === 'Escape') {
			closeCmd();
		}
	}

	$effect(() => {
		const items = cmdSuggestions;
		if (items.length === 0) {
			cmdActiveIndex = -1;
		} else if (cmdActiveIndex < 0 || cmdActiveIndex >= items.length) {
			cmdActiveIndex = 0;
		}
	});

	function isActive(href: string) {
		if (href === '/') return $page.url.pathname === '/';
		return $page.url.pathname.startsWith(href);
	}
</script>

<!-- Command Palette Overlay -->
{#if cmdOpen}
	<div class="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]">
		<!-- Backdrop -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="absolute inset-0 bg-ink-950/80 backdrop-blur-sm animate-fade-in"
			onclick={closeCmd}
			onkeydown={(e) => e.key === 'Escape' && closeCmd()}
		></div>

		<!-- Palette -->
		<div class="relative z-10 w-full max-w-lg mx-4 animate-enter-scale">
			<div class="surface-raised overflow-hidden shadow-2xl shadow-black/40" style="border-radius: 16px;">
				<!-- Search input -->
				<div class="flex items-center gap-3 border-b border-ink-700/50 px-5 py-4">
					<Search class="h-5 w-5 text-ink-400 shrink-0" />
					<input
						bind:this={cmdInput}
						type="text"
						bind:value={cmdQuery}
						onkeydown={handleCmdKeydown}
						placeholder="Search stocks by symbol or name..."
						autocomplete="off"
						class="flex-1 bg-transparent text-cream-100 text-base placeholder-ink-500 outline-none"
					/>
					<button onclick={closeCmd} class="rounded-md p-1 text-ink-500 hover:text-cream-300 transition-colors">
						<X class="h-4 w-4" />
					</button>
				</div>

				<!-- Results -->
				{#if cmdQuery.trim() && cmdSuggestions.length > 0}
					<div class="max-h-80 overflow-y-auto py-2">
						{#each cmdSuggestions as s, i}
							<button
								type="button"
								class="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors
								{i === cmdActiveIndex ? 'bg-coral-500/8 text-cream-50' : 'text-cream-300 hover:bg-ink-800/50'}"
								onmousedown={() => navigate(s.symbol)}
								onmouseenter={() => { cmdActiveIndex = i; }}
							>
								<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-ink-800 font-mono text-xs font-semibold {i === cmdActiveIndex ? 'text-coral-400' : 'text-ink-400'}">
									{s.symbol.substring(0, 2)}
								</span>
								<div class="min-w-0 flex-1">
									<div class="flex items-baseline gap-2">
										<span class="font-semibold text-sm {i === cmdActiveIndex ? 'text-cream-50' : 'text-cream-200'}">{s.symbol}</span>
										{#if s.current_price}
											<span class="text-xs font-mono text-ink-400">₹{s.current_price.toFixed(2)}</span>
										{/if}
									</div>
									{#if s.name}
										<div class="truncate text-xs text-ink-400 mt-0.5">{s.name}</div>
									{/if}
								</div>
								{#if i === cmdActiveIndex}
									<ArrowRight class="h-3.5 w-3.5 text-coral-400 shrink-0" />
								{/if}
							</button>
						{/each}
					</div>
				{:else if cmdQuery.trim() && cmdSuggestions.length === 0}
					<div class="px-5 py-8 text-center text-sm text-ink-500">
						No matches. Press <span class="font-mono text-ink-400">Enter</span> to look up "{cmdQuery.trim().toUpperCase()}" directly.
					</div>
				{:else}
					<div class="px-5 py-6 text-center text-sm text-ink-500">
						Type a stock symbol or company name
					</div>
				{/if}

				<!-- Footer hints -->
				<div class="flex items-center gap-4 border-t border-ink-700/50 px-5 py-2.5 text-[11px] text-ink-500">
					<span class="flex items-center gap-1"><span class="kbd">↑</span><span class="kbd">↓</span> navigate</span>
					<span class="flex items-center gap-1"><span class="kbd">↵</span> open</span>
					<span class="flex items-center gap-1"><span class="kbd">esc</span> close</span>
				</div>
			</div>
		</div>
	</div>
{/if}

<div class="min-h-screen flex flex-col">
	<!-- Header -->
	<header class="sticky top-0 z-50 border-b border-ink-700/30 bg-ink-950/90 backdrop-blur-xl">
		<div class="mx-auto flex h-12 max-w-screen-xl items-center gap-6 px-4 lg:px-8">
			<!-- Logo: editorial style -->
			<a href="/" class="flex items-baseline gap-1.5 group shrink-0">
				<span class="heading-serif text-xl text-cream-50 group-hover:text-coral-400 transition-colors">Dividend</span>
				<span class="text-[11px] font-mono font-medium text-ink-500 tracking-wider uppercase">cli</span>
			</a>

			<!-- Desktop Nav -->
			<nav class="hidden md:flex items-center gap-1">
				{#each navLinks as link}
					<a
						href={link.href}
						class="relative px-3 py-1 text-[13px] font-medium transition-colors
						{isActive(link.href)
							? 'text-cream-50'
							: 'text-ink-400 hover:text-cream-300'}"
					>
						{link.label}
						{#if isActive(link.href)}
							<span class="absolute -bottom-[9px] left-1/2 -translate-x-1/2 w-4 h-[2px] bg-coral-400 rounded-full"></span>
						{/if}
					</a>
				{/each}
			</nav>

			<!-- Right side actions -->
			<div class="ml-auto flex items-center gap-2">
				<!-- Search trigger -->
				<button
					onclick={openCmd}
					class="flex items-center gap-2.5 rounded-lg border border-ink-700/40 bg-ink-900/50 px-3 py-1.5 text-[13px] text-ink-400 transition-all hover:border-ink-600/40 hover:text-cream-300 hover:bg-ink-800/50"
				>
					<Search class="h-3.5 w-3.5" />
					<span class="hidden sm:inline">Search</span>
					<div class="hidden sm:flex items-center gap-0.5">
						<span class="kbd">Ctrl</span>
						<span class="kbd">K</span>
					</div>
				</button>

				<!-- Settings (Update page) -->
				<a
					href="/update"
					class="flex items-center justify-center rounded-lg p-2 text-ink-500 transition-colors hover:text-cream-300 hover:bg-ink-800/50
					{isActive('/update') ? 'text-cream-200 bg-ink-800/30' : ''}"
					title="Data Settings"
				>
					<Settings class="h-4 w-4" />
				</a>

				<!-- Mobile menu toggle -->
				<button
					class="flex md:hidden items-center justify-center rounded-lg p-2 text-ink-500 transition-colors hover:text-cream-300"
					onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
					aria-label="Toggle menu"
				>
					{#if mobileMenuOpen}
						<X class="h-4.5 w-4.5" />
					{:else}
						<Menu class="h-4.5 w-4.5" />
					{/if}
				</button>
			</div>
		</div>

		<!-- Mobile nav -->
		{#if mobileMenuOpen}
			<nav class="animate-enter border-t border-ink-700/30 px-4 py-3 md:hidden">
				<div class="space-y-0.5">
					{#each navLinks as link}
						<a
							href={link.href}
							onclick={() => (mobileMenuOpen = false)}
							class="block rounded-lg px-3 py-2.5 text-sm font-medium transition-colors
							{isActive(link.href)
								? 'text-coral-400 bg-coral-500/5'
								: 'text-ink-400 hover:text-cream-200 hover:bg-ink-800/50'}"
						>
							{link.label}
						</a>
					{/each}
					<a
						href="/update"
						onclick={() => (mobileMenuOpen = false)}
						class="block rounded-lg px-3 py-2.5 text-sm font-medium transition-colors
						{isActive('/update')
							? 'text-coral-400 bg-coral-500/5'
							: 'text-ink-400 hover:text-cream-200 hover:bg-ink-800/50'}"
					>
						Data Settings
					</a>
				</div>
			</nav>
		{/if}
	</header>

	<!-- Main content -->
	<main class="flex-1 mx-auto w-full max-w-screen-xl px-4 py-8 lg:px-8">
		{@render children()}
	</main>

	<!-- Footer: ultra minimal -->
	<footer class="border-t border-ink-700/20 py-5">
		<div class="mx-auto max-w-screen-xl px-4 lg:px-8 flex items-center justify-between text-[11px] text-ink-600">
			<span class="font-mono tracking-wide">DIVIDEND CLI</span>
			<span class="flex items-center gap-1.5">
				<span class="kbd">/</span> search
				<span class="mx-1.5 text-ink-700">|</span>
				Indian Stock Dividend Analytics
			</span>
		</div>
	</footer>
</div>
