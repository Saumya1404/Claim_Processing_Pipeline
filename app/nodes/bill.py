from __future__ import annotations

from typing import Any

from app.utils.gemini_client import generate_json
from app.utils.pdf_loader import render_pdf_pages_as_base64


def _compute_total(items: list[dict[str, Any]]) -> float:
    try:
        return sum(float(item.get("cost", 0)) for item in items)
    except Exception:
        return 0.0


def bill_node(state: dict[str, Any]) -> dict[str, Any]:
    classified = state.get("classified_pages", {})
    pdf_path = state.get("pdf_path")
    errors = list(state.get("errors", []))

    pages = sorted(
        set(
            classified.get("itemized_bill", [])
            + classified.get("cash_receipt", [])
            + classified.get("cheque_or_bank_details", [])
        )
    )

    default_output = {
        "items": [],
        "total_amount": 0.0,
    }

    if not pages or not pdf_path:
        return {"bill_data": default_output}

    try:
        rendered_pages = render_pdf_pages_as_base64(
            pdf_path=pdf_path,
            page_numbers=pages,
        )
    except ValueError as exc:
        errors.append(f"bill_agent: {exc}")
        return {"bill_data": default_output, "errors": errors}

    routed_images = [page["image_base64"] for page in rendered_pages]

    if not routed_images:
        return {"bill_data": default_output}

    prompt = """
You are a medical billing extraction system.

Analyze the provided document pages and extract ALL billing-related information.

These pages may include:

* Hospital itemized bills
* Pharmacy bills
* Cash receipts
* Financial summaries

Instructions:

* Extract ALL monetary values
* Extract line items if present
* If multiple bills exist, include all
* If totals exist, capture them
* If multiple totals exist, SUM them

Return STRICT JSON in this format:
{
"items": [
{"description": "string", "cost": number}
],
"total_amount": number
}

Rules:

* cost and total_amount must be numbers
* Do NOT return any text outside JSON
* If no items found, return empty list
* If no total found, return 0
"""

    extracted = generate_json(
        prompt=prompt,
        image_b64_list=routed_images,
        default=default_output,
    )

    if not extracted.get("items") and extracted.get("total_amount", 0) == 0:
        retry_prompt = prompt + "\nReturn ONLY valid JSON. No explanation."
        extracted = generate_json(
            prompt=retry_prompt,
            image_b64_list=routed_images,
            default=default_output,
        )

    items = extracted.get("items", [])
    total = extracted.get("total_amount", 0)

    if (not total or total == 0) and items:
        total = _compute_total(items)

    normalized = {
        "items": items,
        "total_amount": round(float(total), 2) if total else 0.0,
    }

    print("[Bill Node] Pages:", pages)
    print("[Bill Node] Extracted:", extracted)
    print("[Bill Node] Final:", normalized)

    return {"bill_data": normalized}
