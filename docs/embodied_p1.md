# 具身标注 P1

在 P0 闭环之上，补齐产线常用能力。

## 交付

1. **LeRobot dataset ZIP**：`meta/info.json` + `meta/episodes.jsonl` + `data/chunk-000/*.jsonl` + `videos_urls/`（流 URL 清单；不打包二进制视频）
2. **抓取 / 轨迹**：工作区可标注 `grasps[]`（6DoF 位姿+夹爪开度）与 `trajectory[]`（EE 轨迹点）；写入导出 v5
3. **审核多机位预览**：`/quality/tasks/{id}` 返回 `embodied_preview`；审核页展示多路缩略图 + 指令/成败/区间摘要
4. **单测 + 文档**

## 仍留后续

`tensorflow-datasets` 官方加载器、点云级场景编辑、本地 GPU 策略推理、异步超大包导出。
