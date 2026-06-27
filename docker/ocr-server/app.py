from __future__ import annotations

import base64
import gc
import os
import tempfile
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor


MODEL_NAME = os.getenv("OCR_MODEL", "lightonai/LightOnOCR-2-1B")
DEVICE = os.getenv("OCR_DEVICE", "auto")
DTYPE_NAME = os.getenv("OCR_DTYPE", "auto")
MAX_NEW_TOKENS = int(os.getenv("OCR_MAX_NEW_TOKENS", "4096"))
PROMPT_FALLBACK = (
    "You are an OCR engine for document parsing. "
    "Extract every visible detail from the page into clean Markdown. "
    "Preserve structure, lists, tables, labels, footnotes, and reading order. "
    "Return Markdown only."
)

app = FastAPI(title="OCR Model Service", version="0.1.0")


class OCRPageRequest(BaseModel):
    model: str | None = None
    page_number: int | None = None
    prompt: str | None = None
    image_base64: str
    image_format: str = "png"


class OCRModelRuntime:
    def __init__(self) -> None:
        self.processor = None
        self.model = None
        self.device = None
        self.dtype = None

    def _resolve_device(self) -> str:
        if DEVICE != "auto":
            return DEVICE
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _resolve_dtype(self, device: str):
        if DTYPE_NAME == "auto":
            if device == "cuda":
                return torch.bfloat16
            return torch.float32
        dtype = getattr(torch, DTYPE_NAME, None)
        if dtype is None:
            raise RuntimeError(f"Unsupported OCR_DTYPE: {DTYPE_NAME}")
        if device == "cpu" and dtype in {torch.float16, torch.bfloat16}:
            return torch.float32
        return dtype

    def load(self) -> None:
        if self.model is not None and self.processor is not None:
            return
        self.device = self._resolve_device()
        self.dtype = self._resolve_dtype(self.device)
        self.model = LightOnOcrForConditionalGeneration.from_pretrained(
            MODEL_NAME,
            torch_dtype=self.dtype,
            low_cpu_mem_usage=True,
        )
        self.model = self.model.eval().to(self.device)
        self.processor = LightOnOcrProcessor.from_pretrained(MODEL_NAME)

    def infer_markdown(self, prompt: str, image_bytes: bytes, image_format: str) -> str:
        self.load()
        suffix = ".png" if image_format == "png" else ".jpg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = Path(tmp.name)
        try:
            conversation = [
                {
                    "role": "user",
                    "content": [{"type": "image", "url": str(tmp_path)}],
                }
            ]
            if prompt and prompt.strip() and prompt.strip() != PROMPT_FALLBACK:
                conversation[0]["content"].append({"type": "text", "text": prompt.strip()})
            inputs = self.processor.apply_chat_template(
                conversation,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            )
            inputs = {
                key: value.to(device=self.device, dtype=self.dtype) if value.is_floating_point() else value.to(self.device)
                for key, value in inputs.items()
            }
            with torch.inference_mode():
                output_ids = self.model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)
            generated_ids = output_ids[0, inputs["input_ids"].shape[1] :]
            return self.processor.decode(generated_ids, skip_special_tokens=True).strip()
        finally:
            tmp_path.unlink(missing_ok=True)
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()


runtime = OCRModelRuntime()


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "device": runtime.device or DEVICE,
        "cuda_available": torch.cuda.is_available(),
    }


@app.post("/v1/ocr/page")
def ocr_page(request: OCRPageRequest) -> dict[str, Any]:
    try:
        image_bytes = base64.b64decode(request.image_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image payload.") from exc

    try:
        markdown = runtime.infer_markdown(
            prompt=request.prompt or PROMPT_FALLBACK,
            image_bytes=image_bytes,
            image_format=request.image_format,
        )
    except torch.cuda.OutOfMemoryError as exc:
        raise HTTPException(status_code=507, detail="GPU out of memory while running OCR.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "model": request.model or MODEL_NAME,
        "page_number": request.page_number,
        "markdown": markdown,
    }
