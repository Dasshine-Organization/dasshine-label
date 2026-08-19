# Dasshine Label 自动标注

预标注走 **HTTP 适配器**，不在 API 进程内训练模型。2D 检测请用 `/tasks/{id}/prelabel/*`（YOLO / HF / HTTP）。

高置信（≥ 项目 `auto_label_threshold`，默认 0.8）写入草稿并标记 `recommended`；低置信同样写入草稿，标记 `needs_review`，由人工确认。默认 **不自动提交**（`AUTO_LABEL_AUTO_SUBMIT=false`）。

生产未配置端点且未开 demo 时返回 **503**，不再 501。

---

## 适配器

| 类型 | 环境变量 | 约定 |
|------|----------|------|
| LLM（NER / 分类 / 情感 / 摘要 / 翻译 / QA / caption） | `AUTO_LABEL_LLM_BASE_URL` + 可选 `AUTO_LABEL_LLM_API_KEY` / `AUTO_LABEL_LLM_MODEL` | OpenAI 兼容 `POST {base}/chat/completions`，JSON 对象 |
| ASR | `AUTO_LABEL_WHISPER_ENDPOINT` | `POST {audio_url}` → `{text, segments, confidence}`；`start`/`end` 为秒或 `start_ms`/`end_ms` |
| OCR | `AUTO_LABEL_OCR_ENDPOINT` | `POST {image_url}` → `{texts:[{text,bbox,confidence}]}`，bbox 为像素 xywh；也接受 PaddleOCR `results` 四边形 |

无端点时：`DEBUG=true` 或 `AUTO_LABEL_ALLOW_DEMO=true` 使用确定性启发式（CI / 本地）。

---

## API

```http
POST /api/v1/auto-label/process/{task_id}
POST /api/v1/auto-label/batch
GET  /api/v1/auto-label/status/{project_id}
POST /api/v1/auto-label/enable/{project_id}
POST /api/v1/auto-label/disable/{project_id}
```

- 单任务：有工作台权限的成员即可；写入 **当前用户** 草稿。
- 批量：管理员；优先入 Celery，Redis 不可用时同步小批量兜底。
- 图像 2D：400，请改用 `/tasks/{id}/prelabel/run`。

单任务响应含 `confidence`、`adapter`、`recommended`、`needs_review`、`results[]`。

---

## 配置示例

见 `backend/.env.example` 中 `AUTO_LABEL_*`。

```bash
AUTO_LABEL_LLM_BASE_URL=https://api.openai.com/v1
AUTO_LABEL_LLM_API_KEY=sk-...
AUTO_LABEL_LLM_MODEL=gpt-4o-mini
AUTO_LABEL_WHISPER_ENDPOINT=http://127.0.0.1:9001/v1/transcribe
AUTO_LABEL_OCR_ENDPOINT=http://127.0.0.1:9002/v1/ocr
AUTO_LABEL_ALLOW_DEMO=false
```

---

## Celery

```bash
celery -A app.celery_app worker --loglevel=info
```

| 任务 | 用途 |
|------|------|
| `auto_label_task` | 单任务 |
| `batch_auto_label_task` | 批量（跳过已有 `pre_label_confidence` 的任务） |

---

## 前端

文本 / 语音 / OCR / 多模态 / 视频 caption 工作台「AI 预标注」；项目任务页（nlp/audio/ocr/multimodal/video）「AI 批量预标注」。
