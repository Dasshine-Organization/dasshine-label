# P5 · 产线缺口补齐

对照「分布式多人分发 / 第三方审核 / 多模态标注导出」审计结果，本迭代落地最高杠杆项。

## 计划与顺序

| ID | 交付 | 目标 |
|----|------|------|
| **P5-1** | **OCR 专用工作台** | 路由不再落入文本 NER；图像上框选文字；提交 `spans[]` 带 `bbox`/`text`，对齐 `coco_text` / `paddleocr` |
| **P5-2** | **统一分发 + 交叉人数** | UI 分发真源写 `TaskAssignment`；读取 `cross_validate_count`，多人共标任务；manual 可选指定人 |
| **P5-3** | **质控数据契约** | 交叉验证改用 `Annotation.data` / `is_latest`；修复前端 API 路径；黄金题写入可用答案结构 |
| **P5-4** | **审核预览补齐** | NLP / 音频 / 视频 / 多模态摘要进 `modality_preview`；审核页展示 |
| **P5-5** | **成员管理 + 审核 ACL** | `GET /projects/{id}/members` + 简单管理 UI；平台 reviewer 可审其有权限的项目 |

## 明确不做（P6+）

多租户 Organization、实时协同 CRDT、完整黄金题盲测轮换 UI、点云审核 3D 查看器、异步超大包导出队列。

## 验收

- OCR 项目打开专用工作台，导出 coco_text/paddleocr 非空
- 交叉人数 >1 时分发产生多条 assignment / 元数据，交叉验证 API 不 500
- 审核页能看到文本 spans / 音频转写 / 视频片段摘要
- 成员列表可查看与增删

## 实施状态（本迭代）

| ID | 状态 |
|----|------|
| P5-1 OCR 工作台 | ✅ 路由 `/annotate-ocr`、modality=`ocr`、bbox spans |
| P5-2 分发交叉人数 | ✅ `TaskAssignment` + `co_assignee_ids`；手动选人 |
| P5-3 质控契约 | ✅ `data`/`is_latest`；前端 `/quality/cross-validation` |
| P5-4 审核预览 | ✅ `modality_preview` |
| P5-5 成员 + ACL | ✅ `GET members` + 面板；平台 reviewer 成员可审 |
