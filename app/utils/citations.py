import re

_URL_PATTERN = re.compile(r"https?://[^\s)\]]+")


def verify_citations(analysis: str, search_results: list[dict]) -> str:
    """검색 결과에 실제로 없는 출처를 인용했으면 analysis 끝에 경고를 붙여서 반환한다."""
    known_links = {r["link"] for r in search_results if r.get("link")}
    cited_links = set(_URL_PATTERN.findall(analysis))
    unverified = sorted(cited_links - known_links)

    if not unverified:
        return analysis

    warning = "\n\n⚠️ 검증 안 된 출처(실제 검색 결과에 없음):\n" + "\n".join(
        f"- {link}" for link in unverified
    )
    return analysis + warning
