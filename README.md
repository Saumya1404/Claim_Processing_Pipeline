# Claim_Processing_Pipeline

FastAPI + LangGraph service for claim PDF page classification and routed extraction.

## Setup

1. Add your Gemini key to secrets as `GEMINI_API_KEY_2`.
2. Models are hardcoded in code:
	- Primary: `gemini-2.5-flash-lite`
	- Fallback: `gemini-2.5-flash`
	- Retry attempts: `1`
3. OCR/text controls:
	- `OCR_ENABLED=true|false` (default: `true`)
	- `LLM_USE_IMAGES=true|false` (default: `true`)
	- Set `LLM_USE_IMAGES=false` to run OCR-text-only requests (useful for text-only models).
	- With `LLM_USE_IMAGES=true`, OCR runs only as a second-pass fallback to reduce request latency.
4. Install deps and run:

```bash
uv sync
uv run uvicorn app.main:app --reload
```

## Endpoint

- `POST /api/process`
- multipart fields:
	- `claim_id` (string)
	- `file` (PDF)

## Data Flow

1. HTTP ingress validates PDF bytes and writes a temp PDF file.
2. Segregator renders all pages via PyMuPDF, sends the image batch in a single Gemini call (primary `gemini-2.5-flash-lite`, fallback `gemini-2.5-flash`), and stores only the classification map in state.
3. ID, discharge, and bill nodes fan out in parallel; each node re-renders only its assigned pages and performs one targeted Gemini call.
4. Aggregator fans in results and adds pipeline metadata (classified pages, pages found, and errors).
5. API returns final JSON and deletes the temp PDF.

Expected Gemini usage is 4 calls per request: 1 classification + 3 extraction calls.