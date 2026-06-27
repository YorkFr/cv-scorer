# CV Scorer Project Guide

## 1. Project Goal

The current project implements the first major capability:

- convert resume PDFs into reasonably structured Markdown

To make the pipeline explicit, the implementation is now split into two core modules:

- Module 1: `PDF -> PNG`
- Module 2: `PNG -> Markdown`

This provides a clean base for future stages such as:

- structured resume field extraction
- resume scoring
- multilingual normalization
- batch processing
- formal backend APIs

Validated test files:

- `test/cv_pdf/word_type_en.pdf`
- `test/cv_pdf/canvas type_fr.pdf`

## 2. Current Architecture

The repository now has four key parts:

- module 1: PDF page rendering
- module 2: OCR client
- orchestration module: chains the first two together
- OCR model service: runs separately in Docker

### 2.1 Module 1: PDF -> PNG

Responsibilities:

- accept a PDF file
- render each page into an image
- output PNG/JPEG page images

Code:

- `extract_pdf_to_png.py`
- `src/cv_scorer/pdf_to_png.py`

### 2.2 Module 2: PNG -> Markdown

Responsibilities:

- accept one PNG/JPEG page image
- call the OCR model service
- return Markdown for that page

Code:

- `extract_png_to_markdown.py`
- `src/cv_scorer/png_to_markdown.py`

### 2.3 Orchestration module: PDF -> PNG -> Markdown

Responsibilities:

- call module 1 to render pages
- call module 2 page by page
- merge everything into one Markdown output

Code:

- `extract_pdf_to_markdown.py`
- `src/cv_scorer/pdf_to_markdown.py`

### 2.4 OCR model service

Responsibilities:

- load `lightonai/LightOnOCR-2-1B`
- run OCR on input page images
- return Markdown text

Code:

- `docker/ocr-server/app.py`
- `docker/ocr-server/Dockerfile`
- `compose.ocr.local.yml`

## 3. Why This Split

This boundary is more accurate and more maintainable:

- `PDF -> PNG` and `PNG -> Markdown` are fully separated
- the OCR model does not deal with PDF files directly
- the backend can reuse module 1 or module 2 independently later
- it reflects the actual data flow: the model consumes images, not PDFs

## 4. Directory Overview

Core structure:

```text
CV_Scorer/
├─ docker/
│  └─ ocr-server/
│     ├─ app.py
│     ├─ Dockerfile
│     └─ requirements.txt
├─ docs/
│  ├─ project_guide.md
│  ├─ project_guide_en.md
│  ├─ api_spec.md
│  └─ tool_flow_chart.png
├─ src/
│  └─ cv_scorer/
│     ├─ pdf_to_png.py
│     ├─ png_to_markdown.py
│     └─ pdf_to_markdown.py
├─ test/
│  └─ cv_pdf/
│     ├─ word_type_en.pdf
│     ├─ word_type_en.md
│     ├─ canvas type_fr.pdf
│     └─ canvas type_fr.md
├─ .env.example
├─ compose.ocr.local.yml
├─ extract_pdf_to_png.py
├─ extract_png_to_markdown.py
├─ extract_pdf_to_markdown.py
├─ README.md
└─ requirements.txt
```

## 5. Data Flow

End-to-end flow:

1. start the Docker OCR model service
2. module 1 reads the PDF
3. module 1 renders each page into PNG
4. module 2 sends each PNG to the OCR model service
5. the model service returns page-level Markdown
6. the orchestration module merges all pages into one Markdown document

## 6. How To Use It

### 6.1 Start the OCR model service

Make sure Docker Desktop is running first.

Run from the project root:

```powershell
docker compose -f .\compose.ocr.local.yml build
docker compose -f .\compose.ocr.local.yml up -d
```

Check service health:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/healthz | Select-Object -ExpandProperty Content
```

Expected output:

```json
{"status":"ok","model":"lightonai/LightOnOCR-2-1B","device":"auto","cuda_available":true}
```

### 6.2 Install client dependencies

Recommended in `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 6.3 Run only module 1: PDF -> PNG

```powershell
.\.venv\Scripts\python.exe .\extract_pdf_to_png.py .\test\cv_pdf\word_type_en.pdf -o .\test\cv_pdf\word_type_en_pages
```

This will create page images such as:

- `word_type_en_page_001.png`

### 6.4 Run only module 2: PNG -> Markdown

```powershell
.\.venv\Scripts\python.exe .\extract_png_to_markdown.py .\test\cv_pdf\word_type_en_pages\word_type_en_page_001.png -o .\test\cv_pdf\word_type_en_page_001.md --base-url http://127.0.0.1:8000
```

### 6.5 Run the full orchestration: PDF -> PNG -> Markdown

```powershell
.\.venv\Scripts\python.exe .\extract_pdf_to_markdown.py .\test\cv_pdf\word_type_en.pdf -o .\test\cv_pdf\word_type_en.md --base-url http://127.0.0.1:8000
```

French Canva resume:

```powershell
.\.venv\Scripts\python.exe .\extract_pdf_to_markdown.py ".\test\cv_pdf\canvas type_fr.pdf" -o ".\test\cv_pdf\canvas type_fr.md" --base-url http://127.0.0.1:8000
```

## 7. Configuration

See:

- `.env.example`

Main settings:

```env
OCR_API_KEY=
OCR_BASE_URL=http://127.0.0.1:8000
OCR_MODEL=lightonai/LightOnOCR-2-1B
OCR_TIMEOUT_SECONDS=300

HF_TOKEN=
OCR_LOCAL_MODEL=lightonai/LightOnOCR-2-1B
OCR_LOCAL_DEVICE=auto
OCR_LOCAL_DTYPE=auto
OCR_LOCAL_MAX_NEW_TOKENS=4096
```

## 8. Implementation Notes

### 8.1 PDF rendering fallback strategy

Module 1 uses multiple fallbacks:

- `PyMuPDF` first
- then `pypdfium2`
- finally system `pdftoppm`

This matters on the current machine because:

- some `PyMuPDF` DLLs are blocked by local system policy
- `MiKTeX`-provided `pdftoppm/pdftocairo` is not reliable here

In practice, the most stable path on this machine is:

- `pypdfium2`

### 8.2 What is the real OCR input

The OCR model service does not consume PDF directly.

The real model input is:

- one PNG/JPEG page image

So the actual data path is:

`PDF -> PNG -> OCR -> Markdown`

## 9. Known Limitations

### 9.1 GPU memory

The current machine uses an `RTX 3050 4GB`.  
For `LightOnOCR-2-1B`, this is still a borderline setup.

Current status:

- the Docker service starts successfully
- test PDFs have already been extracted successfully
- larger files or higher concurrency may still trigger OOM

### 9.2 Image placeholders

The Markdown output may include lines such as:

```md
![image](image_1.png)
```

This means the model detected an image region on the page. It does not necessarily mean the actual asset was exported separately.

## 10. Recommended Next Steps

Suggested order:

1. wrap the orchestration module into a formal backend API
2. define a structured resume schema
3. add Markdown -> JSON extraction
4. build scoring logic on top of the JSON layer

## 11. One-line Summary

The project now matches the intended modular design:

- Module 1: `PDF -> PNG`
- Module 2: `PNG -> Markdown`
- the OCR model runs as a standalone Docker service
