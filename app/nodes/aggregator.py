from __future__ import annotations

from typing import Any


def aggregator_node(state: dict[str, Any]) -> dict[str, Any]:
    classified_pages = state.get("classified_pages", {})
    page_presence = {
        "identity_or_claim_form_pages": sorted(
            set(classified_pages.get("identity_document", []) + classified_pages.get("claim_forms", []))
        ),
        "discharge_summary_pages": sorted(classified_pages.get("discharge_summary", [])),
        "billing_or_receipt_pages": sorted(
            set(classified_pages.get("itemized_bill", []) + classified_pages.get("cash_receipt", []))
        ),
    }

    response = {
        "claim_id": state.get("claim_id", ""),
        "identity": state.get(
            "id_data",
            {
                "patient_name": "",
                "dob": "",
                "id_number": "",
                "policy_number": "",
            },
        ),
        "discharge_summary": state.get(
            "discharge_data",
            {
                "diagnosis": "",
                "admission_date": "",
                "discharge_date": "",
                "doctor_name": "",
            },
        ),
        "billing": state.get(
            "bill_data",
            {
                "items": [],
                "total_amount": 0,
            },
        ),
        "pipeline_metadata": {
            "pdf_path": state.get("pdf_path", ""),
            "classified_pages": classified_pages,
            "segregator": state.get("segregator_metadata", {}),
            "page_presence": page_presence,
            "errors": state.get("errors", []),
        },
    }

    return {"final_response": response}
