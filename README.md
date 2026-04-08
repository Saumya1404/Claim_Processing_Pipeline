# Claim Processing Pipeline

FastAPI + LangGraph for claim PDF page classification and routed extraction.

## Overview

This project processes a claim PDF through a graph pipeline:

1. Classify pages by document type.
2. Run specialized extractors in parallel.
3. Aggregate extracted outputs into a single final response.

Core graph definition is in `app/graph.py`.

---

## Graph Structure (ASCII)

```text
                +-------+
                | START |
                +-------+
                    |
                    v
        +-------------------------+
        |     segregator_node     |
        +-------------------------+
            /         |         \
           v          v          v
+----------------+ +----------------+ +----------------+
| id_agent_node  | | discharge_node | |   bill_node    |
+----------------+ +----------------+ +----------------+
           \          |          /
            \         |         /
             v        v        v
        +-------------------------+
        |     aggregator_node     |
        +-------------------------+
                    |
                    v
                +-------+
                |  END  |
                +-------+
```

---

## Segment Details

### `segregator_node`
- Renders all PDF pages.
- Classifies pages into categories (ID, discharge, bill).
- Stores classification map in state.

### `id_agent_node`
- Processes ID-assigned pages.
- Extracts identity-related information.

### `discharge_node`
- Processes discharge-assigned pages.
- Extracts discharge summary details.

### `bill_node`
- Processes bill-assigned pages.
- Extracts billing and charge details.

### `aggregator_node`
- Merges extractor outputs.
- Adds metadata (`classified_pages`, pages found, errors).
- Produces final response payload.

---

## State Model (`ClaimState`)

Shared graph state includes:

- `claim_id`
- `pdf_path`
- `classified_pages`
- `segregator_metadata`
- `id_data`
- `discharge_data`
- `bill_data`
- `errors`
- `final_response`

Defined in `app/graph.py`.

---

## Setup

1. Add your Gemini key to secrets as `GEMINI_API_KEY_2`.
2. Models are hardcoded:
   - Primary: `gemini-2.5-flash-lite`
   - Fallback: `gemini-2.5-flash`
   - Retry attempts: `1`
3. OCR/text controls:
   - `OCR_ENABLED=true|false` (default: `true`)
   - `LLM_USE_IMAGES=true|false` (default: `true`)
   - Set `LLM_USE_IMAGES=false` for OCR-text-only requests.
   - With `LLM_USE_IMAGES=true`, OCR runs as second-pass fallback.
4. Install deps and run:

```bash
uv sync
uv run uvicorn app.main:app --reload
```

---

## Endpoint

- `POST /api/process`
- Multipart fields:
  - `claim_id` (string)
  - `file` (PDF)

---

## Data Flow

1. HTTP ingress validates PDF bytes and writes a temp PDF file.
2. Segregator renders all pages via PyMuPDF and classifies in one Gemini call.
3. ID, discharge, and bill nodes run in parallel; each re-renders assigned pages and performs one targeted Gemini call.
4. Aggregator combines node outputs and pipeline metadata.
5. API returns final JSON and deletes temp PDF.

Expected Gemini usage per request: **4 calls**  
(1 classification + 3 extraction calls).
