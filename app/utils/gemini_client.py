from __future__ import annotations

import base64
from io import BytesIO
import json
import os
import re
import time
from functools import lru_cache
from typing import Any

from google import genai
from google.genai import types
from PIL import Image
import pytesseract

DEFAULT_MODEL = "gemini-2.5-flash-lite"
FALLBACK_MODELS = ["gemini-2.5-flash"]
RETRY_ATTEMPTS = 1
RETRY_BACKOFF_BASE_SECONDS = 0.35
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() != "false"
OCR_LANG = os.getenv("OCR_LANG", "eng")
OCR_MAX_CHARS_PER_PAGE = int(os.getenv("OCR_MAX_CHARS_PER_PAGE", "2000"))
LLM_USE_IMAGES = os.getenv("LLM_USE_IMAGES", "true").lower() != "false"


def _candidate_models() -> list[str]:
    # Keep order stable and unique: configured/default model first, then fallbacks.
    models = [DEFAULT_MODEL, *FALLBACK_MODELS]
    deduped: list[str] = []
    for model in models:
        if model and model not in deduped:
            deduped.append(model)
    return deduped


def _is_gemma_model(model: str) -> bool:
    return "gemma" in model.lower()


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()

    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def _extract_ocr_context(image_b64_list: list[str]) -> str:
    if not OCR_ENABLED or not image_b64_list:
        return ""

    chunks: list[str] = []
    for idx, image_b64 in enumerate(image_b64_list):
        try:
            image = Image.open(BytesIO(base64.b64decode(image_b64)))
            text = pytesseract.image_to_string(image, lang=OCR_LANG, config="--oem 1 --psm 6")
            normalized = re.sub(r"\s+", " ", text).strip()
            if normalized:
                chunks.append(f"page_{idx}: {normalized[:OCR_MAX_CHARS_PER_PAGE]}")
        except Exception:
            continue

    return "\n".join(chunks)


def _build_parts(prompt_text: str, image_b64_list: list[str], send_images: bool) -> list[types.Part]:
    parts: list[types.Part] = [types.Part.from_text(text=prompt_text)]
    if send_images:
        for image_b64 in image_b64_list:
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(image_b64),
                    mime_type="image/png",
                )
            )
    return parts


def _run_generation_attempts(
    client: genai.Client,
    prompt_text: str,
    image_b64_list: list[str],
    will_send_images: bool,
) -> tuple[dict[str, Any] | None, Exception | None]:
    last_error: Exception | None = None

    for model in _candidate_models():
        model_uses_images = will_send_images and not _is_gemma_model(model)
        parts = _build_parts(
            prompt_text=prompt_text,
            image_b64_list=image_b64_list,
            send_images=model_uses_images,
        )

        if _is_gemma_model(model):
            generation_config = types.GenerateContentConfig(
                temperature=0,
            )
        else:
            generation_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            )

        model_returned_non_json = False
        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[types.Content(role="user", parts=parts)],
                    config=generation_config,
                )
                text = getattr(response, "text", "") or ""
                parsed = _extract_json_object(text)
                if parsed is not None:
                    return parsed, last_error

                # Non-JSON output can happen under overload/content filter behavior.
                print(
                    f"[Gemini] Non-JSON response from model={model}; trying next model."
                )
                model_returned_non_json = True
                break
            except Exception as exc:
                last_error = exc
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_BACKOFF_BASE_SECONDS * (2**attempt))

        if not model_returned_non_json:
            print(f"[Gemini] Model failed after retries: {model}; trying fallback.")

    return None, last_error


@lru_cache(maxsize=1)
def get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY_2")
    if not api_key:
        raise RuntimeError(
            "Missing Gemini API key. Set GEMINI_API_KEY_2 in secrets."
        )

    return genai.Client(api_key=api_key)


def generate_json(
    prompt: str,
    image_b64_list: list[str],
    default: dict[str, Any],
) -> dict[str, Any]:
    client = get_gemini_client()
    will_send_images = LLM_USE_IMAGES and bool(image_b64_list)

    # First pass for multimodal flow: skip OCR to keep latency low.
    first_prompt = prompt

    # For text-only flow, OCR is needed up front because images are not sent.
    if not will_send_images and OCR_ENABLED and image_b64_list:
        ocr_context = _extract_ocr_context(image_b64_list)
        if ocr_context:
            first_prompt = (
                f"{first_prompt}\n\n"
                "Additional OCR text extracted from the same images (best effort):\n"
                f"{ocr_context}\n\n"
                "Images are intentionally not provided for this request. "
                "Use only the OCR text context above and still return strict JSON."
            )

    parsed, last_error = _run_generation_attempts(
        client=client,
        prompt_text=first_prompt,
        image_b64_list=image_b64_list,
        will_send_images=will_send_images,
    )
    if parsed is not None:
        return parsed

    # Second pass only when images are enabled and first pass failed.
    if will_send_images and OCR_ENABLED and image_b64_list:
        ocr_context = _extract_ocr_context(image_b64_list)
        if ocr_context:
            ocr_prompt = (
                f"{prompt}\n\n"
                "Additional OCR text extracted from the same images (best effort):\n"
                f"{ocr_context}\n\n"
                "Use OCR text only as a helper and prioritize visual evidence from the images."
            )
            parsed, last_error = _run_generation_attempts(
                client=client,
                prompt_text=ocr_prompt,
                image_b64_list=image_b64_list,
                will_send_images=will_send_images,
            )
            if parsed is not None:
                return parsed

    print(f"[Gemini] All model attempts failed; using default. Last error: {last_error}")
    return default
