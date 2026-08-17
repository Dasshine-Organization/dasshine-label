"""
遗留 /annotations CRUD 已废弃。

真实标注路径：
- GET/PUT /tasks/{id}/annotation-draft
- POST /tasks/{id}/image|pointcloud|modality/submit
"""

from fastapi import APIRouter, HTTPException

router = APIRouter()

_GONE = (
    "该 /annotations CRUD 已废弃（与 Annotation 模型不兼容）。"
    "请使用 /tasks/{id}/annotation-draft 与各模态 /submit。"
)


def _gone():
    raise HTTPException(status_code=410, detail=_GONE)


@router.get("/annotations")
@router.post("/annotations")
def annotations_collection_gone():
    return _gone()


@router.get("/annotations/{annotation_id}")
@router.put("/annotations/{annotation_id}")
@router.delete("/annotations/{annotation_id}")
def annotations_item_gone(annotation_id: str):
    return _gone()


@router.get("/tasks/{task_id}/annotations")
def task_annotations_gone(task_id: int):
    return _gone()


@router.get("/users/{user_id}/annotations")
def user_annotations_gone(user_id: int):
    return _gone()
