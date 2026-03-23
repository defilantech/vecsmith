import { env } from '$env/dynamic/private';
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const backendUrl = () => env.VECSMITH_API_URL || 'http://localhost:8080';

export const GET: RequestHandler = async () => {
	try {
		const res = await fetch(`${backendUrl()}/health`);
		return json(await res.json(), { status: res.status });
	} catch {
		return json({ status: 'unreachable' }, { status: 502 });
	}
};
