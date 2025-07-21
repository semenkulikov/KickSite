#!/usr/bin/env python3
"""
Тестовый скрипт для проверки отправки сообщений через HTTP прокси
"""

import asyncio
import logging
import cloudscraper
import urllib.parse
import time
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("proxy_test")

# Тестовые прокси от Pavel
PROXY_LIST = [
    "pr.lunaproxy.com:12233:user-test1_S4bwJ:Test123",
    "pr.lunaproxy.com:12233:user-test1_S4bwJ-sessid-allhrbkjgtbo7o7phqo-sesstime-90:Test123",
    "pr.lunaproxy.com:12233:user-test1_S4bwJ-sessid-allftfyoyp2k8kx4no4-sesstime-90:Test123",
]

# Тестовые данные аккаунта (замени на реальные)
TEST_TOKEN = "227163000|1vy337VnGuWerycaB3Dcg9DZYf5OQdWNloa0jUUQ"
TEST_CHANNEL = "dwolf"
TEST_MESSAGE = "Тест прокси"

def convert_proxy_format(proxy_str):
    """
    Конвертирует прокси из формата host:port:user:pass в HTTP формат
    """
    try:
        parts = proxy_str.split(':')
        if len(parts) == 4:
            host, port, username, password = parts
            return f"http://{username}:{password}@{host}:{port}"
        else:
            logger.error(f"Неверный формат прокси: {proxy_str}")
            return None
    except Exception as e:
        logger.error(f"Ошибка парсинга прокси {proxy_str}: {e}")
        return None

async def test_proxy_send(proxy_str, token, channel, message):
    """
    Тестирует отправку сообщения через прокси
    """
    logger.info(f"Тестируем прокси: {proxy_str}")
    
    # Конвертируем прокси в HTTP формат
    http_proxy = convert_proxy_format(proxy_str)
    if not http_proxy:
        return False
    
    logger.info(f"HTTP прокси: {http_proxy}")
    
    # Парсим токен
    if not token or '|' not in token:
        logger.error("Неверный формат токена")
        return False
    
    user_id, token_part = token.split('|', 1)
    session_raw = token
    xsrf_token = token_part
    session_decoded = urllib.parse.unquote(session_raw)
    
    # Формируем куки
    cookies = {
        'session_token': session_raw,
        'XSRF-TOKEN': xsrf_token
    }
    
    # Создаем scraper с прокси
    scraper = cloudscraper.create_scraper()
    scraper.proxies = {
        'http': http_proxy,
        'https': http_proxy
    }
    
    # Тестируем подключение к каналу
    try:
        logger.info(f"Получаем информацию о канале: {channel}")
        channel_response = scraper.get(
            f"https://kick.com/api/v2/channels/{channel}",
            cookies=cookies,
            headers={
                'Authorization': f'Bearer {session_decoded}',
                'X-XSRF-TOKEN': xsrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Referer': f'https://kick.com/{channel}',
                'cluster': 'v2'
            },
            timeout=30
        )
        
        logger.info(f"Статус ответа: {channel_response.status_code}")
        logger.debug(f"Ответ: {channel_response.text}")
        
        if channel_response.status_code != 200:
            logger.error(f"Ошибка получения канала: {channel_response.status_code}")
            return False
        
        channel_data = channel_response.json()
        chatroom_id = channel_data.get('chatroom', {}).get('id')
        
        if not chatroom_id:
            logger.error("Не найден chatroom_id")
            return False
        
        logger.info(f"Chatroom ID: {chatroom_id}")
        
        # Отправляем тестовое сообщение
        message_ref = str(int(time.time() * 1000))
        payload = {
            'content': message,
            'type': 'message',
            'message_ref': message_ref
        }
        
        logger.info(f"Отправляем сообщение: {message}")
        response = scraper.post(
            f"https://kick.com/api/v2/messages/send/{chatroom_id}",
            cookies=cookies,
            headers={
                'Authorization': f'Bearer {session_decoded}',
                'X-XSRF-TOKEN': xsrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Referer': f'https://kick.com/{channel}',
                'cluster': 'v2'
            },
            json=payload,
            timeout=30
        )
        
        logger.info(f"Статус отправки: {response.status_code}")
        logger.debug(f"Ответ отправки: {response.text}")
        
        if response.status_code == 200:
            logger.info("✅ Сообщение отправлено успешно!")
            return True
        else:
            logger.error(f"❌ Ошибка отправки: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании прокси: {e}")
        return False

async def main():
    """
    Основная функция тестирования
    """
    logger.info("🚀 Начинаем тестирование прокси")
    
    results = []
    
    for i, proxy in enumerate(PROXY_LIST):
        logger.info(f"\n{'='*50}")
        logger.info(f"Тест {i+1}/{len(PROXY_LIST)}")
        
        success = await test_proxy_send(proxy, TEST_TOKEN, TEST_CHANNEL, TEST_MESSAGE)
        results.append((proxy, success))
        
        # Пауза между тестами
        if i < len(PROXY_LIST) - 1:
            await asyncio.sleep(5)
    
    # Выводим результаты
    logger.info(f"\n{'='*50}")
    logger.info("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    
    for proxy, success in results:
        status = "✅ УСПЕХ" if success else "❌ НЕУДАЧА"
        logger.info(f"{proxy}: {status}")
    
    success_count = sum(1 for _, success in results if success)
    logger.info(f"\nИтого: {success_count}/{len(results)} прокси работают")

if __name__ == "__main__":
    asyncio.run(main()) 