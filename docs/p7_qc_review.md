# P7 · 质控盲测 + 点云审核 3D

P6 已收口共标/分发/异步导出。本迭代补齐黄金题产品闭环与点云审核预览。

## 范围

| ID | 交付 |
|----|------|
| **P7-1** | 黄金题盲测 UI：插入、答案编辑、标注侧剥离 `is_golden` |
| **P7-2** | 点云审核只读 3D（复用 Scene3DWorkspace） |

**P8（原 P7+）：** Organization 多租户、实时 CRDT、完整黄金题轮换调度器。

## 验收

- 管理员插入黄金题后，标注工作台看不到黄金标记；专家可编辑答案
- 点云任务进 `/review` 可旋转查看点云与 3D 框

## 实施状态

| ID | 状态 |
|----|------|
| P7-1 黄金题盲测 | done：API + 剥离 + 质控面板 |
| P7-2 点云审核 3D | done：`pointcloud_preview` + Scene3D `readOnly` |

**P8：** Organization、CRDT。
