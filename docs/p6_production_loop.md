# P6 · 多人共标闭环 + 分发统一 + 异步导出

对照 P5：分发已写 `co_assignee_ids`，但列表/开始/提交仍只认主 `assignee_id`，且首次提交即 `SUBMITTED`。本迭代收口产线闭环。

## 范围

| ID | 交付 |
|----|------|
| **P6-1** | 多人共标生产闭环：共标人可提交；满 N 才进审核 |
| **P6-2** | 统一分发真源：claim / timeout / legacy dispatch 委托 `ProjectService` |
| **P6-3** | 异步导出 job API + UI 轮询下载 |

**明确不做（P7+）：** Organization、CRDT、黄金题盲测 UI、点云审核 3D。

## 状态机

- 所需人数：`task_metadata.cross_validate_count`（缺省 1）
- 已提交：`Annotation.is_latest` 按 `annotator_id` 去重
- 未满 N：保持 `ANNOTATING`，`task_metadata.submitted_annotator_ids` 记录进度
- 满 N：置 `SUBMITTED`

## 验收

- 交叉人数=2：两人各自提交；第二次提交后任务才进 `/review`
- `POST /tasks/dispatch` 与项目分发一致（`TaskAssignment` + 共标 metadata）
- 后台导出：有 worker 可下载；无 worker 时同步导出仍可用

## 实施状态

| ID | 状态 |
|----|------|
| P6-1 多人共标闭环 | done：`apply_cross_submit_gate`；共标 ACL；列表/start/submit |
| P6-2 统一分发 | done：claim / `/tasks/dispatch` 委托 `ProjectService` |
| P6-3 异步导出 | done：`POST /export/{id}/jobs` + 轮询 UI |
