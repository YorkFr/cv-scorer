from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from .pdf_to_markdown import PDFMarkdownExtractor, PDFToMarkdownConfig
from .pdf_to_png import PDFToPNGConfig, PDFToPNGRenderer
from .png_to_markdown import DEFAULT_PROMPT, OCRServiceClient, PNGToMarkdownConfig
from .scoring import score_markdown


DEFAULT_MODEL = os.getenv("OCR_MODEL", "lightonai/LightOnOCR-2-1B")
DEFAULT_OCR_BASE_URL = os.getenv("OCR_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", "300"))
DEFAULT_DPI = 200
MAX_PROMPT_LENGTH = 8000
MAX_MARKDOWN_LENGTH = 200000

app = FastAPI(title="CV Scorer Backend API", version="0.1.0")


def _ensure_pdf(upload: UploadFile) -> None:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported.")


def _ensure_image(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg"}:
        raise HTTPException(status_code=400, detail="Only PNG or JPEG uploads are supported.")
    return "jpeg" if suffix in {".jpg", ".jpeg"} else "png"


def _validate_dpi(dpi: int) -> None:
    if dpi < 72 or dpi > 300:
        raise HTTPException(status_code=400, detail="dpi must be between 72 and 300.")


def _validate_prompt(prompt: str) -> None:
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"prompt must be at most {MAX_PROMPT_LENGTH} characters.",
        )


def _validate_markdown(markdown: str) -> None:
    if not markdown.strip():
        raise HTTPException(status_code=400, detail="markdown must not be empty.")
    if len(markdown) > MAX_MARKDOWN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"markdown must be at most {MAX_MARKDOWN_LENGTH} characters.",
        )


def _ocr_client(
    model: str,
    prompt: str,
    image_format: str,
    api_key: str = "",
    base_url: str = DEFAULT_OCR_BASE_URL,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> OCRServiceClient:
    return OCRServiceClient(
        PNGToMarkdownConfig(
            api_key=api_key,
            base_url=base_url,
            model=model,
            prompt=prompt,
            image_format=image_format,
            timeout_seconds=timeout_seconds,
        )
    )


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    ocr_service: dict[str, Any] = {"reachable": False}
    try:
        response = requests.get(f"{DEFAULT_OCR_BASE_URL.rstrip('/')}/healthz", timeout=10)
        response.raise_for_status()
        ocr_service = {"reachable": True, **response.json()}
    except Exception as exc:
        ocr_service = {"reachable": False, "error": str(exc)}
    return {"status": "ok", "ocr_service": ocr_service}


@app.post("/v1/render/pdf-to-png")
async def render_pdf_to_png(
    file: UploadFile = File(...),
    dpi: int = Form(DEFAULT_DPI),
) -> dict[str, Any]:
    _ensure_pdf(file)
    _validate_dpi(dpi)

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    with tempfile.TemporaryDirectory(prefix="cv_scorer_api_pdf_render_") as tmp_dir:
        input_pdf = Path(tmp_dir) / (file.filename or "upload.pdf")
        input_pdf.write_bytes(pdf_bytes)

        renderer = PDFToPNGRenderer(PDFToPNGConfig(dpi=dpi, image_format="png"))
        try:
            rendered_pages = renderer.render_pdf(input_pdf)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to render PDF: {exc}") from exc

    return {
        "file_name": file.filename,
        "page_count": len(rendered_pages),
        "dpi": dpi,
        "pages": [
            {
                "page_number": page_number,
                "image_format": "png",
                "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            }
            for page_number, image_bytes in rendered_pages
        ],
    }


@app.post("/v1/extract/png-to-markdown")
async def extract_png_to_markdown(
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_MODEL),
    prompt: str = Form(DEFAULT_PROMPT),
    page_number: int = Form(1),
) -> dict[str, Any]:
    image_format = _ensure_image(file)
    _validate_prompt(prompt)
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    client = _ocr_client(model=model, prompt=prompt, image_format=image_format)
    try:
        markdown = client.image_to_markdown(image_bytes, page_number=page_number)
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        raise HTTPException(status_code=502, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "file_name": file.filename,
        "page_number": page_number,
        "model": model,
        "markdown": markdown,
    }


@app.post("/v1/extract/pdf-to-markdown")
async def extract_pdf_to_markdown(
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_MODEL),
    prompt: str = Form(DEFAULT_PROMPT),
    dpi: int = Form(DEFAULT_DPI),
) -> dict[str, Any]:
    _ensure_pdf(file)
    _validate_dpi(dpi)
    _validate_prompt(prompt)

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    with tempfile.TemporaryDirectory(prefix="cv_scorer_api_pdf_extract_") as tmp_dir:
        input_pdf = Path(tmp_dir) / (file.filename or "upload.pdf")
        input_pdf.write_bytes(pdf_bytes)

        extractor = PDFMarkdownExtractor(
            PDFToMarkdownConfig(
                api_key="",
                base_url=DEFAULT_OCR_BASE_URL,
                model=model,
                prompt=prompt,
                dpi=dpi,
                image_format="png",
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
            )
        )
        try:
            markdown = extractor.extract_pdf(input_pdf)
        except requests.HTTPError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            raise HTTPException(status_code=502, detail=detail) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    pages: list[dict[str, Any]] = []
    current_page: int | None = None
    current_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## Page "):
            if current_page is not None:
                pages.append(
                    {
                        "page_number": current_page,
                        "markdown": "\n".join(current_lines).strip(),
                    }
                )
            current_page = int(line.replace("## Page ", "").strip())
            current_lines = []
        else:
            current_lines.append(line)
    if current_page is not None:
        pages.append(
            {
                "page_number": current_page,
                "markdown": "\n".join(current_lines).strip(),
            }
        )
    return {
        "file_name": file.filename,
        "page_count": len(pages),
        "model": model,
        "markdown": markdown,
        "pages": pages,
    }


@app.post("/v1/extract/pdf-to-markdown-file")
async def extract_pdf_to_markdown_file(
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_MODEL),
    prompt: str = Form(DEFAULT_PROMPT),
    dpi: int = Form(DEFAULT_DPI),
) -> PlainTextResponse:
    payload = await extract_pdf_to_markdown(file=file, model=model, prompt=prompt, dpi=dpi)
    input_name = Path(file.filename or "output.pdf").stem
    headers = {"Content-Disposition": f'attachment; filename="{input_name}.md"'}
    return PlainTextResponse(payload["markdown"], headers=headers, media_type="text/markdown")


@app.post("/v1/score/markdown")
async def score_resume_markdown(markdown: str = Form(...)) -> dict[str, Any]:
    _validate_markdown(markdown)
    return score_markdown(markdown).to_dict()
