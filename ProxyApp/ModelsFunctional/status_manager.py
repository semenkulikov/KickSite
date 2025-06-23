from typing import Callable
from django.db.transaction import atomic


class ModelStatusManager:
    save: Callable

    @property
    def is_good(self) -> bool:
        return self.status

    @property
    def is_bad(self) -> bool:
        return not self.status

    @atomic
    def mark_as_good(self):
        self.status = True
        self.save()
        return self

    @atomic
    def mark_as_bad(self):
        self.status = False
        self.save()
        return self
