from collections import defaultdict
import re
from typing import Any

from app.utils.gemini_client import generate_json
from app.utils.pdf_loader import render_pdf_pages_as_base64

SEGREGATION_TYPES = [
    "claim_forms",
    "cheque_or_bank_details",
    "identity_document",
    "itemized_bill",
    "discharge_summary",
    "prescription",
    "investigation_report",
    "cash_receipt",
    "other",
]


def _normalize_page_index(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
        match = re.search(r"\d+", stripped)
        if match:
            return int(match.group(0))
    return None


def segregator_node(state: dict[str, Any]) -> dict[str, Any]:
    pdf_path = state.get("pdf_path")
    classified_pages: dict[str, list[int]] = defaultdict(list)
    errors = list(state.get("errors", []))

    if not pdf_path:
        errors.append("segregator: missing pdf_path in state")
        for category in SEGREGATION_TYPES:
            classified_pages.setdefault(category, [])
        return {
            "classified_pages": dict(classified_pages),
            "segregator_metadata": {"total_pages": 0, "classified_pages_count": 0},
            "errors": errors,
        }

    try:
        rendered_pages = render_pdf_pages_as_base64(pdf_path=pdf_path)
    except ValueError as exc:
        errors.append(f"segregator: {exc}")
        rendered_pages = []

    page_numbers = [page["page_number"] for page in rendered_pages]
    image_b64_list = [page["image_base64"] for page in rendered_pages]

    classification_default: dict[str, Any] = {
        "classified_pages": {
            "other": page_numbers,
        }
    }

    if image_b64_list:
        prompt = f"""
You are a medical insurance document classification system.

You are given multiple PDF pages as images in order (0-indexed).

Classify EACH page into EXACTLY ONE of these categories:
{', '.join(SEGREGATION_TYPES)}

Return STRICT JSON in this format:
{{
"classified_pages": {{
"claim_forms": [],
"cheque_or_bank_details": [],
"identity_document": [],
"itemized_bill": [],
"discharge_summary": [],
"prescription": [],
"investigation_report": [],
"cash_receipt": [],
"other": []
}}
}}

Rules:

* Every page number MUST appear exactly once
* Page numbers are 0-indexed
* Do NOT skip any page
* Do NOT include explanations
* Only output valid JSON

Examples:

* Aadhaar card -> identity_document
* Hospital bill -> itemized_bill
* Discharge summary -> discharge_summary
* Lab report -> investigation_report
* Medicine prescription -> prescription
* Payment receipt -> cash_receipt
"""

        result = generate_json(
            prompt=prompt,
            image_b64_list=image_b64_list,
            default=classification_default,
        )
    else:
        result = classification_default

    returned_map = result.get("classified_pages", {})
    if not isinstance(returned_map, dict):
        returned_map = {}

    assigned_pages: set[int] = set()

    for doc_type, pages in returned_map.items():
        if doc_type not in SEGREGATION_TYPES or not isinstance(pages, list):
            continue

        for page_index in pages:
            normalized_index = _normalize_page_index(page_index)
            if (
                normalized_index is not None
                and normalized_index in page_numbers
                and normalized_index not in assigned_pages
            ):
                classified_pages[doc_type].append(normalized_index)
                assigned_pages.add(normalized_index)

    for page_index in page_numbers:
        if page_index not in assigned_pages:
            classified_pages["other"].append(page_index)

    for category in SEGREGATION_TYPES:
        classified_pages[category] = sorted(classified_pages.get(category, []))

    print("[Segregator] Classified:", dict(classified_pages))

    return {
        "classified_pages": dict(classified_pages),
        "segregator_metadata": {
            "total_pages": len(page_numbers),
            "classified_pages_count": len(assigned_pages)
            if assigned_pages
            else len(page_numbers),
            "document_types_found": [
                doc_type for doc_type in SEGREGATION_TYPES if classified_pages[doc_type]
            ],
        },
        "errors": errors,
    }
