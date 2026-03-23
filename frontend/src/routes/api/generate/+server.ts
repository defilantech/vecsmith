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
		res = await fetch(`${backendUrl()}/generate`, {
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

	return json(await res.json());
};
