<script lang="ts">
	import { generate, generateBatch } from '$lib/api';
	import type { BatchEvent, GenerateResponse, GalleryItem } from '$lib/types';
	import { formatBytes, formatSeconds, sanitizeSvg } from '$lib/utils';

	type Status = 'idle' | 'generating' | 'success' | 'error';

	// Core state
	let prompt = $state('');
	let status = $state<Status>('idle');
	let result = $state<GenerateResponse | null>(null);
	let errorMessage = $state('');
	let elapsedSeconds = $state(0);

	// Options
	let skipEnhance = $state(false);
	let showAdvanced = $state(false);
	let width = $state(1024);
	let height = $state(1024);
	let numInferenceSteps = $state(4);
	let seed = $state('');
	let outputFormat = $state<'svg' | 'png'>('svg');
	let count = $state(1);

	// Batch/gallery state
	let galleryItems = $state<GalleryItem[]>([]);
	let selectedIndex = $state(0);
	let batchCompleted = $state(0);

	// Derived
	let isBatchMode = $derived(count > 1);
	let canGenerate = $derived(prompt.trim().length > 0 && status !== 'generating');
	let sanitizedSvg = $derived(result && result.output_format === 'svg' ? sanitizeSvg(result.svg) : '');

	let activeResult = $derived.by(() => {
		if (isBatchMode && galleryItems.length > 0) {
			return galleryItems[selectedIndex]?.result ?? null;
		}
		return result;
	});

	let activeSanitizedSvg = $derived(
		activeResult && activeResult.output_format === 'svg' ? sanitizeSvg(activeResult.svg) : ''
	);

	let stageHint = $derived.by(() => {
		if (status !== 'generating') return '';
		if (isBatchMode) {
			const current = galleryItems.find((g) => g.status !== 'done' && g.status !== 'error' && g.status !== 'pending');
			const stageLabel = current?.status === 'vectorizing' ? 'Vectorizing' : current?.status === 'optimizing' ? 'Optimizing' : 'Generating image';
			return `${stageLabel} (${batchCompleted + 1}/${count})`;
		}
		if (elapsedSeconds < 3) return 'Enhancing prompt...';
		if (elapsedSeconds < 15) return 'Generating image...';
		if (outputFormat === 'png') return 'Finishing...';
		return 'Vectorizing...';
	});

	// Elapsed time counter
	let timerInterval: ReturnType<typeof setInterval> | undefined;
	let abortController: AbortController | undefined;

	function startTimer() {
		elapsedSeconds = 0;
		timerInterval = setInterval(() => {
			elapsedSeconds += 0.1;
		}, 100);
	}

	function stopTimer() {
		if (timerInterval) {
			clearInterval(timerInterval);
			timerInterval = undefined;
		}
	}

	function parseSeed(): number | undefined {
		const parsedSeed = seed.trim() ? parseInt(seed, 10) : undefined;
		return Number.isNaN(parsedSeed) ? undefined : parsedSeed;
	}

	async function handleGenerate() {
		if (!canGenerate) return;

		status = 'generating';
		result = null;
		errorMessage = '';
		galleryItems = [];
		selectedIndex = 0;
		batchCompleted = 0;
		abortController = new AbortController();
		startTimer();

		if (isBatchMode) {
			await handleBatchGenerate();
		} else {
			await handleSingleGenerate();
		}
	}

	async function handleSingleGenerate() {
		try {
			result = await generate(
				{
					prompt: prompt.trim(),
					width,
					height,
					skip_enhance: skipEnhance,
					seed: parseSeed(),
					num_inference_steps: numInferenceSteps,
					output_format: outputFormat
				},
				abortController!.signal
			);
			status = 'success';
		} catch (e) {
			if (e instanceof DOMException && e.name === 'AbortError') {
				status = 'idle';
			} else {
				errorMessage = e instanceof Error ? e.message : 'Unknown error';
				status = 'error';
			}
		} finally {
			stopTimer();
			abortController = undefined;
		}
	}

	async function handleBatchGenerate() {
		// Initialize gallery items
		galleryItems = Array.from({ length: count }, (_, i) => ({
			index: i,
			status: 'pending',
			result: null,
			error: null
		}));

		function onEvent(event: BatchEvent) {
			switch (event.event) {
				case 'progress': {
					const item = galleryItems[event.index];
					if (item) {
						item.status = event.stage;
					}
					break;
				}
				case 'result': {
					const item = galleryItems[event.index];
					if (item) {
						item.status = 'done';
						item.result = event.result;
					}
					batchCompleted = galleryItems.filter((g) => g.status === 'done' || g.status === 'error').length;
					// Auto-select first completed item
					if (batchCompleted === 1 && selectedIndex === 0) {
						selectedIndex = event.index;
					}
					break;
				}
				case 'error': {
					const item = galleryItems[event.index];
					if (item) {
						item.status = 'error';
						item.error = event.detail;
					}
					batchCompleted = galleryItems.filter((g) => g.status === 'done' || g.status === 'error').length;
					break;
				}
				case 'done':
					break;
			}
		}

		try {
			await generateBatch(
				{
					prompt: prompt.trim(),
					count,
					width,
					height,
					skip_enhance: skipEnhance,
					seed: parseSeed(),
					num_inference_steps: numInferenceSteps,
					output_format: outputFormat
				},
				onEvent,
				abortController!.signal
			);
			status = 'success';
		} catch (e) {
			if (e instanceof DOMException && e.name === 'AbortError') {
				status = 'idle';
				galleryItems = [];
			} else {
				errorMessage = e instanceof Error ? e.message : 'Unknown error';
				// If we have some results, still show them
				if (galleryItems.some((g) => g.status === 'done')) {
					status = 'success';
				} else {
					status = 'error';
				}
			}
		} finally {
			stopTimer();
			abortController = undefined;
		}
	}

	function handleCancel() {
		abortController?.abort();
		stopTimer();
		// If we have partial results, show them
		if (isBatchMode && galleryItems.some((g) => g.status === 'done')) {
			status = 'success';
		} else {
			status = 'idle';
		}
	}

	function clamp(value: number, min: number, max: number): number {
		return Math.min(max, Math.max(min, value));
	}

	function handleKeydown(e: KeyboardEvent) {
		if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
			e.preventDefault();
			handleGenerate();
		}
	}

	function filenameFromPrompt(prompt: string, ext: string, index?: number): string {
		const title = prompt
			.trim()
			.replace(/^(a|an|the)\s+/i, '')
			.split(/\s+/)
			.slice(0, 5)
			.map((w) => w.replace(/[^a-zA-Z0-9]/g, ''))
			.filter((w) => w.length > 0)
			.map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
			.join(' ');
		const suffix = index != null ? ` ${index + 1}` : '';
		return `${title || 'Generated'}${suffix}.${ext}`;
	}

	function downloadResult() {
		const res = activeResult;
		if (!res) return;
		const ext = res.output_format === 'png' ? 'png' : 'svg';
		const idx = isBatchMode ? selectedIndex : undefined;
		const filename = filenameFromPrompt(res.original_prompt, ext, idx);
		if (res.output_format === 'png' && res.png_base64) {
			const bytes = Uint8Array.from(atob(res.png_base64), (c) => c.charCodeAt(0));
			const blob = new Blob([bytes], { type: 'image/png' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = filename;
			a.click();
			URL.revokeObjectURL(url);
		} else {
			const blob = new Blob([res.svg], { type: 'image/svg+xml' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = filename;
			a.click();
			URL.revokeObjectURL(url);
		}
	}

	let copied = $state(false);
	function copySvgCode() {
		const res = activeResult;
		if (!res) return;
		navigator.clipboard.writeText(res.svg);
		copied = true;
		setTimeout(() => (copied = false), 2000);
	}

	function handleRegenerate() {
		handleGenerate();
	}

	// Timing bar widths
	function timingPercent(value: number | null, total: number): number {
		if (!value || total === 0) return 0;
		return (value / total) * 100;
	}

	function galleryItemLabel(item: GalleryItem): string {
		switch (item.status) {
			case 'pending':
				return 'Waiting...';
			case 'generating':
				return 'Generating...';
			case 'vectorizing':
				return 'Vectorizing...';
			case 'optimizing':
				return 'Optimizing...';
			case 'error':
				return 'Failed';
			case 'done':
				return '';
		}
	}
</script>

<div class="min-h-screen bg-surface text-text">
	<div class="mx-auto max-w-2xl px-4 py-8">
		<!-- Header -->
		<header class="mb-8 text-center">
			<h1 class="text-3xl font-bold">Vecsmith</h1>
			<p class="mt-1 text-text-muted">Powered by Flux & vtracer</p>
		</header>

		<!-- Input Section -->
		<div class="rounded-lg border border-border bg-surface-raised p-5">
			<label for="prompt" class="mb-2 block text-sm font-medium">Describe the image you want</label>
			<textarea
				id="prompt"
				bind:value={prompt}
				onkeydown={handleKeydown}
				rows={3}
				maxlength={2000}
				placeholder="A minimalist mountain landscape at sunset..."
				disabled={status === 'generating'}
				class="w-full resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm text-text placeholder-text-muted transition focus:border-border-focus focus:outline-none disabled:opacity-50"
			></textarea>
			<div class="mt-1 text-right text-xs text-text-muted">
				{prompt.length} / 2000
			</div>

			<!-- Options row -->
			<div class="mt-3 flex items-center gap-4">
				<label class="flex items-center gap-2 text-sm">
					<input
						type="checkbox"
						bind:checked={skipEnhance}
						class="rounded border-border accent-accent"
					/>
					<span class="text-text-muted">Skip prompt enhancement</span>
				</label>

				<!-- Count slider -->
				<label class="flex items-center gap-2 text-sm">
					<span class="text-text-muted">Variations</span>
					<input
						type="range"
						min={1}
						max={10}
						bind:value={count}
						class="h-1.5 w-20 cursor-pointer accent-accent"
					/>
					<span class="w-5 text-center text-sm font-medium tabular-nums">{count}</span>
				</label>

				<button
					type="button"
					onclick={() => (showAdvanced = !showAdvanced)}
					class="ml-auto text-sm text-text-muted transition hover:text-text"
				>
					Advanced {showAdvanced ? '\u25B4' : '\u25BE'}
				</button>
			</div>

			<!-- Advanced options -->
			{#if showAdvanced}
				<div class="mt-3 grid grid-cols-2 gap-3 rounded-md border border-border bg-surface p-3 sm:grid-cols-4">
					<label class="text-xs">
						<span class="text-text-muted">Width</span>
						<input
							type="number"
							bind:value={width}
							min={256}
							max={2048}
							step={64}
							onblur={() => (width = clamp(width, 256, 2048))}
							class="mt-1 w-full rounded border border-border bg-surface-raised px-2 py-1 text-sm text-text"
						/>
					</label>
					<label class="text-xs">
						<span class="text-text-muted">Height</span>
						<input
							type="number"
							bind:value={height}
							min={256}
							max={2048}
							step={64}
							onblur={() => (height = clamp(height, 256, 2048))}
							class="mt-1 w-full rounded border border-border bg-surface-raised px-2 py-1 text-sm text-text"
						/>
					</label>
					<label class="text-xs">
						<span class="text-text-muted">Steps</span>
						<input
							type="number"
							bind:value={numInferenceSteps}
							min={1}
							max={50}
							class="mt-1 w-full rounded border border-border bg-surface-raised px-2 py-1 text-sm text-text"
						/>
					</label>
					<label class="text-xs">
						<span class="text-text-muted">Seed</span>
						<input
							type="text"
							bind:value={seed}
							placeholder="Random"
							class="mt-1 w-full rounded border border-border bg-surface-raised px-2 py-1 text-sm text-text placeholder-text-muted"
						/>
					</label>
				</div>
			{/if}

			<!-- Output format toggle + Generate button -->
			<div class="mt-4 flex gap-3">
				<!-- Segmented toggle -->
				<div class="flex shrink-0 overflow-hidden rounded-md border border-border">
					<button
						type="button"
						onclick={() => (outputFormat = 'svg')}
						class="px-3 py-2.5 text-sm font-medium transition {outputFormat === 'svg'
							? 'bg-accent text-white'
							: 'bg-surface-overlay text-text-muted hover:text-text'}"
					>
						SVG
					</button>
					<button
						type="button"
						onclick={() => (outputFormat = 'png')}
						class="px-3 py-2.5 text-sm font-medium transition {outputFormat === 'png'
							? 'bg-accent text-white'
							: 'bg-surface-overlay text-text-muted hover:text-text'}"
					>
						PNG
					</button>
				</div>

				{#if status === 'generating'}
					<button
						type="button"
						onclick={handleCancel}
						class="w-full cursor-pointer rounded-md border border-border bg-surface-overlay px-4 py-2.5 text-sm font-medium text-text transition hover:bg-surface"
					>
						Cancel
					</button>
				{:else}
					<button
						type="button"
						onclick={handleGenerate}
						disabled={!canGenerate}
						class="w-full cursor-pointer rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
					>
						Generate {outputFormat.toUpperCase()}{count > 1 ? ` x${count}` : ''}
					</button>
				{/if}
			</div>
		</div>

		<!-- Loading state -->
		{#if status === 'generating'}
			<div class="mt-6 rounded-lg border border-border bg-surface-raised p-5 text-center">
				<div class="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-border border-t-accent"></div>
				<p class="text-sm font-medium">
					{stageHint}
					<span class="ml-1 text-text-muted">{elapsedSeconds.toFixed(1)}s</span>
				</p>
			</div>
		{/if}

		<!-- Gallery grid (batch mode, visible during and after generation) -->
		{#if isBatchMode && galleryItems.length > 0}
			<div class="mt-6 rounded-lg border border-border bg-surface-raised p-4">
				<h3 class="mb-3 text-sm font-medium">
					Variations
					{#if status === 'generating'}
						<span class="text-text-muted">({batchCompleted}/{count})</span>
					{/if}
				</h3>
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
					{#each galleryItems as item, i}
						<button
							type="button"
							onclick={() => {
								if (item.status === 'done') selectedIndex = i;
							}}
							class="group relative aspect-square overflow-hidden rounded-md border-2 transition
								{selectedIndex === i && item.status === 'done'
								? 'border-accent'
								: 'border-border hover:border-border-focus'}
								{item.status === 'done' ? 'cursor-pointer' : 'cursor-default'}"
						>
							<!-- Badge -->
							<span
								class="absolute left-1 top-1 z-10 flex h-5 w-5 items-center justify-center rounded-full text-xs font-medium
									{selectedIndex === i && item.status === 'done'
									? 'bg-accent text-white'
									: 'bg-surface-overlay/80 text-text-muted'}"
							>
								{i + 1}
							</span>

							{#if item.status === 'done' && item.result}
								<!-- Thumbnail -->
								<div class="checkerboard-sm flex h-full w-full items-center justify-center p-1">
									{#if item.result.output_format === 'png' && item.result.png_base64}
										<img
											src="data:image/png;base64,{item.result.png_base64}"
											alt="Variation {i + 1}"
											class="max-h-full max-w-full object-contain"
										/>
									{:else}
										<div class="gallery-svg-container">
											{@html sanitizeSvg(item.result.svg)}
										</div>
									{/if}
								</div>
							{:else if item.status === 'error'}
								<!-- Error state -->
								<div class="flex h-full w-full flex-col items-center justify-center bg-error/10 p-2">
									<span class="text-lg text-error">!</span>
									<span class="mt-1 text-xs text-error">Failed</span>
								</div>
							{:else}
								<!-- Loading state -->
								<div class="flex h-full w-full flex-col items-center justify-center bg-surface p-2">
									<div class="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-accent"></div>
									<span class="mt-2 text-xs text-text-muted">{galleryItemLabel(item)}</span>
								</div>
							{/if}
						</button>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Error state -->
		{#if status === 'error'}
			<div class="mt-6 rounded-lg border border-error/30 bg-error/10 p-5">
				<p class="text-sm font-medium text-error">Generation failed</p>
				<p class="mt-1 text-sm text-text-muted">{errorMessage}</p>
				<button
					type="button"
					onclick={handleGenerate}
					class="mt-3 cursor-pointer rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-hover"
				>
					Retry
				</button>
			</div>
		{/if}

		<!-- Success state / Preview -->
		{#if (status === 'success' && activeResult) || (status === 'generating' && isBatchMode && activeResult)}
			<div class="mt-6 space-y-4">
				<!-- Preview -->
				<div class="rounded-lg border border-border bg-surface-raised p-4">
					<div
						class="checkerboard flex items-center justify-center overflow-hidden rounded-md p-4"
					>
						{#if activeResult.output_format === 'png' && activeResult.png_base64}
							<img
								src="data:image/png;base64,{activeResult.png_base64}"
								alt="Generated PNG"
								class="max-h-[512px] max-w-full"
							/>
						{:else}
							<div class="svg-container">
								{@html activeSanitizedSvg}
							</div>
						{/if}
					</div>
				</div>

				<!-- Action buttons -->
				{#if status === 'success'}
					<div class="flex gap-3">
						<button
							type="button"
							onclick={downloadResult}
							class="flex-1 cursor-pointer rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-hover"
						>
							Download {activeResult.output_format === 'png' ? 'PNG' : 'SVG'}
						</button>
						{#if activeResult.output_format === 'svg'}
							<button
								type="button"
								onclick={copySvgCode}
								class="flex-1 cursor-pointer rounded-md border border-border bg-surface-overlay px-4 py-2 text-sm font-medium text-text transition hover:bg-surface"
							>
								{copied ? 'Copied!' : 'Copy Code'}
							</button>
						{/if}
						<button
							type="button"
							onclick={handleRegenerate}
							class="flex-1 cursor-pointer rounded-md border border-border bg-surface-overlay px-4 py-2 text-sm font-medium text-text transition hover:bg-surface"
						>
							Regenerate
						</button>
					</div>
				{/if}

				<!-- Timings -->
				<div class="rounded-lg border border-border bg-surface-raised p-4">
					<h3 class="mb-3 text-sm font-medium">
						Pipeline Timings
						{#if isBatchMode && galleryItems.length > 0}
							<span class="text-text-muted">(Variation {selectedIndex + 1})</span>
						{/if}
					</h3>
					<div class="space-y-2">
						{#each [
							{ label: 'Prompt Enhance', value: activeResult.timings.prompt_enhance_s },
							{ label: 'Image Generate', value: activeResult.timings.image_generate_s },
							{ label: 'Vectorize', value: activeResult.timings.vectorize_s },
							{ label: 'SVG Optimize', value: activeResult.timings.svg_optimize_s }
						] as stage}
							{#if stage.value != null}
								<div class="flex items-center gap-3 text-xs">
									<span class="w-28 shrink-0 text-text-muted">{stage.label}</span>
									<div class="h-2 flex-1 overflow-hidden rounded-full bg-surface">
										<div
											class="h-full rounded-full bg-accent transition-all"
											style="width: {timingPercent(stage.value, activeResult.timings.total_s)}%"
										></div>
									</div>
									<span class="w-12 shrink-0 text-right text-text-muted">{formatSeconds(stage.value)}</span>
								</div>
							{/if}
						{/each}
						<div class="flex items-center justify-between border-t border-border pt-2 text-xs">
							<span class="text-text-muted">Total</span>
							<span class="font-medium">{formatSeconds(activeResult.timings.total_s)}</span>
						</div>
					</div>
				</div>

				<!-- Metadata -->
				<div class="rounded-lg border border-border bg-surface-raised p-4 text-sm">
					<div class="flex justify-between text-text-muted">
						<span>{activeResult.output_format === 'png' ? 'PNG size' : 'SVG size'}</span>
						<span>{formatBytes(activeResult.svg_size_bytes)}</span>
					</div>
					{#if activeResult.prompt_used !== activeResult.original_prompt}
						<div class="mt-3 border-t border-border pt-3">
							<p class="text-xs font-medium text-text-muted">Enhanced prompt:</p>
							<p class="mt-1 text-xs text-text">{activeResult.prompt_used}</p>
						</div>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Keyboard shortcut hint -->
		<p class="mt-6 text-center text-xs text-text-muted">
			Press <kbd class="rounded border border-border px-1.5 py-0.5 font-mono text-xs">Ctrl</kbd>+<kbd class="rounded border border-border px-1.5 py-0.5 font-mono text-xs">Enter</kbd> to generate
		</p>
	</div>
</div>

<style>
	.checkerboard {
		background-color: #1a1a2e;
		background-image: repeating-conic-gradient(#252540 0% 25%, transparent 0% 50%);
		background-size: 16px 16px;
	}

	.checkerboard-sm {
		background-color: #1a1a2e;
		background-image: repeating-conic-gradient(#252540 0% 25%, transparent 0% 50%);
		background-size: 8px 8px;
	}

	.svg-container :global(svg) {
		max-width: 100%;
		height: auto;
		max-height: 512px;
	}

	.gallery-svg-container :global(svg) {
		max-width: 100%;
		height: auto;
		max-height: 100%;
	}
</style>
