from app.graph import app_graph


def test_graph_returns_stable_top_level_keys() -> None:
    state = {
        "claim_id": "C-1",
        "pdf_path": "/tmp/fake.pdf",
        "classified_pages": {
            "claim_forms": [],
            "cheque_or_bank_details": [],
            "identity_document": [],
            "itemized_bill": [],
            "discharge_summary": [],
            "prescription": [],
            "investigation_report": [],
            "cash_receipt": [],
            "other": [],
        },
    }

    result = app_graph.invoke(state)
    payload = result["final_response"]

    assert set(payload.keys()) == {
        "claim_id",
        "identity",
        "discharge_summary",
        "billing",
        "pipeline_metadata",
    }
    assert payload["claim_id"] == "C-1"
