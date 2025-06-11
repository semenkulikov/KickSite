from django.core.exceptions import ValidationError
from django.contrib import messages
from ServiceApp import BaseImporter
from ServiceApp.Validators import validate_twitch_token
from TwitchApp.models import TwitchAccount
from ProxyApp.models import Proxy
import logging

logger = logging.getLogger(__name__)


class TwitchAccountImporter(BaseImporter):
    @classmethod
    def commit_to_db(cls, data: str) -> tuple[str, int]:
        added_count = int()
        failed_count = int()

        for account_data in data.split(cls.separator):
            if ' ' not in account_data:
                continue

            login, token, *_ = account_data.split(' ')

            try:
                validate_twitch_token(token)
            except ValidationError:
                failed_count += 1
                continue

            if TwitchAccount.objects.filter(login=login).count():
                failed_count += 1
                continue

            try:
                ta_obj = TwitchAccount(login=login, token=token)
                # Попробуем назначить прокси, но не будем падать если их нет
                free_proxy = Proxy.get_valid_twitch_free_proxy()
                if free_proxy:
                    ta_obj.proxy = free_proxy
                ta_obj.save()
                added_count += 1
                logger.info(f"Created TwitchAccount {login} with proxy: {ta_obj.proxy.url if ta_obj.proxy else 'None'}")
            except Exception as e:
                logger.error(f"Failed to create TwitchAccount {login}: {str(e)}")
                failed_count += 1
                continue

        result_msg = f'Создано {added_count} новых записей'
        if failed_count > 0:
            result_msg += f', пропущено {failed_count} записей'
        
        return result_msg, messages.INFO
