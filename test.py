import asyncio
from kickpython import KickClient

async def test_login_and_send():
    client = KickClient()
    await client.login("yomillerr", "LE8519pACYg@")
    await client.join_channel("mk14ebr")
    await client.send_message("mk14ebr", "тестовое сообщение")
    print("Сообщение отправлено!")

if __name__ == "__main__":
    asyncio.run(test_login_and_send())
