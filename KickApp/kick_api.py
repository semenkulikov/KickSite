import asyncio
from kickpython import KickClient
from KickApp.models import KickAccount

async def update_all_kick_tokens():
    """
    Проходит по всем KickAccount с логином и паролем, обновляет токен через kickpython и сохраняет в БД
    """
    accounts = list(KickAccount.objects.filter(password__isnull=False).exclude(password=""))
    for acc in accounts:
        try:
            client = KickClient()
            await client.login(acc.login, acc.password)
            # Получаем access_token (JWT)
            token = client.token
            if token and token != acc.token:
                acc.token = token
                acc.save(update_fields=["token"])
                print(f"[kick_api] Updated token for {acc.login}")
        except Exception as e:
            print(f"[kick_api] Failed to update token for {acc.login}: {e}")

async def send_kick_message(login, password, channel, message):
    """
    Логинится через kickpython и отправляет сообщение в чат
    """
    client = KickClient()
    await client.login(login, password)
    await client.join_channel(channel)
    await client.send_message(channel, message)
    print(f"[kick_api] Sent message to {channel} from {login}")

# Для синхронного вызова из Django:
def update_all_kick_tokens_sync():
    asyncio.run(update_all_kick_tokens())

def send_kick_message_sync(login, password, channel, message):
    asyncio.run(send_kick_message(login, password, channel, message)) 