"""COCO 导出纯函数冒烟测试。"""

from types import SimpleNamespace

from app.services.coco_export import bbox_xywh, build_coco_from_tasks


def _task(task_id: int, anns):
    return SimpleNamespace(
        id=task_id,
        data={"file_name": f"{task_id}.jpg", "width": 100, "height": 80},
        data_url=f"http://localhost/uploads/{task_id}.jpg",
        annotations=anns,
        status=SimpleNamespace(value="approved"),
        is_golden=False,
    )


def _ann(data):
    return SimpleNamespace(
        id="a1",
        annotator_id=1,
        version=1,
        work_time=10,
        is_latest=True,
        data=data,
    )


def test_bbox_xywh_from_points():
    box = {
        "type": "bbox",
        "label": "car",
        "points": [{"x": 10, "y": 20}, {"x": 40, "y": 50}],
    }
    assert bbox_xywh(box) == (10.0, 20.0, 30.0, 30.0)


def test_export_coco_from_image_session():
    session = {
        "schema": "dasshine.image_export.v1",
        "session": {
            "frames": {
                "0": [
                    {
                        "id": "b1",
                        "type": "bbox",
                        "label": "person",
                        "points": [{"x": 0, "y": 0}, {"x": 10, "y": 20}],
                    }
                ]
            }
        },
    }
    tasks = [_task(101, [_ann(session)])]
    coco = build_coco_from_tasks(tasks, "demo", [{"id": "person", "name": "person"}])
    assert len(coco["images"]) == 1
    assert coco["images"][0]["id"] == 101
    assert len(coco["annotations"]) == 1
    assert coco["annotations"][0]["bbox"] == [0.0, 0.0, 10.0, 20.0]
    assert any(c["name"] == "person" for c in coco["categories"])
