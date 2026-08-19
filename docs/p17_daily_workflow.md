# P17 · 多用户标注日常

对照：规范必读、驳回定位、下一题/跳过、站内通知、一致率自动过审、排行榜、黄金题连错暂停领取。

## 交付

| 能力 | 行为 |
|------|------|
| 标注规范 | `GET/PUT /projects/{id}/guidelines`；Markdown 存 `quality_config`；`POST .../guidelines/ack` 写 `project_members.meta` |
| 必读门禁 | `guidelines_must_read` 时未 ack 不可 claim / claim-next（owner/admin 豁免） |
| 驳回定位 | `ReviewRequest.targets` → workspace `last_reject_targets` + 通知 assignee |
| 下一题 / 跳过 | `POST /tasks/claim-next`、`POST /tasks/{id}/skip`；工作台 `?` 快捷键 |
| 通知铃铛 | `notifications` 表；Layout 铃铛轮询；驳回等写入 |
| 自动过审 | `quality_config.auto_approve_on_agreement` + `min_agreement`；交叉一致后直接 approved |
| 黄金暂停 | 连续失败 ≥ `golden_fail_threshold`（默认 5）禁止领取 |
| 排行榜 | `/leaderboard` 页；`completed_tasks >= 1` |

## 迁移

```bash
cd backend && alembic upgrade head
```

新增：`project_members.meta`、`notifications`。

## 验收

- `pytest tests/test_p17_daily_workflow.py`
- 项目质控面板可编辑规范与日常质控开关
- 审核驳回可点选对象；工作台显示驳回条与定位
- 任务页「领取下一题」；侧栏铃铛与排行榜入口
