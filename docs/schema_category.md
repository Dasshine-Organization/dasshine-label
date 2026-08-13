# 项目分类约定（P1）

## 存储

| 字段 | 位置 | 说明 |
|------|------|------|
| `projects.category` | 列 | UI 分类一等字段（`image_2d` / `nlp` / …） |
| `projects.ann_type` | 列 | 标注子类型（`bbox_2d` / `ner` / …） |
| `annotation_schema.category` | JSON | 与列**双写**，兼容旧客户端 |
| `annotation_schema.ann_type` | JSON | 同上 |
| `projects.type` | 遗留枚举 | 仅兼容旧 `ProjectType`；新逻辑勿依赖 |

解析顺序（`_resolve_project_category`）：

1. 列 `category`
2. `annotation_schema.category`
3. `ann_type` → 类别映射
4. 旧 `Project.type` → 类别映射

## 迁移

```bash
cd backend
alembic upgrade head
# 或 Docker entrypoint 已自动执行
```

已有库若列已通过 `create_all` 建出但值为空：

```bash
python scripts/backfill_project_category.py
```

## 种子

每个主类别至少一个真实项目（无硬编码 task id）：

```bash
python scripts/seed_category_projects.py
```

## 导入提示

| 类别 | 推荐导入方式 |
|------|----------------|
| image_2d | 本地图片 / ZIP / COCO / YOLO |
| pointcloud_3d | URL 列表 / ZIP（`.pcd/.bin/.ply`） |
| video | URL 列表 / ZIP |
| audio | URL / ZIP / 文本 |
| nlp | 文本 / CSV / JSONL |
| embodied | JSONL / URL（完整 episode 导入见后续） |
| ocr / multimodal | CSV / JSONL / URL |
