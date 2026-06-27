# CV Scorer API Spec

## Overview

This document defines the current API contract for the project.

The repository is organized into four layers:

- `PDF -> PNG` rendering module
- `PNG -> Markdown` OCR client module
- orchestration module for `PDF -> PNG -> Markdown`
- standalone OCR model service running in Docker

The OCR model service and the business backend API are both implemented.

## 1. OCR Model Service API

Base URL:

```text
http://127.0.0.1:8000
```

Implementation:

- `docker/ocr-server/app.py`
- `docker/ocr-server/Dockerfile`
- `compose.ocr.local.yml`

### 1.1 Health Check

Endpoint:

```http
GET /healthz
```

Purpose:

- verify that the model service process is up
- verify that the container is reachable
- confirm whether CUDA is visible

Example response:

```json
{
  "status": "ok",
  "model": "lightonai/LightOnOCR-2-1B",
  "device": "auto",
  "cuda_available": true
}
```

### 1.2 OCR One Page

Endpoint:

```http
POST /v1/ocr/page
Content-Type: application/json
```

Purpose:

- send one rendered page image to the OCR model
- receive Markdown text for that page

Request body:

```json
{
  "model": "lightonai/LightOnOCR-2-1B",
  "page_number": 1,
  "prompt": "Extract page to detailed markdown",
  "image_base64": "BASE64_ENCODED_IMAGE",
  "image_format": "png"
}
```

Field definitions:

- `model`
Model name passed through to the OCR service.

- `page_number`
Original page number in the source PDF.

- `prompt`
Optional OCR instruction prompt.

- `image_base64`
Rendered page image encoded as base64.

- `image_format`
Supported values:
- `png`
- `jpeg`

Successful response:

```json
{
  "model": "lightonai/LightOnOCR-2-1B",
  "page_number": 1,
  "markdown": "# ..."
}
```

### 1.3 Error Behavior

Possible status codes:

- `200`
Request succeeded.

- `400`
Invalid request payload, usually malformed base64 image data.

- `500`
Internal OCR failure such as model input formatting issues or runtime errors.

- `507`
GPU out of memory during inference.

Example error:

```json
{
  "detail": "GPU out of memory while running OCR."
}
```

## 2. Business Backend API

Base URL:

```text
http://127.0.0.1:9000
```

Implementation:

- `src/cv_scorer/backend_api.py`
- `run_backend_api.py`

The business backend does the following:

- accept PDF or PNG inputs
- render PDF pages locally
- call the OCR model service page by page
- merge page-level markdown
- return JSON results or a downloadable Markdown file

### 2.1 Health Check

Endpoint:

```http
GET /healthz
```

Example response:

```json
{
  "status": "ok",
  "ocr_service": {
    "reachable": true,
    "model": "lightonai/LightOnOCR-2-1B"
  }
}
```

### 2.2 Render PDF to PNG

Endpoint:

```http
POST /v1/render/pdf-to-png
Content-Type: multipart/form-data
```

Form fields:

- `file`
Input PDF file.

- `dpi`
Optional rendering DPI. Default:
`200`

Successful response:

```json
{
  "file_name": "resume.pdf",
  "page_count": 1,
  "dpi": 200,
  "pages": [
    {
      "page_number": 1,
      "image_base64": "BASE64_ENCODED_IMAGE",
      "image_format": "png"
    }
  ]
}
```

### 2.3 Extract PNG to Markdown

Endpoint:

```http
POST /v1/extract/png-to-markdown
Content-Type: multipart/form-data
```

Form fields:

- `file`
Input page image.

- `model`
Optional model name. Default:
`lightonai/LightOnOCR-2-1B`

- `prompt`
Optional OCR prompt override.

- `page_number`
Optional original page number. Default:
`1`

Successful response:

```json
{
  "file_name": "resume_page_001.png",
  "page_number": 1,
  "model": "lightonai/LightOnOCR-2-1B",
  "markdown": "# ..."
}
```

### 2.4 Extract PDF to Markdown

Endpoint:

```http
POST /v1/extract/pdf-to-markdown
Content-Type: multipart/form-data
```

Form fields:

- `file`
Input PDF file.

- `model`
Optional model name. Default:
`lightonai/LightOnOCR-2-1B`

- `prompt`
Optional OCR prompt override.

- `dpi`
Optional rendering DPI. Default:
`200`

Successful response:

```json
{
  "file_name": "resume.pdf",
  "page_count": 1,
  "model": "lightonai/LightOnOCR-2-1B",
  "markdown": "## Page 1\n\n# ...",
  "pages": [
    {
      "page_number": 1,
      "markdown": "# ..."
    }
  ]
}
```

### 2.5 Download Markdown File

Endpoint:

```http
POST /v1/extract/pdf-to-markdown-file
Content-Type: multipart/form-data
```

Response behavior:

- `Content-Type: text/markdown`
- `Content-Disposition: attachment; filename="resume.md"`

## 3. Data Flow

Current business backend flow:

1. receive uploaded PDF or PNG
2. if input is PDF, render each page into PNG
3. call `POST /v1/ocr/page` for each page image
4. collect page-level markdown
5. merge pages into final markdown if needed
6. return JSON or `.md` file

## 4. Responsibilities

The OCR model service only:

- loads the OCR model
- accepts page images
- returns page-level OCR results

The business backend:

- handles uploads
- renders PDFs
- calls the OCR service
- merges results
- exposes product-facing APIs

This separation keeps model dependencies isolated from the business layer.

## 5. Validation Rules

Current validation rules:

- reject non-PDF uploads for PDF endpoints
- reject non-image uploads for PNG endpoint
- reject empty files
- validate `dpi` range
- validate prompt length

Current values:

- allowed `dpi`: `72` to `300`
- default `dpi`: `200`
- max `prompt` length: `8000` characters

## 6. Error Contract

Current business-layer errors use FastAPI's default error response shape:

```json
{
  "detail": "Only PDF uploads are supported."
}
```

Typical current status codes:

- `400`
Invalid file type, empty upload, invalid `dpi`, or prompt too long.

- `500`
PDF rendering failure or unexpected backend error.

- `502`
The OCR model service returned an HTTP error.

Planned stable business-layer error codes:

- `invalid_file_type`
- `invalid_request`
- `pdf_render_error`
- `ocr_service_unavailable`
- `ocr_service_error`
- `ocr_service_oom`
- `timeout`

Planned JSON error shape:

```json
{
  "error": {
    "code": "ocr_service_error",
    "message": "OCR model service returned 500",
    "details": {
      "page_number": 1
    }
  }
}
```

## 7. Startup

Start the OCR model service first:

```powershell
docker compose -f .\compose.ocr.local.yml up -d
```

Then start the business backend:

```powershell
.\.venv\Scripts\python.exe .\run_backend_api.py
```

The backend listens on:

```text
http://127.0.0.1:9000
```

## 8. Example cURL Calls

### 8.1 Model service health

```bash
curl http://127.0.0.1:8000/healthz
```

### 8.2 Model service OCR page

```bash
curl -X POST http://127.0.0.1:8000/v1/ocr/page \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lightonai/LightOnOCR-2-1B",
    "page_number": 1,
    "prompt": "Extract page to detailed markdown",
    "image_base64": "BASE64_IMAGE",
    "image_format": "png"
  }'
```

### 8.3 Business backend PDF to Markdown

```bash
curl -X POST http://127.0.0.1:9000/v1/extract/pdf-to-markdown \
  -F "file=@resume.pdf" \
  -F "dpi=200"
```
