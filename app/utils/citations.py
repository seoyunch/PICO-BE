import logging
import re

logger = logging.getLogger("pico.citations")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

_INDEX_PATTERN = re.compile(r"\[(\d+)\]")
_URL_PATTERN = re.compile(r"https?://[^\s)\]<>\"']+")
_ANCHOR_PATTERN = re.compile(
    r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL
)
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

_UNVERIFIED_MARKER = "(검증되지 않은 출처 삭제됨)"


def resolve_citations(
    analysis: str, search_results: list[dict], *, stage: str | None = None
) -> str:
    """모델이 만들어낸 출처 표기를 실제 검색 결과로 검증/치환한다.

    CLOVA는 지시를 무시하고 세 가지 방식으로 출처를 지어내는 게 관찰됐다: (1) 번호
    인용([n])은 정상 경로라 index로 실제 링크를 채워 넣고, (2) <a href="...">
    같은 HTML 앵커 태그, (3) 맨 URL 텍스트 — 둘 다 검색 결과에 실제로 없는 링크일
    수 있으므로 known_links와 대조해서 없으면 삭제한다. resolved/stripped 건수를
    로그로 남겨 환각률(stripped / (resolved + stripped))을 추적할 수 있게 한다.
    """
    # 순서가 중요하다: URL/앵커 정제를 먼저 끝내고 [n] 인덱스 치환을 맨 마지막에 해야
    # 한다. 반대로 하면 인덱스 치환으로 갓 삽입한 진짜 링크가 뒤이은 URL 정규식 패스에
    # 다시 걸려서 resolved/stripped 카운트가 중복 집계된다.
    known_links = {r["link"] for r in search_results if r.get("link")}
    resolved = 0
    stripped = 0

    def _replace_anchor(match: re.Match) -> str:
        nonlocal resolved, stripped
        href, label = match.group(1), match.group(2).strip()
        if href in known_links:
            resolved += 1
            return f"{label} ({href})"
        stripped += 1
        return label or _UNVERIFIED_MARKER

    text = _ANCHOR_PATTERN.sub(_replace_anchor, analysis)
    # <a> 외에 다른 HTML 태그가 남아있으면(예: <b>, <p>) 프런트가 렌더링하지 않으므로 제거한다.
    text = _HTML_TAG_PATTERN.sub("", text)

    def _strip_unverified_url(match: re.Match) -> str:
        nonlocal resolved, stripped
        if match.group(0) in known_links:
            resolved += 1
            return match.group(0)
        stripped += 1
        return _UNVERIFIED_MARKER

    text = _URL_PATTERN.sub(_strip_unverified_url, text)

    def _replace_index(match: re.Match) -> str:
        nonlocal resolved
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(search_results):
            resolved += 1
            r = search_results[idx]
            return f"{r.get('title', '')} ({r.get('link', '')})"
        return match.group(0)

    text = _INDEX_PATTERN.sub(_replace_index, text)

    total = resolved + stripped
    if total:
        logger.info(
            "citation_resolution stage=%s resolved=%d stripped=%d hallucination_rate=%.2f",
            stage,
            resolved,
            stripped,
            stripped / total,
        )

    return text
