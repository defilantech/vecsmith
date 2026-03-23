import { env } from '$env/dynamic/private';
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const backendUrl = () => env.VECSMITH_API_URL || 'http://localhost:8080';

export const POST: RequestHandler = async ({ request }) => {
	let body: unknown;
	try {
		body = await request.json();
	} catch {
		return json({ detail: 'Invalid JSON in request body' }, { status: 400 });
	}

	let res: Response;
	try {
		res = await fetch(`${backendUrl()}/generate/batch`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(body)
		});
	} catch (e) {
		const msg = e instanceof Error ? e.message : 'Unknown error';
		return json({ detail: `Backend unreachable: ${msg}` }, { status: 502 });
	}

	if (!res.ok) {
		const error = await res.json().catch(() => ({ detail: res.statusText }));
		return json(error, { status: res.status });
	}

	if (!res.body) {
		return json({ detail: 'No response body from backend' }, { status: 502 });
	}

	// Eagerly read chunks from the backend and push them through a fresh
	// ReadableStream. Using start() instead of pull() ensures chunks are
	// forwarded immediately as they arrive, rather than waiting for the
	// consumer (adapter-node / Nginx) to request them.
	const backendReader = res.body.getReader();
	const stream = new ReadableStream({
		async start(controller) {
			try {
				while (true) {
					const { done, value } = await backendReader.read();
					if (done) {
						controller.close();
						return;
					}
					controller.enqueue(value);
				}
			} catch {
				// Backend closed or client disconnected
				controller.close();
			}
		},
		cancel() {
			backendReader.cancel();
		}
	});

	return new Response(stream, {
		headers: {
			'Content-Type': 'text/event-stream',
			'Cache-Control': 'no-cache',
			'X-Accel-Buffering': 'no'
		}
	});
};
