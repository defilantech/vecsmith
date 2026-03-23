/**
 * Strip <script> tags and on* event handlers from SVG to prevent XSS.
 */
export function sanitizeSvg(svg: string): string {
	return svg
		.replace(/<script[\s\S]*?<\/script>/gi, '')
		.replace(/\bon\w+\s*=\s*"[^"]*"/gi, '')
		.replace(/\bon\w+\s*=\s*'[^']*'/gi, '');
}

export function formatBytes(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatSeconds(seconds: number): string {
	return `${seconds.toFixed(1)}s`;
}
