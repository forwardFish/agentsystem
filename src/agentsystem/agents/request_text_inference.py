from __future__ import annotations

import re


TITLE_SIGNALS: tuple[str, ...] = ("title", "标题", "鏍囬")
SUBTITLE_SIGNALS: tuple[str, ...] = ("subtitle", "副标题", "鍓爣棰")
ENGLISH_REQUEST_VERBS: tuple[str, ...] = ("add", "set", "use", "show", "insert", "create", "render")
CHINESE_REQUEST_VERBS: tuple[str, ...] = ("加", "添加", "增加", "新增", "补", "补上", "显示", "写上", "放", "放上")


def infer_requested_text(candidates: list[str], *, target_kind: str) -> str | None:
    normalized = [str(item).strip() for item in candidates if str(item).strip()]
    if not normalized:
        return None

    for candidate in normalized:
        quoted = _extract_quoted_text(candidate)
        if quoted:
            return quoted

    patterns = _build_patterns(target_kind)
    for candidate in normalized:
        direct = _infer_from_patterns(candidate, patterns)
        if direct:
            return direct

    for candidate in normalized:
        inline = _infer_inline_request_text(candidate, target_kind)
        if inline:
            return inline

    signals = SUBTITLE_SIGNALS if target_kind == "subtitle" else TITLE_SIGNALS
    for candidate in normalized:
        suffix = _infer_after_request_delimiter(candidate, signals)
        if suffix:
            return suffix
    return None


def _build_patterns(target_kind: str) -> list[str]:
    signal_pattern = _signal_pattern(target_kind)
    english_signal = r"subtitle\b" if target_kind == "subtitle" else r"(?<!sub)title\b"
    english_verbs = "|".join(ENGLISH_REQUEST_VERBS)

    return [
        rf"add\s+(?:a\s+|an\s+)?{english_signal}[:：]?\s*(.+)$",
        rf"add\s+(?:a\s+|an\s+)?(.+?)\s+{english_signal}$",
        rf"{signal_pattern}[:：]?\s*(.+)$",
        rf"(?:{english_verbs})\s+(?:a\s+|an\s+)?(.+?)\s+{english_signal}$",
        rf".*?(?:把){signal_pattern}(?:改成|设为|写成)\s*(.+)$",
    ]


def _infer_inline_request_text(candidate: str, target_kind: str) -> str | None:
    signal_pattern = _signal_pattern(target_kind)
    chinese_verbs = "|".join(CHINESE_REQUEST_VERBS)
    english_verbs = "|".join(ENGLISH_REQUEST_VERBS)
    patterns = [
        rf".*?(?:{chinese_verbs})(?:一个|个)?\s*(.+?{signal_pattern})$",
        rf"(?:{english_verbs})\s+(?:a\s+|an\s+)?(.+?\s+{signal_pattern})$",
    ]
    return _infer_from_patterns(candidate, patterns)


def _signal_pattern(target_kind: str) -> str:
    if target_kind == "subtitle":
        return r"(?:subtitle\b|副标题|鍓爣棰)"
    return r"(?:(?<!sub)title\b|(?<!副)标题|鏍囬)"


def _infer_from_patterns(candidate: str, patterns: list[str]) -> str | None:
    cleaned = _clean_text(candidate)
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if not match:
            continue
        value = _clean_text(match.group(1))
        if value and not _looks_like_signal_only(value):
            return value
    return None


def _infer_after_request_delimiter(candidate: str, signals: tuple[str, ...]) -> str | None:
    if not _contains_signal(candidate, signals):
        return None

    for delimiter in ("：", ":", "?", "？"):
        if delimiter not in candidate:
            continue
        _, suffix = candidate.split(delimiter, 1)
        cleaned = _clean_text(suffix)
        if cleaned and not _looks_like_signal_only(cleaned):
            return cleaned
    return None


def _contains_signal(candidate: str, signals: tuple[str, ...]) -> bool:
    target_kind = "subtitle" if signals == SUBTITLE_SIGNALS else "title"
    return bool(re.search(_signal_pattern(target_kind), candidate, re.IGNORECASE))


def _looks_like_signal_only(value: str) -> bool:
    lowered = value.lower()
    return lowered in {"title", "subtitle"} or value in {"标题", "副标题", "鏍囬", "鍓爣棰"}


def _clean_text(value: str) -> str:
    return value.strip(" \t\r\n,.!?:;，。！？：；'\"“”‘’「」『』")


def _extract_quoted_text(text: str) -> str | None:
    match = re.search(r"[\"'“”‘’「」『』](.*?)[\"'“”‘’「」『』]", text)
    if match:
        cleaned = _clean_text(match.group(1))
        if cleaned:
            return cleaned
    return None
