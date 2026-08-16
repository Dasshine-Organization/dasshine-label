# Dasshine Label 任务分发算法文档

> **P6 真源：** 产品分发与 claim 统一走 `ProjectService.dispatch` / `_assign_task_multi`
> （写 `TaskAssignment` + `task_metadata.assignee_ids` / `co_assignee_ids`，消费 `cross_validate_count`）。
> `POST /api/v1/tasks/dispatch` 与 `TaskDispatchService.dispatch_tasks` 已委托该路径。
> UI：`POST /projects/{id}/dispatch`。详见 `docs/p6_production_loop.md`。

## 概述

Dasshine Label 的任务分发系统采用**智能匹配算法**，基于多维度评分选择最优标注员，实现高效、公平的任务分配。

---

## 核心算法

### 1. 智能匹配评分公式

```
总分 = 技能匹配 × 0.35 + 历史质量 × 0.25 + 负载均衡 × 0.20 + 响应速度 × 0.10 + 等级加成 × 0.10
```

### 2. 各维度评分详解

#### 2.1 技能匹配度（权重35%）
- 标注员技能标签与项目需求的匹配程度
- 计算公式：`0.3 + (匹配技能数 / 总需求技能数) × 0.7`
- 无技能标签用户：基础分0.3

#### 2.2 历史质量（权重25%）
- 基于历史标注准确率
- 新用户默认0.6分，鼓励参与
- 计算公式：`准确率 × 0.7 + 完成率 × 0.3`

#### 2.3 负载均衡（权重20%）
- 避免单个标注员过载
- 负载低于30%：满分1.0
- 负载30-70%：线性递减
- 负载70-90%：快速递减
- 负载90%+：极低分0.1

#### 2.4 响应速度（权重10%）
- 基于平均任务完成时间
- 使用效率评分作为指标

#### 2.5 等级加成（权重10%）

| 等级 | 容量上限 | 加成系数 |
|------|----------|----------|
| 新手(novice) | 10 | 0.5 |
| 初级(junior) | 20 | 0.6 |
| 中级(intermediate) | 30 | 0.75 |
| 高级(senior) | 50 | 0.9 |
| 专家(expert) | 80 | 1.0 |

---

## 分发策略

### 策略1：智能分发（Smart）- 默认
使用上述多维度评分算法，选择总分最高的标注员。

### 策略2：随机分发（Random）
在可用标注员中随机选择，适用于均匀负载场景。

### 策略3：轮询分发（Round Robin）
按顺序依次分配，实现简单均衡。

---

## API接口

### 1. 触发任务分发（管理员）

```http
POST /api/v1/tasks/dispatch
Content-Type: application/json

{
  "project_id": 1,
  "batch_size": 100,
  "strategy": "smart"
}
```

**响应：**
```json
{
  "success": true,
  "assigned_count": 85,
  "assignments": [
    {
      "task_id": 101,
      "user_id": 5,
      "username": "annotator_01",
      "assigned_at": "2026-03-28T12:00:00"
    }
  ]
}
```

### 2. 一键自动分发

```http
POST /api/v1/tasks/auto-dispatch?project_id=1
```

### 3. 标注员领取任务

```http
POST /api/v1/tasks/{task_id}/claim
```

### 4. 放弃任务

```http
POST /api/v1/tasks/release/{task_id}
Body: { "reason": "任务太难" }
```

### 5. 检查超时任务

```http
POST /api/v1/tasks/check-timeout?timeout_minutes=30
```

---

## 防冲突机制

### 1. 数据库行锁
```python
fresh_task = db.query(Task).filter(
    Task.id == task.id
).with_for_update().first()
```

### 2. 状态检查
分配前二次确认任务状态仍为PENDING且未被分配

### 3. 超时回收
- 默认30分钟超时
- 自动释放未处理任务
- 记录释放日志

---

## 主动学习（可选）

优先分发对模型提升最有价值的样本：
- 模型置信度低的样本（<0.6）
- 多样性高的样本
- 边界情况样本

---

## 使用示例

### 启动分发服务

```python
from app.services.task_dispatch import TaskDispatchService

service = TaskDispatchService(db)
results = service.dispatch_tasks(
    project_id=1,
    batch_size=100,
    strategy="smart"
)
```

### 自定义权重

```python
class CustomDispatch(TaskDispatchService):
    WEIGHTS = {
        'skill': 0.40,     # 提高技能权重
        'quality': 0.30,
        'load': 0.15,
        'speed': 0.10,
        'level': 0.05,
    }
```

---

## 监控指标

| 指标 | 说明 |
|------|------|
| 分配成功率 | 成功分配数 / 尝试分配数 |
| 平均分配时间 | 从触发到完成的时间 |
| 负载方差 | 各标注员负载的差异程度 |
| 超时回收率 | 超时回收数 / 总分配数 |

---

## 优化建议

1. **权重调优**：根据实际业务调整各维度权重
2. **容量动态调整**：根据历史表现动态调整等级容量
3. **技能标签细化**：更细粒度的技能分类
4. **A/B测试**：对比不同策略的效果

---

## 文件位置

- 核心算法：`backend/app/services/task_dispatch.py`
- API路由：`backend/app/api/v1/tasks.py`
