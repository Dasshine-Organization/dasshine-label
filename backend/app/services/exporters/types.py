"""导出结果与格式元数据。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass(frozen=True)
class FormatMeta:
    id: str
    label: str
    ext: str
    description: str
    primary: bool = True  # False = raw_json 等兜底


@dataclass
class ExportArtifact:
    content: bytes
    filename_suffix: str
    media_type: str


ExporterFn = Callable[..., ExportArtifact]
