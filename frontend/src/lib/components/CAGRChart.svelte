<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js';
	import type { CAGRStats } from '$lib/types';

	Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);

	let { data }: { data: CAGRStats[] } = $props();

	let canvas: HTMLCanvasElement | undefined;
	let chart: Chart | null = null;

	// Mint for positive, signal-red for negative
	const MINT = 'rgba(77, 230, 176, 0.55)';
	const MINT_BORDER = 'rgba(77, 230, 176, 0.75)';
	const MINT_HOVER = 'rgba(77, 230, 176, 0.8)';
	const RED = 'rgba(239, 83, 80, 0.55)';
	const RED_BORDER = 'rgba(239, 83, 80, 0.75)';
	const RED_HOVER = 'rgba(239, 83, 80, 0.8)';

	function buildChart() {
		if (!canvas) return;
		chart?.destroy();

		const filtered = data.filter(d => d.cagr != null);
		const labels = filtered.map(d => d.period);
		const values = filtered.map(d => d.cagr as number);

		chart = new Chart(canvas, {
			type: 'bar',
			data: {
				labels,
				datasets: [
					{
						label: 'CAGR (%)',
						data: values,
						backgroundColor: values.map(v => v >= 0 ? MINT : RED),
						borderColor: values.map(v => v >= 0 ? MINT_BORDER : RED_BORDER),
						borderWidth: 1,
						borderRadius: 3,
						borderSkipped: false,
						hoverBackgroundColor: values.map(v => v >= 0 ? MINT_HOVER : RED_HOVER),
					},
				],
			},
			options: {
				responsive: true,
				maintainAspectRatio: true,
				animation: {
					duration: 700,
					easing: 'easeOutQuart',
				},
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: 'rgba(10, 12, 16, 0.95)',
						borderColor: 'rgba(77, 230, 176, 0.15)',
						borderWidth: 1,
						titleColor: '#faf9f6',
						bodyColor: '#9098b1',
						titleFont: { family: "'Geist', sans-serif", weight: 600 as const },
						bodyFont: { family: "'Geist Mono', monospace" },
						padding: 10,
						cornerRadius: 6,
						displayColors: false,
						callbacks: {
							label: ctx => `${(ctx.raw as number).toFixed(2)}% CAGR`,
						},
					},
				},
				scales: {
					x: {
						ticks: { color: '#545a72', font: { size: 10, family: "'Geist Mono', monospace" } },
						grid: { display: false },
						border: { display: false },
					},
					y: {
						ticks: {
							color: '#545a72',
							font: { size: 10, family: "'Geist Mono', monospace" },
							callback: v => `${v}%`,
						},
						grid: { color: 'rgba(144, 152, 177, 0.05)' },
						border: { display: false },
					},
				},
			},
		});
	}

	onMount(() => buildChart());

	$effect(() => {
		data;
		buildChart();
	});

	onDestroy(() => chart?.destroy());
</script>

<canvas bind:this={canvas} class="w-full"></canvas>
