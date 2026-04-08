from __future__ import annotations

from typing import Any

from app.utils.gemini_client import generate_json
from app.utils.pdf_loader import render_pdf_pages_as_base64


def id_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    classified = state.get("classified_pages", {})
    pages = sorted(
        set(classified.get("identity_document", []) + classified.get("claim_forms", []))
    )
    pdf_path = state.get("pdf_path")
    errors = list(state.get("errors", []))
    default_output = {
        "patient_name": "",
        "dob": "",
        "id_number": "",
        "policy_number": "",
    }

    if not pages or not pdf_path:
        return {"id_data": default_output}

    try:
        rendered_pages = render_pdf_pages_as_base64(pdf_path=pdf_path, page_numbers=pages)
    except ValueError as exc:
        errors.append(f"id_agent: {exc}")
        return {"id_data": default_output, "errors": errors}

    routed_images = [page["image_base64"] for page in rendered_pages]

    if not routed_images:
        return {"id_data": default_output}

    prompt = (
        "Extract identity fields from the provided identity document pages. "
        "Return strict JSON only with keys: patient_name, dob, id_number, policy_number. "
        "If a field is missing, return empty string."
    )
    extracted = generate_json(
        prompt=prompt,
        image_b64_list=routed_images,
        default=default_output,
    )

    return {"id_data": {**default_output, **extracted}}
