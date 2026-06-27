# CV Scorer

![flow chart](docs/tool_flow_chart.png)

详细项目说明见：

- 中文版 [docs/project_guide.md](docs/project_guide.md)
- English version [docs/project_guide_en.md](docs/project_guide_en.md)
- API spec [docs/api_spec.md](docs/api_spec.md)

当前仓库按新的模块边界组织：

- 第一模块：`PDF -> PNG`
- 第二模块：`PNG -> Markdown`
- 编排模块：`PDF -> PNG -> Markdown`
- 模型服务：单独用 Docker 启动，内部使用 `Transformers` 加载 `lightonai/LightOnOCR-2-1B`

## Architecture

- `src/cv_scorer/pdf_to_png.py`
第一模块，负责 PDF 页渲染。

- `src/cv_scorer/png_to_markdown.py`
第二模块，负责页图 OCR。

- `src/cv_scorer/pdf_to_markdown.py`
编排模块，负责串联前两个模块。

- `src/cv_scorer/backend_api.py`
业务后端 API，暴露正式 HTTP 接口。

- `docker/ocr-server/app.py`
模型服务入口。负责加载 OCR 模型并返回单页 Markdown。

- `compose.ocr.local.yml`
本地模型服务的 Docker Compose 配置。

## Model Service

模型服务使用 `Transformers + FastAPI`，不是 `vLLM`。

模型默认是 `lightonai/LightOnOCR-2-1B`。模型卡说明这个模型从 `transformers v5` 开始支持，并给出了官方 `Transformers` 用法：
https://huggingface.co/lightonai/LightOnOCR-2-1B

服务接口：

- `GET /healthz`
- `POST /v1/ocr/page`

请求体示例：

```json
{
  "model": "lightonai/LightOnOCR-2-1B",
  "page_number": 1,
  "prompt": "Extract page to detailed markdown",
  "image_base64": "....",
  "image_format": "png"
}
```

响应体示例：

```json
{
  "model": "lightonai/LightOnOCR-2-1B",
  "page_number": 1,
  "markdown": "## ..."
}
```

## Start Model Service

先启动 Docker Desktop，再启动模型服务：

```powershell
docker compose -f .\compose.ocr.local.yml build
docker compose -f .\compose.ocr.local.yml up
```

如果模型拉取需要 Hugging Face token，先配置 `.env` 或环境变量里的 `HF_TOKEN`。

## Install Client

```powershell
python -m pip install -r requirements.txt
```

## Run Client

模型服务启动后，可以这样调用：

第一模块：

```powershell
python .\extract_pdf_to_png.py .\resume.pdf -o .\resume_pages
```

第二模块：

```powershell
python .\extract_png_to_markdown.py .\resume_pages\resume_page_001.png -o .\resume_page_001.md --base-url http://127.0.0.1:8000
```

完整编排：

```powershell
python .\extract_pdf_to_markdown.py .\resume.pdf `
  -o .\resume.md `
  --base-url http://127.0.0.1:8000 `
  --model lightonai/LightOnOCR-2-1B
```

业务后端 API：

```powershell
python .\run_backend_api.py
```

## Config

参考 `.env.example`：

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

## Resource Note

`LightOnOCR-2-1B` 虽然比更大的 OCR 多模态模型轻，但你的 `RTX 3050 4GB` 仍然是边缘配置。模型服务可能可以启动，也可能在加载或推理时 OOM。出现问题时优先尝试：

- 将 `OCR_LOCAL_DEVICE=cpu`
- 降低输入页数
- 降低 PDF 渲染 DPI
