"""项目 category 解析冒烟测试。"""

from types import SimpleNamespace

from app.services.project_service import _resolve_project_ann_type, _resolve_project_category


def test_resolve_category_prefers_column():
    p = SimpleNamespace(
        category="nlp",
        ann_type="ner",
        type=SimpleNamespace(value="object_detection"),
        annotation_schema={"category": "image_2d", "ann_type": "bbox_2d"},
    )
    assert _resolve_project_category(p) == "nlp"
    assert _resolve_project_ann_type(p) == "ner"


def test_resolve_category_falls_back_to_schema():
    p = SimpleNamespace(
        category=None,
        ann_type=None,
        type=SimpleNamespace(value="object_detection"),
        annotation_schema={"category": "image_2d", "ann_type": "bbox_2d"},
    )
    assert _resolve_project_category(p) == "image_2d"
    assert _resolve_project_ann_type(p) == "bbox_2d"


def test_resolve_category_from_ann_type_map():
    p = SimpleNamespace(
        category="",
        ann_type="ner",
        type=SimpleNamespace(value="object_detection"),
        annotation_schema={},
    )
    assert _resolve_project_category(p) == "nlp"
