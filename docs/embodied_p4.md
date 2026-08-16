# 具身标注 P4

在 P3 互通与编辑之上，补齐训练格式、标定、策略资产与数据集质检。

## 交付

1. **TFRecord（无 TensorFlow）**：纯 Python 写入 `tf.Example` 兼容记录；项目主格式之一（ZIP 内 `*.tfrecord`）
2. **6DoF 手柄**：工作台 3D 面板对抓取/当前轨迹点支持平移 + 旋转（TransformControls）；与数值字段同步
3. **相机内外参**：`streams[]` 可带 `intrinsics` / `extrinsics`；导入 normalize 与导出 v7 透传
4. **策略权重托管桩**：上传 / 列表 / 激活权重文件（本地或 S3）；预标注可附带 `active_weight` 元数据（推理仍走 HTTP）
5. **具身质量摘要**：区间覆盖、指令空缺、抓取/轨迹/偏好计数、成败分布；写入审核 `embodied_preview.quality`
6. **单测 + 文档**

## 明确不做（后续）

`tensorflow-datasets` 官方加载器、点云级场景编辑、本地 GPU 策略推理、异步超大包导出任务队列。
