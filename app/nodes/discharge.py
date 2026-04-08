from __future__ import annotations

from typing import Any

from app.utils.gemini_client import generate_json
from app.utils.pdf_loader import render_pdf_pages_as_base64


def discharge_node(state: dict[str, Any]) -> dict[str, Any]:
    pages = state.get("classified_pages", {}).get("discharge_summary", [])
    pdf_path = state.get("pdf_path")
    errors = list(state.get("errors", []))
    default_output = {
        "diagnosis": "",
        "admission_date": "",
        "discharge_date": "",
        "doctor_name": "",
    }

    if not pages or not pdf_path:
        return {"discharge_data": default_output}

    try:
        rendered_pages = render_pdf_pages_as_base64(pdf_path=pdf_path, page_numbers=pages)
    except ValueError as exc:
        errors.append(f"discharge_agent: {exc}")
        return {"discharge_data": default_output, "errors": errors}

    routed_images = [page["image_base64"] for page in rendered_pages]

    if not routed_images:
        return {"discharge_data": default_output}

    prompt = (
        "Extract discharge summary fields from the provided pages. "
        "Return strict JSON only with keys: diagnosis, admission_date, discharge_date, doctor_name. "
        "If a field is missing, return empty string."
    )
    extracted = generate_json(
        prompt=prompt,
        image_b64_list=routed_images,
        default=default_output,
    )

    return {"discharge_data": {**default_output, **extracted}}
