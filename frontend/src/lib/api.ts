import type { BatchEvent, BatchGenerateRequest, GenerateRequest, GenerateResponse } from './types';

function extractErrorMessage(body: Record<string, unknown>, status: number): string {
	const detail = body.detail;
	if (typeof detail === 'string') return detail;
	if (Array.isArray(detail)) {
		return detail
			.map((e: Record<string, unknown>) => {
				const loc = Array.isArray(e.loc) ? e.loc.slice(1).join('.') : '';
				const msg = e.msg || 'invalid';
				return loc ? `${loc}: ${msg}` : String(msg);
			})
			.join('; ');
	}
	return `HTTP ${status}`;
}

export async function generate(
	request: GenerateRequest,
	signal?: AbortSignal
): Promise<GenerateResponse> {
	const res = await fetch('/api/generate', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(request),
		signal
	});

	if (!res.ok) {
		const body = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(extractErrorMessage(body, res.status));
	}

	return res.json();
}

export async function generateBatch(
	request: BatchGenerateRequest,
	onEvent: (event: BatchEvent) => void,
	signal?: AbortSignal
): Promise<void> {
	const res = await fetch('/api/generate/batch', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(request),
		signal
	});

	if (!res.ok) {
		const body = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(extractErrorMessage(body, res.status));
	}

	const reader = res.body?.getReader();
	if (!reader) throw new Error('No response body');

	const decoder = new TextDecoder();
	let buffer = '';

	while (true) {
		const { done, value } = await reader.read();
		if (done) break;

		buffer += decoder.decode(value, { stream: true });

		// Parse SSE events from buffer (sse-starlette uses \r\n line endings)
		const parts = buffer.split(/\r?\n\r?\n/);
		buffer = parts.pop() || '';

		for (const part of parts) {
			const lines = part.split('\n');
			let eventType = '';
			let data = '';

			for (const line of lines) {
				const trimmed = line.replace(/\r$/, '');
				if (trimmed.startsWith('event:')) {
					eventType = trimmed.slice(6).trim();
				} else if (trimmed.startsWith('data:')) {
					data += trimmed.slice(5).trim();
				}
			}

			if (eventType && data) {
				try {
					const parsed = JSON.parse(data) as BatchEvent;
					onEvent(parsed);
				} catch (e) {
					console.warn('SSE parse error:', e, 'raw data:', data.slice(0, 200));
				}
			}
		}
	}
}

export async function healthCheck(): Promise<boolean> {
	try {
		const res = await fetch('/api/health');
		return res.ok;
	} catch {
		return false;
	}
}
