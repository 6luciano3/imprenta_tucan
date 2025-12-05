from django.db import transaction


class UnitOfWork:
    def __enter__(self):
        self._atomic = transaction.atomic()
        self._atomic.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._atomic.__exit__(exc_type, exc, tb)
