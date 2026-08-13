# 导出格式矩阵

项目级导出：`GET /api/v1/export/{project_id}?format=…&status=approved`

`GET /api/v1/export/{project_id}/stats` 返回当前 `category` 可用的格式列表（三种主流 + `raw_json`）。

| 模态 | 格式 1 | 格式 2 | 格式 3 |
|------|--------|--------|--------|
| `image_2d` | `coco` | `yolo` (ZIP) | `voc` (ZIP) |
| `pointcloud_3d` | `kitti` (ZIP) | `openpcdet` | `csv` |
| `nlp` | `jsonl` | `conll` | `csv` |
| `audio` | `jsonl` | `rttm` | `csv` |
| `video` | `jsonl` | `webvtt` | `csv` |
| `ocr` | `jsonl` | `coco_text` | `paddleocr` |
| `multimodal` | `jsonl` | `sharegpt` | `csv` |
| `embodied` | `json` | `lerobot_jsonl` | `torque_csv` |

实现目录：`backend/app/services/exporters/`。前端入口：项目任务页与各模态工作区「导出数据」菜单（`ProjectExportMenu`）。
