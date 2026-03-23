export interface StageTimings {
	prompt_enhance_s: number | null;
	image_generate_s: number | null;
	vectorize_s: number | null;
	svg_optimize_s: number | null;
	total_s: number;
}

export interface GenerateRequest {
	prompt: string;
	width?: number;
	height?: number;
	skip_enhance?: boolean;
	seed?: number | null;
	num_inference_steps?: number;
	output_format?: 'svg' | 'png';
}

export interface GenerateResponse {
	svg: string;
	png_base64: string | null;
	output_format: string;
	prompt_used: string;
	timings: StageTimings;
	svg_size_bytes: number;
	original_prompt: string;
}

export interface ApiError {
	detail: string;
}

// Batch generation types

export interface BatchGenerateRequest {
	prompt: string;
	count: number;
	width?: number;
	height?: number;
	skip_enhance?: boolean;
	seed?: number | null;
	num_inference_steps?: number;
	output_format?: 'svg' | 'png';
}

export interface BatchProgressEvent {
	event: 'progress';
	index: number;
	total: number;
	stage: 'generating' | 'vectorizing' | 'optimizing';
}

export interface BatchResultEvent {
	event: 'result';
	index: number;
	total: number;
	result: GenerateResponse;
}

export interface BatchDoneEvent {
	event: 'done';
	total: number;
	prompt_used: string;
}

export interface BatchErrorEvent {
	event: 'error';
	index: number;
	total: number;
	detail: string;
}

export type BatchEvent = BatchProgressEvent | BatchResultEvent | BatchDoneEvent | BatchErrorEvent;

export interface GalleryItem {
	index: number;
	status: 'pending' | 'generating' | 'vectorizing' | 'optimizing' | 'done' | 'error';
	result: GenerateResponse | null;
	error: string | null;
}
