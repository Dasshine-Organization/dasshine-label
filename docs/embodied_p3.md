# 具身标注 P3

在 P2 传感与导出之上，补齐训练侧互通与交互编辑。

## 交付

1. **RLDS-lite ZIP**：无 TensorFlow 依赖的 episode/steps 布局（`dataset_info.json` + `episodes/episode_*/steps.jsonl`）；项目主格式之一
2. **远端视频下载打包**：导出 LeRobot ZIP 时，对 `http(s)` 相机源在超时/体积上限内下载并写入 `videos/`（失败仍保留 `videos_urls/`）
3. **抓取 / 轨迹 3D 面板**：工作台内 Three.js 轻量场景（轨迹折线、抓取位姿、可拖拽平移）；与数值编辑双向同步
4. **外接策略 HTTP**：配置 `EMBODIED_POLICY_HTTP_*` 后，预标注优先调用外部服务；失败回退 demo 启发式
5. **单测 + 文档**

## 明确不做（P4+）

原生 TFRecord / tensorflow-datasets 依赖、完整点云级 6DoF 手柄编辑器、策略模型本地推理权重托管。
