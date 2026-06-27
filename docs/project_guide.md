# CV Scorer 项目说明

## 1. 项目目标

这个项目当前完成的是第一阶段能力：

- 把简历 PDF 转成结构化较好的 Markdown

为了让链路更清晰，当前实现已经明确拆成两个核心模块：

- 第一模块：`PDF -> PNG`
- 第二模块：`PNG -> Markdown`

在这个基础上，后面可以继续做：

- 简历字段抽取
- 简历评分
- 中英文统一结构化
- 批量处理
- 正式后端 API

当前已经验证通过的测试文件：

- `test/cv_pdf/word_type_en.pdf`
- `test/cv_pdf/canvas type_fr.pdf`

## 2. 当前架构

当前仓库有四个关键部分：

- 第一模块：PDF 页渲染模块
- 第二模块：OCR 客户端模块
- 编排模块：把前两者串起来
- 模型服务：单独在 Docker 里运行

### 2.1 第一模块：PDF -> PNG

职责：

- 接收 PDF 文件
- 将 PDF 每一页渲染成图片
- 输出 PNG/JPEG 页图

代码位置：

- `extract_pdf_to_png.py`
- `src/cv_scorer/pdf_to_png.py`

### 2.2 第二模块：PNG -> Markdown

职责：

- 接收单页 PNG/JPEG
- 调用 OCR 模型服务
- 返回该页的 Markdown

代码位置：

- `extract_png_to_markdown.py`
- `src/cv_scorer/png_to_markdown.py`

### 2.3 编排模块：PDF -> PNG -> Markdown

职责：

- 调用第一模块把 PDF 渲染成页图
- 再调用第二模块逐页 OCR
- 最后拼接成整份 Markdown

代码位置：

- `extract_pdf_to_markdown.py`
- `src/cv_scorer/pdf_to_markdown.py`

### 2.4 OCR 模型服务

职责：

- 单独加载 `lightonai/LightOnOCR-2-1B`
- 对输入页图执行 OCR
- 返回 Markdown 文本

代码位置：

- `docker/ocr-server/app.py`
- `docker/ocr-server/Dockerfile`
- `compose.ocr.local.yml`

## 3. 为什么这样拆

这次重构后的边界更清晰：

- `PDF -> PNG` 和 `PNG -> Markdown` 职责完全分离
- OCR 模型不关心 PDF，只关心图片
- 业务后端以后可以单独复用第一个模块或第二个模块
- 更符合实际数据流：模型真正输入的是图片，不是 PDF

## 4. 目录说明

核心目录如下：

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

## 5. 数据流

完整流程如下：

1. 启动 Docker OCR 模型服务
2. 第一模块读取 PDF
3. 第一模块将 PDF 每一页转成 PNG
4. 第二模块把 PNG 发送给模型服务
5. 模型服务返回每页 Markdown
6. 编排模块合并为整份 Markdown

## 6. 如何使用

### 6.1 启动 OCR 模型服务

先确保 Docker Desktop 已经启动。

在项目根目录执行：

```powershell
docker compose -f .\compose.ocr.local.yml build
docker compose -f .\compose.ocr.local.yml up -d
```

检查服务是否可用：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/healthz | Select-Object -ExpandProperty Content
```

正常情况下会返回：

```json
{"status":"ok","model":"lightonai/LightOnOCR-2-1B","device":"auto","cuda_available":true}
```

### 6.2 安装业务侧依赖

推荐安装到 `.venv`：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 6.3 只执行第一模块：PDF -> PNG

```powershell
.\.venv\Scripts\python.exe .\extract_pdf_to_png.py .\test\cv_pdf\word_type_en.pdf -o .\test\cv_pdf\word_type_en_pages
```

这一步会输出按页命名的图片，例如：

- `word_type_en_page_001.png`

### 6.4 只执行第二模块：PNG -> Markdown

```powershell
.\.venv\Scripts\python.exe .\extract_png_to_markdown.py .\test\cv_pdf\word_type_en_pages\word_type_en_page_001.png -o .\test\cv_pdf\word_type_en_page_001.md --base-url http://127.0.0.1:8000
```

### 6.5 执行完整编排：PDF -> PNG -> Markdown

```powershell
.\.venv\Scripts\python.exe .\extract_pdf_to_markdown.py .\test\cv_pdf\word_type_en.pdf -o .\test\cv_pdf\word_type_en.md --base-url http://127.0.0.1:8000
```

法语 Canva 简历：

```powershell
.\.venv\Scripts\python.exe .\extract_pdf_to_markdown.py ".\test\cv_pdf\canvas type_fr.pdf" -o ".\test\cv_pdf\canvas type_fr.md" --base-url http://127.0.0.1:8000
```

## 7. 配置说明

配置示例在：

- `.env.example`

主要配置项：

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

## 8. 实现细节

### 8.1 PDF 渲染策略

第一模块当前做了多重回退：

- 优先 `PyMuPDF`
- 失败后回退到 `pypdfium2`
- 最后再尝试系统 `pdftoppm`

这样做是因为当前机器上：

- `PyMuPDF` 的某些 DLL 会被系统策略拦截
- `MiKTeX` 自带的 `pdftoppm/pdftocairo` 不稳定

因此当前更稳定的实际路径通常是：

- `pypdfium2`

### 8.2 OCR 输入到底是什么

模型服务不直接接收 PDF。

模型服务真正接收的是：

- 单页 PNG/JPEG 图片

也就是说，当前真实输入链路是：

`PDF -> PNG -> OCR -> Markdown`

## 9. 已知限制

### 9.1 GPU 显存

你当前机器是 `RTX 3050 4GB`。  
对 `LightOnOCR-2-1B` 来说这是边缘配置。

现状是：

- Docker 服务已经成功启动
- 测试 PDF 已经成功提取
- 更大文件或更高并发下仍可能出现 OOM

### 9.2 图片占位

输出 Markdown 里可能会出现类似：

```md
![image](image_1.png)
```

这表示模型识别到了页面中的图片区域，不代表图片资源已经单独导出。

## 10. 推荐下一步

建议后续按这个顺序推进：

1. 把当前编排模块封装成正式后端 API
2. 定义简历结构化字段 schema
3. 增加 Markdown -> JSON 抽取
4. 在 JSON 基础上做评分逻辑

## 11. 一句话总结

当前项目已经按你要求重构为：

- 第一模块：`PDF -> PNG`
- 第二模块：`PNG -> Markdown`
- 模型单独作为 Docker 服务运行
