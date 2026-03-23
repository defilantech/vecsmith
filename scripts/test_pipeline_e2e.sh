#!/usr/bin/env bash
# End-to-end integration test against a running VecSmith pipeline.
# Usage: ./scripts/test_pipeline_e2e.sh [BASE_URL]
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"

echo "=== VecSmith E2E Test ==="
echo "Target: $BASE_URL"
echo ""

# Test 1: Health check
echo "--- Test 1: Health check ---"
HEALTH=$(curl -sf "$BASE_URL/health")
echo "$HEALTH" | python3 -m json.tool
echo ""

# Test 2: Generate SVG (with prompt enhancement)
echo "--- Test 2: Generate SVG (full pipeline) ---"
RESULT=$(curl -sf -X POST "$BASE_URL/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a friendly cat sitting on a windowsill watching birds outside"}')

echo "$RESULT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'  Original prompt: {data[\"original_prompt\"]}')
print(f'  Enhanced prompt: {data[\"prompt_used\"][:80]}...')
print(f'  SVG size: {data[\"svg_size_bytes\"]} bytes')
print(f'  Timings:')
t = data['timings']
if t.get('prompt_enhance_s'): print(f'    Prompt enhance: {t[\"prompt_enhance_s\"]}s')
print(f'    Image generate: {t[\"image_generate_s\"]}s')
print(f'    Vectorize:      {t[\"vectorize_s\"]}s')
print(f'    SVG optimize:   {t[\"svg_optimize_s\"]}s')
print(f'    Total:          {t[\"total_s\"]}s')
"

# Save the SVG
echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['svg'])" > /tmp/e2e_test_output.svg
echo "  SVG saved to: /tmp/e2e_test_output.svg"
echo ""

# Test 3: Generate SVG-only (raw SVG response)
echo "--- Test 3: Generate SVG-only (skip_enhance) ---"
SVG=$(curl -sf -X POST "$BASE_URL/generate/svg-only" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a simple red star icon, vector illustration style, flat design", "skip_enhance": true}')

SVG_LEN=${#SVG}
echo "  SVG length: $SVG_LEN chars"
echo "  Starts with: ${SVG:0:80}..."
echo ""

# Summary
echo "=== All E2E tests passed ==="
