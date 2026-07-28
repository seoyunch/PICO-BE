import functools
import logging
import time

logger = logging.getLogger("pico.perf")
# uvicorn이 자체 dictConfig로 root 로거 핸들러를 건드릴 수 있어서, 이 로거에는
# 항상 보이도록 전용 핸들러를 직접 붙인다(uvicorn --reload로 띄워도 안 가려짐).
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


def timed(label: str):
    """비동기 함수 실행 시간을 재서 pico.perf 로거로 남긴다.

    Langfuse가 같은 정보를 이미 추적하지만, 대시보드를 열지 않고도 터미널에서
    바로 어디가 느린지 보려고 얕은 로컬 타이머를 하나 더 둔다.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.monotonic() - start
                logger.info("perf label=%s elapsed=%.2fs", label, elapsed)

        return wrapper

    return decorator
