# 仓库约定 · P0

## 唯一真源

本目录 `Dashine/dasshine-label` 为唯一开发与提交副本。

请勿在以下路径并行修改同一功能后再来回同步：

- `~/Documents/VscodeProject/dasshine-label`（历史分叉，仅作归档参考）

## 前端入口

- 启动：`frontend/index.html` → `frontend/src/main.tsx` → `frontend/src/App.tsx`
- 已删除的陈旧文件：根目录 `App.tsx` / `main.tsx` / `index.css` / `components/` / `contexts/` / `styles/`

## 演示 vs 业务

| 类型 | 行为 |
|------|------|
| 业务入口 | `/projects?category=`、`/tasks?category=`、真实 `project.id` → `/projects/:id/tasks` |
| 演示入口 | 硬编码 task（1001/1002/3001/demo…），仅开发或 `VITE_ENABLE_DEMO_ENTRIES=true` |

`DEMO_TASK_IDS` 仍用于工作台识别离线样例数据，但不再作为 Dashboard 默认跳转目标。
