# VecSmith

An open-source text-to-SVG generation pipeline. Turn natural language prompts into production-ready SVG vector graphics using LLM prompt enhancement, Flux image generation, and vtracer vectorization.

```
"a geometric fox logo" ──> LLM Enhancement ──> Flux Image Gen ──> vtracer ──> SVG
                            (optional)          (GPU)             (CPU)
```

## How It Works

VecSmith chains four stages into a single API call:

| Stage | What It Does | Runs On | Time |
|-------|-------------|---------|------|
| **1. Prompt Enhancement** | An LLM expands your brief prompt into a detailed, SVG-optimized description | Any OpenAI-compatible API | ~2s |
| **2. Image Generation** | FLUX.1-schnell generates a high-quality raster image from the enhanced prompt | NVIDIA GPU | ~10-15s |
| **3. Vectorization** | vtracer converts the raster image into SVG paths | CPU | ~0.05s |
| **4. SVG Optimization** | Cleans up the SVG: rounds coordinates, strips comments, ensures viewBox | CPU | <0.01s |

**Total pipeline time: ~12-20 seconds** for a 1024x1024 SVG.

## Features

- **Single API endpoint** — `POST /generate` returns a complete SVG
- **Batch generation** — Generate multiple variations via SSE streaming
- **PNG output mode** — Skip vectorization and get raster output directly
- **Flexible LLM backend** — Works with any OpenAI-compatible API (Ollama, vLLM, LiteLLM, OpenAI, etc.)
- **Skip enhancement** — Pass `skip_enhance: true` to use your own prompts directly
- **Web UI** — Built-in SvelteKit frontend for interactive generation
- **Kubernetes-ready** — Example manifests included for GPU cluster deployment

## Quick Start

### Prerequisites

- Python 3.11+
- An NVIDIA GPU with 16GB+ VRAM (for the Flux server)
- An OpenAI-compatible LLM endpoint (optional, for prompt enhancement)

### Local Development

```bash
# 1. Install the orchestrator
make install

# 2. Install the Flux server (requires CUDA)
make install-flux

# 3. Start the Flux server (in one terminal)
make dev-flux

# 4. Start the orchestrator (in another terminal)
make dev

# 5. Generate your first SVG
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a minimalist mountain landscape logo"}'
```

### Docker

```bash
# Build images
make build

# Or build individually
make build-orchestrator
make build-flux
```

### Frontend

```bash
make frontend-install
make frontend-dev
# Opens http://localhost:5173
```

## API Reference

### `POST /generate`

Generate a single SVG from a text prompt.

**Request:**

```json
{
  "prompt": "a geometric fox logo",
  "width": 1024,
  "height": 1024,
  "skip_enhance": false,
  "seed": null,
  "num_inference_steps": 4,
  "output_format": "svg"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | string | (required) | Text description (1-2000 chars) |
| `width` | int | 1024 | Image width (256-2048) |
| `height` | int | 1024 | Image height (256-2048) |
| `skip_enhance` | bool | false | Skip LLM prompt enhancement |
| `seed` | int\|null | null | Random seed for reproducibility |
| `num_inference_steps` | int | 4 | Diffusion steps (4 is optimal for FLUX.1-schnell) |
| `output_format` | string | "svg" | `"svg"` or `"png"` |

**Response:**

```json
{
  "svg": "<svg ...>...</svg>",
  "png_base64": null,
  "output_format": "svg",
  "prompt_used": "A minimalist geometric fox logo rendered in...",
  "original_prompt": "a geometric fox logo",
  "timings": {
    "prompt_enhance_s": 2.41,
    "image_generate_s": 14.12,
    "vectorize_s": 0.04,
    "svg_optimize_s": 0.002,
    "total_s": 16.57
  },
  "svg_size_bytes": 16043
}
```

### `POST /generate/svg-only`

Returns raw SVG as `image/svg+xml` (same request body as `/generate`).

### `POST /generate/batch`

Generate multiple variations via Server-Sent Events.

**Request:**

```json
{
  "prompt": "a geometric fox logo",
  "count": 4,
  "seed": 42
}
```

**SSE Events:**

- `progress` — Stage updates for each variation
- `result` — Completed SVG for each variation
- `done` — All variations complete
- `error` — If a variation fails

### `GET /health`

Health check endpoint.

## Configuration

All settings are configured via environment variables with the `VECSMITH_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `VECSMITH_LLM_BASE_URL` | `http://localhost:8080/v1` | OpenAI-compatible LLM endpoint |
| `VECSMITH_LLM_MODEL` | `default` | Model name for prompt enhancement |
| `VECSMITH_LLM_API_KEY` | (empty) | API key for authenticated endpoints |
| `VECSMITH_LLM_MAX_TOKENS` | `300` | Max tokens for enhanced prompt |
| `VECSMITH_LLM_TEMPERATURE` | `0.7` | LLM sampling temperature |
| `VECSMITH_FLUX_BASE_URL` | `http://localhost:8081` | Flux server endpoint |
| `VECSMITH_FLUX_STEPS` | `4` | Diffusion steps |
| `VECSMITH_VTRACER_FILTER_SPECKLE` | `4` | Noise reduction threshold |
| `VECSMITH_VTRACER_COLOR_PRECISION` | `6` | Color quantization (2^n colors per channel) |
| `VECSMITH_SVG_COORDINATE_PRECISION` | `2` | Decimal places in SVG coordinates |
| `VECSMITH_HOST` | `0.0.0.0` | Orchestrator bind address |
| `VECSMITH_PORT` | `8080` | Orchestrator bind port |

### Flux Server

| Variable | Default | Description |
|----------|---------|-------------|
| `FLUX_HOST` | `0.0.0.0` | Flux server bind address |
| `FLUX_PORT` | `8081` | Flux server bind port |
| `HF_HOME` | `/models/flux` | HuggingFace model cache directory |
| `HF_TOKEN` | (empty) | HuggingFace token (for gated models) |

## LLM Backend Options

VecSmith's prompt enhancement works with any OpenAI-compatible `/v1/chat/completions` endpoint. Some options:

| Backend | Use Case | Setup |
|---------|----------|-------|
| [Ollama](https://ollama.ai) | Easiest local setup | `VECSMITH_LLM_BASE_URL=http://localhost:11434/v1` |
| [vLLM](https://github.com/vllm-project/vllm) | High-throughput GPU inference | `VECSMITH_LLM_BASE_URL=http://localhost:8000/v1` |
| [LiteLLM](https://github.com/BerriAI/litellm) | Proxy to any LLM provider | `VECSMITH_LLM_BASE_URL=http://localhost:4000/v1` |
| [LLMKube](https://github.com/defilantech/LLMKube) | Kubernetes-native LLM inference | Deploy as InferenceService |
| OpenAI API | Cloud-hosted | `VECSMITH_LLM_BASE_URL=https://api.openai.com/v1` |

Or skip enhancement entirely with `skip_enhance: true` in your requests.

## Architecture

```
                    ┌─────────────────────────────────┐
                    │          VecSmith API            │
                    │       (FastAPI orchestrator)     │
                    │            :8080                 │
                    └─────┬──────────────┬────────────┘
                          │              │
                ┌─────────▼──────┐  ┌────▼─────────────┐
                │   LLM Service  │  │   Flux Server     │
                │  (any OpenAI-  │  │  (FLUX.1-schnell) │
                │   compatible)  │  │  NVIDIA GPU       │
                │    :8080/v1    │  │    :8081           │
                └────────────────┘  └──────────────────┘
```

The orchestrator is stateless and CPU-only. It coordinates calls to:
1. An external LLM for prompt enhancement (optional)
2. The Flux server for image generation (requires NVIDIA GPU)
3. Built-in vtracer for vectorization (CPU, in-process)
4. Built-in SVG optimizer (CPU, in-process)

## Kubernetes Deployment

Example manifests are provided in `deploy/k8s/`. Edit the image references and LLM configuration, then:

```bash
# Deploy
make deploy

# Check status
make status

# View logs
make logs-orchestrator
make logs-flux
```

See `deploy/k8s/orchestrator/deployment.yaml` for LLM configuration examples.

### GPU Requirements

The Flux server requires:
- 1x NVIDIA GPU with 16GB+ VRAM
- NVIDIA device plugin for Kubernetes
- CUDA 12.4+ runtime

The model (~12GB) is cached in a PersistentVolumeClaim. First startup downloads the model and takes 2-3 minutes; subsequent startups load from cache in ~30 seconds.

## Testing

```bash
# Install test dependencies
make install-test

# Run all tests
make test

# Run unit tests only
make test-unit

# Lint
make lint
```

### End-to-End Test

With the pipeline running:

```bash
./scripts/test_pipeline_e2e.sh http://localhost:8080
```

## Project Structure

```
vecsmith/
├── src/
│   ├── orchestrator/       # FastAPI app, routes, pipeline logic
│   │   ├── app.py          # App factory
│   │   ├── routes.py       # API endpoints
│   │   ├── pipeline.py     # Pipeline orchestration
│   │   ├── batch.py        # Batch generation (SSE)
│   │   └── schemas.py      # Pydantic models
│   ├── stages/             # Pipeline stages
│   │   ├── prompt_enhance.py   # LLM prompt enhancement
│   │   ├── image_generate.py   # Flux client
│   │   ├── vectorize.py        # vtracer wrapper
│   │   └── svg_optimize.py     # SVG cleanup
│   └── flux_server/        # Standalone Flux inference server
│       ├── server.py        # FastAPI server
│       └── model_loader.py  # CUDA model management
├── tests/                  # pytest test suite
├── frontend/               # SvelteKit web UI
├── docker/                 # Dockerfiles
├── deploy/k8s/             # Example Kubernetes manifests
├── scripts/                # Development and test scripts
└── requirements.txt        # Python dependencies
```

## Models

VecSmith uses [FLUX.1-schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell) by Black Forest Labs, licensed under Apache 2.0. The model is downloaded automatically on first startup.

## Contributing

Contributions are welcome! Please open an issue to discuss your idea before submitting a PR.

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
