# 点云样例数据

## `urban_intersection_mini.pcd`

- **用途**：任务 `1002` / `1006`（自动驾驶点云标注）默认加载
- **场景**：约 44m × 44m 城市十字路口（东西 + 南北车道、路缘、车辆、杆状物）
- **坐标系**：与 [KITTI Object Detection](http://www.cvlibs.net/datasets/kitti/eval_object.php?obj_benchmark=3d) Velodyne 一致（x 前 / y 左 / z 上），加载后自动转换到标注场景坐标并居中
- **生成**：`npm run gen:intersection-sample`（约 1.3 万点，ASCII PCD）

### 替换为真实 KITTI 帧（可选）

从 KITTI 官方下载 `data_object_velodyne.zip`，解压后取 `training/velodyne/000008.bin`（街景路口帧），复制为：

`frontend/public/samples/kitti_intersection_000008.bin`

并在 `src/utils/annotationRoutes.ts` 中将任务 `1002` 的路径改为该 `.bin` 文件。
