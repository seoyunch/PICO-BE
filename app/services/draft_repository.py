# TODO: ERD 확정 후 실제 DB(SQLAlchemy 등)로 교체


class DraftRepository:
    def __init__(self) -> None:
        self._drafts: dict[str, str] = {}

    def save(self, thread_id: str, draft: str) -> None:
        self._drafts[thread_id] = draft

    def get(self, thread_id: str) -> str | None:
        return self._drafts.get(thread_id)


draft_repository = DraftRepository()
