# 具身标注 P0（落地计划）

目标：从「多机位动作 Demo」推进到可服务多数具身公司 **基础产线** 的最小闭环。

## 本迭代交付

1. **VLA 元数据**：语言指令 `instruction`、结局 `success`（success/fail/unknown）、动作区间 `segments`
2. **真值本体**：episode 可带 `proprioception[]`；导出优先用真值，无真值时才 mock 并标记 `joints_source`
3. **导入**：`POST /projects/{id}/import/embodied` 支持 Episode JSON / JSONL
4. **导出**：任务级增加 `lerobot_jsonl`；JSON/JSONL 含 instruction/success/segments
5. **工作台**：编辑上述字段、区间标注、**提交审核** 接线
6. **文档 + 单测**

## 明确不做（P1+）

完整 LeRobot parquet 包、RLDS/HDF5、6DoF 抓取编辑器、力觉/触觉、偏好对 RLHF、审核多机位专用 UI。
