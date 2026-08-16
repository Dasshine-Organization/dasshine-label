# 具身标注 P2

在 P1 产线能力之上，补齐机器人学习常用传感与导出形态。

## 交付

1. **力觉 / 触觉**：episode `proprioception[]` 可带 `force`（6D wrench）与 `tactile`；无真值时 mock 并标记 `force_source` / `tactile_source`；工作台可读出；写入导出 v6
2. **偏好对 RLHF**：VLA `preferences[]`（chosen / rejected / winner）；工作台可增删；审核预览计数
3. **LeRobot dataset v2**：ZIP 同时含 `*.parquet` + 兼容 `*.jsonl`；本地路径相机尽量打入 `videos/`；远程仍写 `videos_urls/`
4. **HDF5 导出**：单文件 `observations/qpos|force|tactile` + attrs（instruction/success/…）；项目主格式之一
5. **策略预标注**：`POST /embodied/tasks/{ref}/prelabel`（demo 启发式填指令/区间/抓取）；工作台一键应用
6. **单测 + 文档**

## 仍留后续

`tensorflow-datasets` 官方加载器、点云级场景编辑、本地 GPU 策略推理、异步超大包导出。
