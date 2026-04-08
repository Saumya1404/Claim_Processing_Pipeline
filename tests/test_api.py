from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_process_endpoint_returns_aggregated_response(monkeypatch) -> None:
    def fake_write_pdf_to_temp_file(file_bytes: bytes):
        return "/tmp/fake-claim.pdf"

    def fake_delete_temp_pdf(pdf_path: str):
        return None

    def fake_graph_invoke(state):
        return {
            "final_response": {
                "claim_id": state["claim_id"],
                "identity": {},
                "discharge_summary": {},
                "billing": {},
                "pipeline_metadata": {},
            }
        }

    monkeypatch.setattr("app.main.write_pdf_to_temp_file", fake_write_pdf_to_temp_file)
    monkeypatch.setattr("app.main.delete_temp_pdf", fake_delete_temp_pdf)
    monkeypatch.setattr("app.main.app_graph.invoke", fake_graph_invoke)

    response = client.post(
        "/api/process",
        data={"claim_id": "C-100"},
        files={"file": ("claim.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["claim_id"] == "C-100"
