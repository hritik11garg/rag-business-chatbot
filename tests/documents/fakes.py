"""Shared doubles for document use-case tests."""


class _CountQuery:
    def __init__(self, count):
        self._count = count

    def filter(self, *a, **k):
        return self

    def count(self):
        return self._count


class UnderQuotaDB:
    """Minimal DB double for tests that exercise the file-handling path.

    UploadDocumentUseCase checks the per-org document quota before writing
    anything, so those tests still need a db that can answer a count query.
    Reports zero documents, i.e. always under quota.
    """

    def __init__(self, count: int = 0):
        self.count = count

    def query(self, *a, **k):
        return _CountQuery(self.count)
