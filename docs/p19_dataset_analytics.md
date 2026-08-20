# P19 · 数据集版本与运营看板

对照：不可变导出快照、主动学习入池、项目吞吐/单价/TAT 看板。

## 交付

| 能力 | 行为 |
|------|------|
| 导出快照 | 同步/异步导出后写入 `export_snapshots`（version 递增 + manifest） |
| 快照列表 | `GET /export/{project_id}/snapshots`；导出菜单「历史快照」 |
| 主动学习 | `POST .../active-learning/sync` 低置信入池；`GET .../active-learning`；面板可勾选 `POST .../relabel` |
| 优先领取 | `claim-next?prefer_active_learning=true` 或 `quality_config.active_learning_prefer_claim` |
| 运营看板 | `GET /projects/{id}/analytics?days=30` — 吞吐、TAT p50、累计成本（SQL 聚合计数） |
| completed_at | 审核通过 / 自动过审时写入，供 TAT 统计 |

## 迁移

```bash
cd backend && alembic upgrade head
```

表：`export_snapshots`。

## 验收

- `pytest tests/test_p19_dataset_analytics.py`
- 导出后在菜单看到 v1/v2 快照并可下载
- 项目任务页：运营看板 + 主动学习面板
- 批量预标注后同步入池，领取下一题优先池内任务
