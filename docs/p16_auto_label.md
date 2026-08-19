# P16 · 关掉 501，接上预标注

对照：`POST /auto-label/process|batch` 不再 501；推理全部 HTTP / demo 启发式，不在 API 进程内训练。

## 交付

| 路径 | 行为 |
|------|------|
| NLP | OpenAI 兼容 `chat/completions`；无端点且 DEBUG/`AUTO_LABEL_ALLOW_DEMO` 时 demo NER/分类/情感/摘要 |
| ASR | `AUTO_LABEL_WHISPER_ENDPOINT` POST `{audio_url}` → transcript + segments（毫秒） |
| OCR | `AUTO_LABEL_OCR_ENDPOINT` POST `{image_url}` → xywh spans；兼容 PaddleOCR quad |
| 2D | 仍走 `/tasks/{id}/prelabel/*`；`/auto-label` 返回 400 指引 |
| 批量 | 优先 Celery `batch_auto_label_task`；broker 不可用则同步最多 `AUTO_LABEL_BATCH_SYNC_MAX` 条 |
| 草稿 | 写入当前用户 `AnnotationDraft` + `task.pre_label_result/confidence`；默认不自动提交 |

未配置端点且不允许 demo 时返回 **503**（不是 501）。高置信（≥ 项目阈值）标记 `recommended`，低置信 `needs_review`。

## 验收

- `pytest tests/test_p16_auto_label.py`
- 文本 / 语音工作台「AI 预标注」写入草稿后可刷新看到结果
- 项目任务页对 nlp/audio/ocr/multimodal/video 可「AI 批量预标注」
