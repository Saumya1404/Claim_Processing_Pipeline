from __future__ import annotations

import base64
import os
import tempfile
from typing import TypedDict

import fitz


class RenderedPage(TypedDict):
    page_number: int
    image_base64: str


def validate_pdf_input(file_bytes: bytes, content_type: str | None) -> None:
    if not file_bytes:
        raise ValueError("Uploaded PDF is empty.")

    if content_type and content_type != "application/pdf":
        raise ValueError("Invalid file type. Please upload a PDF.")

    if not file_bytes.startswith(b"%PDF"):
        raise ValueError("Invalid PDF content.")


def write_pdf_to_temp_file(file_bytes: bytes) -> str:
    temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        temp_file.write(file_bytes)
        temp_file.flush()
    finally:
        temp_file.close()

    return temp_file.name


def delete_temp_pdf(pdf_path: str | None) -> None:
    if not pdf_path:
        return

    try:
        os.remove(pdf_path)
    except FileNotFoundError:
        return


def render_pdf_pages_as_base64(
    pdf_path: str,
    page_numbers: list[int] | None = None,
    zoom: float = 2.0,
) -> list[RenderedPage]:
    try:
        document = fitz.open(pdf_path)
    except Exception as exc:
        raise ValueError("Unable to parse PDF. The file may be corrupt.") from exc

    try:
        if document.page_count == 0:
            raise ValueError("No pages found in uploaded PDF.")

        if page_numbers is None:
            selected_pages = list(range(document.page_count))
        else:
            selected_pages = sorted(set(page_numbers))

        rendered_pages: list[RenderedPage] = []
        matrix = fitz.Matrix(zoom, zoom)
        for page_index in selected_pages:
            if page_index < 0 or page_index >= document.page_count:
                continue

            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix)
            image_bytes = pixmap.tobytes("png")
            rendered_pages.append(
                {
                    "page_number": page_index,
                    "image_base64": base64.b64encode(image_bytes).decode("ascii"),
                }
            )

        return rendered_pages
    finally:
        document.close()
