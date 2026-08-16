# P9 · 共识裁决 + 规模化硬化

P8 完成组织与占用锁。产线审核显示：**多人共标已能收集，缺「整合真源」**；大规模还缺租户硬隔离与作业硬化。

本迭代收口这两块；**完整 CRDT / Yjs、计费配额延后 P10**。

## 范围

| ID | 交付 | 状态 |
|----|------|------|
| **P9-1** | 审核并排多版本；通过时选定 `canonical_annotation_id`；导出优先 canonical | ✅ |
| **P9-2** | 可领任务按组织过滤；任务复合索引；连接池读配置；导出 Celery 时限放宽；清理坏 beat | ✅ |
| **P9-3** | 轻量黄金题：available 按 `quality_config.golden_claim_ratio` 优先 | ✅ |

**明确不做（P11）：** Yjs/Automerge CRDT、org 计费扣款、完整对象存储目录挂载、异步导入以外的全量导入队列化。

## 数据

- `tasks.canonical_annotation_id` → `annotations.id`（可空，UUID 字符串）
- 索引：`(project_id, status)`、`(assignee_id, status)`、`(status)`

## API

- `GET /quality/tasks/{id}` 增加 `versions[]`
- `POST /quality/review` 可选 `canonical_annotation_id`（多版本通过时必填）
- `GET /tasks/available` 默认按用户 `active_org_id` 过滤

## 验收

- 双人共标任务审核可见两个版本；选定其一通过后导出只出该版本
- 非同组织用户看不到对方组织 PENDING 可领任务（非超管）

## 迁移

`cd backend && .venv/bin/alembic upgrade head`（`20260816_p9_consensus`）
