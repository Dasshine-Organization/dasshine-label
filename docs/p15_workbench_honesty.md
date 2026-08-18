# P15 · 工作台诚实化

对照「能创建的 ann_type 必须能标、能审、能导出」。`lane_3d` 无 3D 折线工具，创建向导不下发。

## 交付

| 模态 | 兑现 |
|------|------|
| 视频 `video_tracking` | 暂停后在画面上画框；`track_id`；关键帧线性插值；jsonl 含 `tracks` + 采样框 |
| 图像 `classification` | 整图多选标签，不再进入画框工具 |
| 图像 `keypoint` | 「插入 COCO-17 姿态」+ 骨架连线 |
| OCR layout / table | 版面类别；表格行列单元格 |
| 语音 | 波形点击定位；情绪 / TTS MOS |
| 多模态 `rlhf` | 成对回复偏好 |
| 点云 `lidar_seg` | 默认 Point Label；点标签可提交 |

## 向导

`GET /projects/meta/types` 与 `CreateProjectModal` fallback 对齐。明确不做：`lane_3d`。

## 验收

- 每种仍开放的类型：导入 → 工作台有对应工具 → 审核预览非空摘要 → 导出字段存在
- `pytest tests/test_p15_workbench.py`
