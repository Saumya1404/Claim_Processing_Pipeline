from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.graph import app_graph
from app.utils.pdf_loader import delete_temp_pdf, validate_pdf_input, write_pdf_to_temp_file

app = FastAPI(title="Claim Processing Pipeline")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/process")
async def process_claim(claim_id: str = Form(...), file: UploadFile = File(...)) -> dict:
    file_bytes = await file.read()
    pdf_path: str | None = None

    try:
        validate_pdf_input(file_bytes=file_bytes, content_type=file.content_type)
        pdf_path = write_pdf_to_temp_file(file_bytes=file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        state = {
            "claim_id": claim_id,
            "pdf_path": pdf_path,
            "errors": [],
        }
        result = app_graph.invoke(state)
        return result.get("final_response", {})
    finally:
        delete_temp_pdf(pdf_path)
