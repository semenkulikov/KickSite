from abc import ABC, abstractmethod


class BaseImporter(ABC):
    separator = '\r\n'

    @classmethod
    @abstractmethod
    def commit_to_db(cls, data: str) -> tuple[str, int]:
        raise NotImplementedError('This method must be redefined')
