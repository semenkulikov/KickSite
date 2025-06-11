from typing import Any, Union


class StorageManager:
    """
    Storage structure:
        {
            "<key>": {"obj": <Any>, "owners": set[str], "status": Union[None, bool]},
            "<key>": {"obj": <Any>, "owners": set[str], "status": Union[None, bool]},
            "<key>": {"obj": <Any>, "owners": set[str], "status": Union[None, bool]},
            "<key>": {"obj": <Any>, "owners": set[str], "status": Union[None, bool]}
        }
    """
    __storage = dict()

    def count(self) -> int:
        return len(self.__storage)

    def count_owners(self, key: str) -> int:
        if self.contains(key):
            return len(self.__storage[key]['owners'])
        return 0

    def contains(self, key: str) -> bool:
        return key in self.__storage

    def contains_owner(self, key: str, owner: str) -> bool:
        if self.contains(key):
            return owner in self.__storage[key]['owners']
        return False

    def add(self, key: str, owner: str, obj: Any, forced: bool = False):
        if forced:
            self.__storage[key] = {'obj': obj, 'owners': {owner}, 'status': False}
        elif not self.contains(key):
            self.__storage[key] = {'obj': obj, 'owners': {owner}, 'status': False}

    def add_owner(self, key: str, owner: str):
        if self.contains(key):
            self.__storage[key]['owners'].add(owner)

    def set_status(self, key: str, status: Union[None, bool]):
        if self.contains(key):
            self.__storage[key]['status'] = status

    def get_status(self, key: str) -> Union[None, bool]:
        if self.contains(key):
            return self.__storage[key]['status']
        return None

    def get(self, key: str) -> Union[None, Any]:
        if self.contains(key):
            return self.__storage[key]['obj']
        return None

    def remove(self, key: str, owner: str, forced: bool = False) -> Union[None, Any]:
        """
        Smart removal of an object from __storage.
        When None is returned, the object still has owners and the object itself is still in __storage.
        If an object is returned, then it has no owners left and is removed from __storage.
        The forced flag forced the object to be deleted.
        """
        if forced and self.contains(key):
            self.set_status(key, None)
            return self.__storage.pop(key)['obj']
        if not self.contains_owner(key, owner):
            return None
        self.__storage[key]['owners'].remove(owner)
        if len(self.__storage[key]['owners']) == 0:
            self.set_status(key, None)
            return self.__storage.pop(key)['obj']


if __name__ == '__main__':
    def main():
        # item 1
        key_1 = '1'
        owner_1 = 'Ben'
        item_1 = ...

        # item 2
        key_2 = '2'
        owner_2 = 'Joe'
        item_2 = ...

        storage = StorageManager()

        storage.add(key_1, owner_1, item_1)
        print(getattr(storage, f'_{storage.__class__.__name__}__storage'))
        storage.add_owner(key_1, owner_2)
        print(getattr(storage, f'_{storage.__class__.__name__}__storage'))
        print(storage.count_owners(key_1))

        storage.add(key_2, owner_2, item_2)
        storage.set_status(key_2, True)
        storage.set_status(key_1, True)
        print(getattr(storage, f'_{storage.__class__.__name__}__storage'))
        print(storage.count())

        print(storage.remove(key_1, owner_1))
        print(getattr(storage, f'_{storage.__class__.__name__}__storage'))
        print(storage.remove(key_1, owner_2))
        print(getattr(storage, f'_{storage.__class__.__name__}__storage'))
        print(storage.count_owners(key_1))


    main()
