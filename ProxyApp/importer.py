from django.core.exceptions import ValidationError
from django.contrib import messages
from ServiceApp import BaseImporter
from ServiceApp.Validators import validate_socks5_address
from ProxyApp.models import Proxy


class ProxyImporter(BaseImporter):
    @classmethod
    def commit_to_db(cls, data: str) -> tuple[str, int]:
        objs: list[Proxy] = list()

        for proxy_url in data.split(cls.separator):
            try:
                validate_socks5_address(proxy_url)
            except ValidationError:
                continue

            if Proxy.objects.filter(url=proxy_url).count():
                continue

            objs.append(Proxy(url=proxy_url))

        Proxy.objects.bulk_create(objs)

        return f'Создано {len(objs)} новых записей', messages.INFO
