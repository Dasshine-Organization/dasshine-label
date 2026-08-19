"""
自动标注 HTTP 适配器：OpenAI 兼容 LLM、Whisper/ASR HTTP、OCR HTTP。
无端点且允许 demo（DEBUG 或 AUTO_LABEL_ALLOW_DEMO）时走确定性启发式，供 CI / 本地无 key。
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, NoReturn, Optional, Sequence, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

IMAGE_2D_TYPES = {
    "bbox_2d",
    "polygon",
    "polyline",
    "keypoint",
    "segmentation",
    "classification",
}
UNSUPPORTED_TYPES = {
    "bbox_3d",
    "lidar_seg",
    "lane_3d",
    "video_tracking",
    "video_action",
    "robot_traj",
    "robot_action",
    "robot_grasp",
    "robot_scene",
    "rlhf",
}


class AutoLabelConfigError(Exception):
    """未配置推理端点（应对 API 503）。"""


class AutoLabelAdapterError(Exception):
    """远端 HTTP / 解析失败（应对 API 502）。"""


class AutoLabelUnsupportedError(Exception):
    """该 ann_type 不走 /auto-label（应对 API 400）。"""


@dataclass
class LabelHit:
    label: str
    text: str
    start: Optional[int] = None
    end: Optional[int] = None
    confidence: float = 0.0


@dataclass
class AdapterResult:
    hits: List[LabelHit] = field(default_factory=list)
    overall_confidence: float = 0.0
    model: str = "demo"
    adapter: str = "demo"
    raw_response: Optional[str] = None
    payload_patch: Dict[str, Any] = field(default_factory=dict)


def demo_allowed() -> bool:
    return bool(settings.AUTO_LABEL_ALLOW_DEMO or settings.DEBUG)


def llm_configured() -> bool:
    return bool((settings.AUTO_LABEL_LLM_BASE_URL or "").strip())


def whisper_configured() -> bool:
    return bool((settings.AUTO_LABEL_WHISPER_ENDPOINT or "").strip())


def ocr_configured() -> bool:
    return bool((settings.AUTO_LABEL_OCR_ENDPOINT or "").strip())


def adapter_status() -> Dict[str, Any]:
    return {
        "global_enabled": bool(settings.AUTO_LABEL_ENABLED),
        "demo_allowed": demo_allowed(),
        "auto_submit": bool(settings.AUTO_LABEL_AUTO_SUBMIT),
        "llm": {
            "configured": llm_configured(),
            "model": settings.AUTO_LABEL_LLM_MODEL,
            "base_url": bool(settings.AUTO_LABEL_LLM_BASE_URL),
        },
        "whisper": {"configured": whisper_configured()},
        "ocr": {"configured": ocr_configured()},
    }


def post_json(
    url: str,
    body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
) -> Any:
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    t = timeout if timeout is not None else float(settings.AUTO_LABEL_HTTP_TIMEOUT or 60)
    try:
        with httpx.Client(timeout=t) as client:
            r = client.post(url, json=body, headers=hdrs)
            r.raise_for_status()
            if not r.content:
                return {}
            return r.json()
    except httpx.HTTPStatusError as e:
        raise AutoLabelAdapterError(f"推理服务 HTTP {e.response.status_code}: {e.response.text[:300]}") from e
    except httpx.HTTPError as e:
        raise AutoLabelAdapterError(f"推理服务不可达: {e}") from e
    except ValueError as e:
        raise AutoLabelAdapterError(f"推理服务返回非 JSON: {e}") from e


def _auth_headers(api_key: Optional[str]) -> Dict[str, str]:
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def _extract_json(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    raise AutoLabelAdapterError("模型未返回 JSON 对象")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _label_ids(label_classes: Sequence[Any]) -> List[str]:
    out: List[str] = []
    for item in label_classes or []:
        if isinstance(item, dict):
            lid = str(item.get("id") or item.get("name") or "").strip()
        else:
            lid = str(item).strip()
        if lid and lid not in out:
            out.append(lid)
    return out


# ---------- demo heuristics ----------

_KNOWN_ENTS: List[Tuple[str, str]] = [
    ("马斯克", "PER"),
    ("张三", "PER"),
    ("李四", "PER"),
    ("特斯拉", "ORG"),
    ("OpenAI", "ORG"),
    ("上海", "LOC"),
    ("北京", "LOC"),
    ("纽约", "LOC"),
    ("硅谷", "LOC"),
]
_POS = ("好", "喜欢", "优秀", "满意", "正面", "棒", "赞")
_NEG = ("差", "糟糕", "失望", "负面", "恨", "垃圾")


def demo_ner(text: str, label_classes: Optional[Sequence[Any]] = None) -> AdapterResult:
    allowed = set(_label_ids(label_classes)) or {"PER", "ORG", "LOC"}
    hits: List[LabelHit] = []
    seen: set[Tuple[int, int]] = set()
    for frag, lab in _KNOWN_ENTS:
        if lab not in allowed:
            continue
        start = 0
        while True:
            idx = text.find(frag, start)
            if idx < 0:
                break
            span = (idx, idx + len(frag))
            if span not in seen:
                seen.add(span)
                hits.append(LabelHit(lab, frag, idx, idx + len(frag), 0.88))
            start = idx + len(frag)
    for m in re.finditer(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", text):
        if "PER" not in allowed:
            break
        span = (m.start(), m.end())
        if span not in seen:
            seen.add(span)
            hits.append(LabelHit("PER", m.group(0), m.start(), m.end(), 0.7))
    hits.sort(key=lambda h: h.start or 0)
    conf = sum(h.confidence for h in hits) / len(hits) if hits else 0.4
    spans = [
        {
            "id": _new_id("al"),
            "start": h.start,
            "end": h.end,
            "label": h.label,
            "text": h.text,
            "confidence": h.confidence,
        }
        for h in hits
    ]
    return AdapterResult(
        hits=hits,
        overall_confidence=round(conf, 4),
        model="demo_heuristic",
        adapter="demo",
        payload_patch={"spans": spans},
    )


def demo_classify(text: str, label_classes: Optional[Sequence[Any]] = None) -> AdapterResult:
    ids = _label_ids(label_classes)
    picked: List[str] = []
    for lid in ids:
        if lid and lid.lower() in text.lower():
            picked.append(lid)
    if not picked and ids:
        picked = [ids[0]]
        conf = 0.55
    else:
        conf = 0.82 if picked else 0.4
    if not picked:
        picked = ["other"]
    hit = LabelHit(picked[0], ",".join(picked), confidence=conf)
    return AdapterResult(
        hits=[hit],
        overall_confidence=conf,
        model="demo_heuristic",
        adapter="demo",
        payload_patch={"classification_labels": picked},
    )


def demo_sentiment(text: str) -> AdapterResult:
    if any(w in text for w in _POS):
        sent, conf = "positive", 0.86
    elif any(w in text for w in _NEG):
        sent, conf = "negative", 0.86
    else:
        sent, conf = "neutral", 0.6
    return AdapterResult(
        hits=[LabelHit(sent, sent, confidence=conf)],
        overall_confidence=conf,
        model="demo_heuristic",
        adapter="demo",
        payload_patch={"sentiment": sent},
    )


def demo_summary(text: str) -> AdapterResult:
    clipped = (text or "").strip().replace("\n", " ")
    summary = clipped[:120] + ("…" if len(clipped) > 120 else "")
    return AdapterResult(
        hits=[LabelHit("summary", summary, confidence=0.58)],
        overall_confidence=0.58,
        model="demo_heuristic",
        adapter="demo",
        payload_patch={"summary": summary or "（空文本）"},
    )


def demo_asr(text_hint: str = "") -> AdapterResult:
    transcript = (text_hint or "").strip() or "（演示转写）这是一段示例语音内容。"
    seg = {
        "id": _new_id("seg"),
        "start_ms": 0,
        "end_ms": 3000,
        "speaker": "说话人 A",
        "text": transcript,
        "emotion": "",
    }
    return AdapterResult(
        hits=[LabelHit("transcript", transcript, confidence=0.7)],
        overall_confidence=0.7,
        model="demo_heuristic",
        adapter="demo",
        payload_patch={"transcript": transcript, "segments": [seg]},
    )


def demo_ocr() -> AdapterResult:
    span = {
        "id": _new_id("ocr"),
        "text": "演示识别文字",
        "label": "text",
        "bbox": [20, 20, 240, 48],
        "confidence": 0.72,
    }
    hit = LabelHit("text", span["text"], confidence=0.72)
    return AdapterResult(
        hits=[hit],
        overall_confidence=0.72,
        model="demo_heuristic",
        adapter="demo",
        payload_patch={"spans": [span]},
    )


def demo_caption(hint: str = "") -> AdapterResult:
    cap = (hint or "").strip()[:80] or "（演示）图片/视频内容描述。"
    return AdapterResult(
        hits=[LabelHit("caption", cap, confidence=0.55)],
        overall_confidence=0.55,
        model="demo_heuristic",
        adapter="demo",
        payload_patch={"caption": cap},
    )


# ---------- LLM ----------

def _llm_url() -> str:
    base = (settings.AUTO_LABEL_LLM_BASE_URL or "").rstrip("/")
    if not base:
        raise AutoLabelConfigError("未配置 AUTO_LABEL_LLM_BASE_URL")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def llm_chat(
    system: str,
    user: str,
    *,
    model: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Dict[str, Any]:
    content: Any
    if image_url:
        content = [
            {"type": "text", "text": user},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    else:
        content = user
    body = {
        "model": model or settings.AUTO_LABEL_LLM_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
    }
    data = post_json(_llm_url(), body, _auth_headers(settings.AUTO_LABEL_LLM_API_KEY))
    if isinstance(data, dict) and any(
        k in data for k in ("spans", "labels", "sentiment", "summary", "translation", "caption", "vqa")
    ):
        return data
    try:
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        raw = msg.get("content")
        if isinstance(raw, list):
            raw = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in raw
            )
        if not isinstance(raw, str):
            raise AutoLabelAdapterError("chat.completions 无文本 content")
        return _extract_json(raw)
    except AutoLabelAdapterError:
        raise
    except (KeyError, IndexError, TypeError, AttributeError) as e:
        raise AutoLabelAdapterError(f"无法解析 LLM 响应: {e}") from e


def _fix_span_offsets(text: str, start: Any, end: Any, fragment: str) -> Optional[Tuple[int, int]]:
    try:
        s, e = int(start), int(end)
    except (TypeError, ValueError):
        s, e = -1, -1
    frag = fragment or (text[s:e] if 0 <= s < e <= len(text) else "")
    if 0 <= s < e <= len(text) and (not frag or text[s:e] == frag):
        return s, e
    if frag:
        idx = text.find(frag)
        if idx >= 0:
            return idx, idx + len(frag)
    return None


def llm_text(
    ann_type: str,
    text: str,
    label_classes: Optional[Sequence[Any]] = None,
    model: Optional[str] = None,
) -> AdapterResult:
    labels = _label_ids(label_classes)
    system = "You are a data labeling assistant. Reply with a single JSON object, no markdown."
    if ann_type in ("ner", "re"):
        allowed = labels or ["PER", "ORG", "LOC"]
        user = (
            f"Extract named entities. Allowed labels: {', '.join(allowed)}.\n"
            'Return {"spans":[{"start":int,"end":int,"label":str,"text":str,"confidence":float}]}\n'
            "Offsets are 0-based character indices in the following UTF-8 string.\n\n"
            f"Text:\n{text}"
        )
        data = llm_chat(system, user, model=model)
        hits: List[LabelHit] = []
        spans: List[Dict[str, Any]] = []
        for item in data.get("spans") or []:
            if not isinstance(item, dict):
                continue
            frag = str(item.get("text") or "")
            off = _fix_span_offsets(text, item.get("start"), item.get("end"), frag)
            if not off:
                continue
            lab = str(item.get("label") or allowed[0])
            conf = float(item.get("confidence") or 0.75)
            hits.append(LabelHit(lab, text[off[0] : off[1]], off[0], off[1], conf))
            spans.append(
                {
                    "id": _new_id("al"),
                    "start": off[0],
                    "end": off[1],
                    "label": lab,
                    "text": text[off[0] : off[1]],
                    "confidence": conf,
                }
            )
        overall = sum(h.confidence for h in hits) / len(hits) if hits else float(data.get("confidence") or 0.5)
        return AdapterResult(
            hits=hits,
            overall_confidence=round(overall, 4),
            model=model or settings.AUTO_LABEL_LLM_MODEL,
            adapter="llm",
            raw_response=json.dumps(data, ensure_ascii=False)[:4000],
            payload_patch={"spans": spans},
        )
    if ann_type == "text_classify":
        user = (
            f"Classify the text. Candidate labels: {', '.join(labels) or 'unspecified'}.\n"
            'Return {"labels":["..."],"confidence":0.0}\n\n'
            f"Text:\n{text}"
        )
        data = llm_chat(system, user, model=model)
        labs = [str(x) for x in (data.get("labels") or []) if x]
        conf = float(data.get("confidence") or 0.7)
        return AdapterResult(
            hits=[LabelHit(labs[0] if labs else "other", ",".join(labs), confidence=conf)],
            overall_confidence=conf,
            model=model or settings.AUTO_LABEL_LLM_MODEL,
            adapter="llm",
            raw_response=json.dumps(data, ensure_ascii=False)[:4000],
            payload_patch={"classification_labels": labs},
        )
    if ann_type == "sentiment":
        user = f'Return {{"sentiment":"positive|negative|neutral","confidence":0.0}}\n\nText:\n{text}'
        data = llm_chat(system, user, model=model)
        sent = str(data.get("sentiment") or "neutral")
        conf = float(data.get("confidence") or 0.7)
        return AdapterResult(
            hits=[LabelHit(sent, sent, confidence=conf)],
            overall_confidence=conf,
            model=model or settings.AUTO_LABEL_LLM_MODEL,
            adapter="llm",
            raw_response=json.dumps(data, ensure_ascii=False)[:4000],
            payload_patch={"sentiment": sent},
        )
    if ann_type == "summarization":
        user = f'Return {{"summary":"...","confidence":0.0}}\n\nText:\n{text}'
        data = llm_chat(system, user, model=model)
        summary = str(data.get("summary") or "")
        conf = float(data.get("confidence") or 0.7)
        return AdapterResult(
            hits=[LabelHit("summary", summary, confidence=conf)],
            overall_confidence=conf,
            model=model or settings.AUTO_LABEL_LLM_MODEL,
            adapter="llm",
            raw_response=json.dumps(data, ensure_ascii=False)[:4000],
            payload_patch={"summary": summary},
        )
    if ann_type == "translation":
        user = f'Return {{"translation":"...","confidence":0.0}} Translate into Chinese if source is not Chinese, else English.\n\nText:\n{text}'
        data = llm_chat(system, user, model=model)
        trans = str(data.get("translation") or "")
        conf = float(data.get("confidence") or 0.7)
        return AdapterResult(
            hits=[LabelHit("translation", trans, confidence=conf)],
            overall_confidence=conf,
            model=model or settings.AUTO_LABEL_LLM_MODEL,
            adapter="llm",
            raw_response=json.dumps(data, ensure_ascii=False)[:4000],
            payload_patch={"translation": trans},
        )
    if ann_type == "qa_pair":
        user = f'Return {{"question":"...","answer":"...","confidence":0.0}} based on the text.\n\nText:\n{text}'
        data = llm_chat(system, user, model=model)
        qa = {
            "question": str(data.get("question") or ""),
            "answer": str(data.get("answer") or ""),
        }
        conf = float(data.get("confidence") or 0.7)
        return AdapterResult(
            hits=[LabelHit("qa", qa["answer"], confidence=conf)],
            overall_confidence=conf,
            model=model or settings.AUTO_LABEL_LLM_MODEL,
            adapter="llm",
            raw_response=json.dumps(data, ensure_ascii=False)[:4000],
            payload_patch={"qa_pairs": [qa]},
        )
    # fallback: caption-like
    user = f'Return {{"caption":"...","confidence":0.0}}\n\nText:\n{text}'
    data = llm_chat(system, user, model=model)
    cap = str(data.get("caption") or data.get("summary") or "")
    conf = float(data.get("confidence") or 0.65)
    return AdapterResult(
        hits=[LabelHit("caption", cap, confidence=conf)],
        overall_confidence=conf,
        model=model or settings.AUTO_LABEL_LLM_MODEL,
        adapter="llm",
        raw_response=json.dumps(data, ensure_ascii=False)[:4000],
        payload_patch={"caption": cap},
    )


def llm_caption(text: str, image_url: Optional[str], model: Optional[str] = None) -> AdapterResult:
    system = "You are a data labeling assistant. Reply with a single JSON object, no markdown."
    user = 'Describe the image or text. Return {"caption":"...","confidence":0.0}'
    if text:
        user += f"\n\nHint:\n{text}"
    data = llm_chat(system, user, model=model, image_url=image_url)
    cap = str(data.get("caption") or "")
    conf = float(data.get("confidence") or 0.7)
    return AdapterResult(
        hits=[LabelHit("caption", cap, confidence=conf)],
        overall_confidence=conf,
        model=model or settings.AUTO_LABEL_LLM_MODEL,
        adapter="llm",
        raw_response=json.dumps(data, ensure_ascii=False)[:4000],
        payload_patch={"caption": cap},
    )


def llm_vqa(text: str, image_url: Optional[str], question: str = "", model: Optional[str] = None) -> AdapterResult:
    system = "You are a data labeling assistant. Reply with a single JSON object, no markdown."
    q = question or "What is shown?"
    user = f'Return {{"question":"...","answer":"...","confidence":0.0}}\nQuestion: {q}'
    if text:
        user += f"\nContext:\n{text}"
    data = llm_chat(system, user, model=model, image_url=image_url)
    qa = {
        "question": str(data.get("question") or q),
        "answer": str(data.get("answer") or ""),
    }
    conf = float(data.get("confidence") or 0.7)
    return AdapterResult(
        hits=[LabelHit("vqa", qa["answer"], confidence=conf)],
        overall_confidence=conf,
        model=model or settings.AUTO_LABEL_LLM_MODEL,
        adapter="llm",
        raw_response=json.dumps(data, ensure_ascii=False)[:4000],
        payload_patch={"vqa": qa},
    )


# ---------- Whisper / OCR HTTP ----------

def whisper_asr(audio_url: str, text_hint: str = "") -> AdapterResult:
    url = (settings.AUTO_LABEL_WHISPER_ENDPOINT or "").strip()
    if not url:
        raise AutoLabelConfigError("未配置 AUTO_LABEL_WHISPER_ENDPOINT")
    data = post_json(
        url,
        {"audio_url": audio_url, "text_hint": text_hint},
        _auth_headers(settings.AUTO_LABEL_WHISPER_API_KEY),
    )
    transcript = str(data.get("text") or data.get("transcript") or "")
    segs_in = data.get("segments") or []
    segments: List[Dict[str, Any]] = []
    for i, item in enumerate(segs_in):
        if not isinstance(item, dict):
            continue
        if "start_ms" in item or "end_ms" in item:
            start_ms = int(item.get("start_ms") or 0)
            end_ms = int(item.get("end_ms") or start_ms)
        else:
            start_ms = int(float(item.get("start") or 0) * 1000)
            end_ms = int(float(item.get("end") or 0) * 1000)
        segments.append(
            {
                "id": str(item.get("id") or _new_id("seg")),
                "start_ms": start_ms,
                "end_ms": max(end_ms, start_ms),
                "speaker": str(item.get("speaker") or f"说话人 {chr(65 + (i % 26))}"),
                "text": str(item.get("text") or ""),
                "emotion": str(item.get("emotion") or ""),
            }
        )
    if not segments and transcript:
        segments = [
            {
                "id": _new_id("seg"),
                "start_ms": 0,
                "end_ms": 3000,
                "speaker": "说话人 A",
                "text": transcript,
                "emotion": "",
            }
        ]
    conf = float(data.get("confidence") or 0.8)
    if not conf and segments:
        scores = [float(s.get("confidence") or 0) for s in segs_in if isinstance(s, dict)]
        conf = sum(scores) / max(len(scores), 1) if scores else 0.75
    return AdapterResult(
        hits=[LabelHit("transcript", transcript, confidence=conf)],
        overall_confidence=conf,
        model=str(data.get("model") or "whisper_http"),
        adapter="whisper",
        raw_response=json.dumps(data, ensure_ascii=False)[:4000],
        payload_patch={"transcript": transcript, "segments": segments},
    )


def _bbox_xywh(raw: Any) -> Optional[List[float]]:
    """Accept pixel xywh, xyxy, or a quad [[x,y],...]. Default 4-tuple is xywh."""
    if isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], (list, tuple)):
        xs = [float(p[0]) for p in raw if isinstance(p, (list, tuple)) and len(p) >= 2]
        ys = [float(p[1]) for p in raw if isinstance(p, (list, tuple)) and len(p) >= 2]
        if xs and ys:
            x0, y0 = min(xs), min(ys)
            return [x0, y0, max(xs) - x0, max(ys) - y0]
    if isinstance(raw, (list, tuple)) and len(raw) >= 4 and all(
        isinstance(x, (int, float)) for x in raw[:4]
    ):
        x, y, w, h = [float(v) for v in raw[:4]]
        return [x, y, w, h]
    return None


def ocr_http(image_url: str) -> AdapterResult:
    url = (settings.AUTO_LABEL_OCR_ENDPOINT or "").strip()
    if not url:
        raise AutoLabelConfigError("未配置 AUTO_LABEL_OCR_ENDPOINT")
    data = post_json(
        url,
        {"image_url": image_url},
        _auth_headers(settings.AUTO_LABEL_OCR_API_KEY),
    )
    items = data.get("texts") or data.get("spans") or data.get("results") or []
    spans: List[Dict[str, Any]] = []
    hits: List[LabelHit] = []
    for item in items:
        text = ""
        bbox_raw: Any = None
        conf = 0.75
        label = "text"
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("transcription") or "")
            bbox_raw = item.get("bbox") or item.get("box") or item.get("points")
            conf = float(item.get("confidence") or item.get("score") or 0.75)
            label = str(item.get("label") or "text")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            # PaddleOCR: [quad, (text, conf)]
            bbox_raw = item[0]
            rec = item[1]
            if isinstance(rec, (list, tuple)):
                text = str(rec[0])
                if len(rec) > 1:
                    try:
                        conf = float(rec[1])
                    except (TypeError, ValueError):
                        conf = 0.75
            else:
                text = str(rec)
        bbox = _bbox_xywh(bbox_raw) or [20, 20, 120, 32]
        if not text:
            continue
        spans.append(
            {
                "id": _new_id("ocr"),
                "text": text,
                "label": label,
                "bbox": bbox,
                "confidence": conf,
            }
        )
        hits.append(LabelHit(label, text, confidence=conf))
    overall = float(data.get("confidence") or 0)
    if not overall:
        overall = sum(h.confidence for h in hits) / len(hits) if hits else 0.5
    return AdapterResult(
        hits=hits,
        overall_confidence=round(overall, 4),
        model=str(data.get("model") or "ocr_http"),
        adapter="ocr",
        raw_response=json.dumps(data, ensure_ascii=False)[:4000],
        payload_patch={"spans": spans},
    )


# ---------- router ----------

def _need_endpoint(kind: str) -> NoReturn:
    names = {
        "llm": "AUTO_LABEL_LLM_BASE_URL",
        "whisper": "AUTO_LABEL_WHISPER_ENDPOINT",
        "ocr": "AUTO_LABEL_OCR_ENDPOINT",
    }
    raise AutoLabelConfigError(
        f"未配置 {names.get(kind, kind)}。"
        "请在环境变量中设置推理 HTTP 端点，或开启 DEBUG / AUTO_LABEL_ALLOW_DEMO。"
    )


def infer(
    *,
    modality: str,
    ann_type: str,
    content: Dict[str, Any],
    label_classes: Optional[Sequence[Any]] = None,
    model: Optional[str] = None,
) -> AdapterResult:
    if not settings.AUTO_LABEL_ENABLED:
        raise AutoLabelConfigError("AUTO_LABEL_ENABLED=false")
    if ann_type in IMAGE_2D_TYPES or modality == "image_2d":
        raise AutoLabelUnsupportedError("2D 图像请使用 /tasks/{id}/prelabel/run，不走 /auto-label。")
    if ann_type in UNSUPPORTED_TYPES:
        raise AutoLabelUnsupportedError(f"类型 {ann_type} 未接入自动标注适配器，请人工标注。")

    text = str(content.get("text") or content.get("title") or "")
    audio_url = content.get("audio_url") or ""
    image_url = content.get("image_url") or ""

    if modality == "text":
        if llm_configured():
            if not text.strip():
                raise AutoLabelUnsupportedError("任务没有可标注文本")
            return llm_text(ann_type, text, label_classes, model=model)
        if demo_allowed():
            if ann_type in ("ner", "re"):
                return demo_ner(text, label_classes)
            if ann_type == "text_classify":
                return demo_classify(text, label_classes)
            if ann_type == "sentiment":
                return demo_sentiment(text)
            if ann_type == "translation":
                patch = {"translation": f"（演示译文）{text[:80]}"}
                return AdapterResult(
                    hits=[LabelHit("translation", patch["translation"], confidence=0.5)],
                    overall_confidence=0.5,
                    payload_patch=patch,
                )
            if ann_type == "qa_pair":
                qa = {"question": text[:40] or "这段在讲什么？", "answer": "（演示）见原文。"}
                return AdapterResult(
                    hits=[LabelHit("qa", qa["answer"], confidence=0.5)],
                    overall_confidence=0.5,
                    payload_patch={"qa_pairs": [qa]},
                )
            return demo_summary(text)
        _need_endpoint("llm")

    if modality == "audio":
        result: AdapterResult
        if whisper_configured() and audio_url:
            result = whisper_asr(str(audio_url), text)
        elif demo_allowed():
            result = demo_asr(text)
        elif whisper_configured() and not audio_url:
            raise AutoLabelUnsupportedError("语音任务缺少 audio_url")
        else:
            _need_endpoint("whisper")
        if ann_type == "emotion_audio":
            sent = demo_sentiment(result.payload_patch.get("transcript") or text)
            result.payload_patch["emotion"] = sent.payload_patch.get("sentiment")
            result.hits.extend(sent.hits)
        if ann_type == "tts_label" and result.payload_patch.get("mos") is None:
            result.payload_patch["mos"] = 3.5
        return result

    if modality == "ocr":
        if ocr_configured() and image_url:
            return ocr_http(str(image_url))
        if demo_allowed():
            return demo_ocr()
        if ocr_configured() and not image_url:
            raise AutoLabelUnsupportedError("OCR 任务缺少 image_url")
        _need_endpoint("ocr")

    if modality == "multimodal":
        if ann_type == "vqa":
            if llm_configured():
                return llm_vqa(text, image_url or None, model=model)
            if demo_allowed():
                return AdapterResult(
                    hits=[LabelHit("vqa", "（演示回答）", confidence=0.5)],
                    overall_confidence=0.5,
                    payload_patch={"vqa": {"question": text or "图中有什么？", "answer": "（演示回答）"}},
                )
            _need_endpoint("llm")
        if llm_configured():
            return llm_caption(text, image_url or None, model=model)
        if demo_allowed():
            return demo_caption(text)
        _need_endpoint("llm")

    if modality == "video" and ann_type == "video_caption":
        if llm_configured():
            return llm_caption(text, None, model=model)
        if demo_allowed():
            return demo_caption(text)
        _need_endpoint("llm")

    raise AutoLabelUnsupportedError(f"模态 {modality}/{ann_type} 未接入自动标注")
