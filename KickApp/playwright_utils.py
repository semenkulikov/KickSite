import asyncio
import logging
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import os

logger = logging.getLogger(__name__)


class KickPlaywrightClient:
    """Клиент для работы с Kick через Playwright"""
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
    
    async def validate_account(self, token: Optional[str] = None, session_token: Optional[str] = None, proxy_url: Optional[str] = None) -> bool:
        """
        Проверка валидности аккаунта Kick через Playwright
        
        Args:
            token: Bearer token аккаунта
            session_token: Session token из cookies
            proxy_url: URL прокси (только HTTP/HTTPS)
            
        Returns:
            bool: True если аккаунт валиден, False если нет
        """
        try:
            async with async_playwright() as p:
                # Настройка прокси
                browser_options = {
                    'headless': self.headless,
                    'args': [
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor',
                        '--no-sandbox',
                        '--disable-dev-shm-usage'
                    ]
                }
                
                # Playwright поддерживает только HTTP/HTTPS прокси
                if proxy_url and (proxy_url.startswith('http://') or proxy_url.startswith('https://')):
                    try:
                        browser_options['proxy'] = {'server': proxy_url}
                    except Exception as e:
                        logger.warning(f"Failed to parse proxy URL {proxy_url}: {e}")
                elif proxy_url:
                    logger.warning(f"Skipping unsupported proxy {proxy_url} - Playwright supports only HTTP/HTTPS")
                
                browser = await p.chromium.launch(**browser_options)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                
                page = await context.new_page()
                
                # Устанавливаем cookies/tokens
                if session_token:
                    await context.add_cookies([{
                        'name': '__Secure-next-auth.session-token',
                        'value': session_token,
                        'domain': '.kick.com',
                        'path': '/',
                        'secure': True,
                        'httpOnly': True
                    }])
                
                # Устанавливаем заголовки
                headers = {
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Content-Type': 'application/json'
                }
                
                if token:
                    headers['Authorization'] = f'Bearer {token}'
                
                await page.set_extra_http_headers(headers)
                
                # Проверяем валидность через API эндпоинты
                try:
                    # Пробуем разные API эндпоинты для валидации
                    api_endpoints = [
                        'https://kick.com/api/v1/user',
                        'https://kick.com/api/v1/user/me',
                        'https://kick.com/api/v2/user/me'
                    ]
                    
                    for api_url in api_endpoints:
                        try:
                            response = await page.goto(api_url, timeout=self.timeout, wait_until='networkidle')
                            
                            if response and response.status == 200:
                                # Проверяем, что ответ содержит данные пользователя
                                content = await page.content()
                                if 'username' in content.lower() or 'user_id' in content.lower() or '"id"' in content:
                                    await browser.close()
                                    logger.debug(f"Account validation successful via {api_url}")
                                    return True
                        except Exception as e:
                            logger.debug(f"Failed to validate via {api_url}: {e}")
                            continue
                    
                    # Если API не работает, пробуем через основную страницу
                    response = await page.goto('https://kick.com/', timeout=self.timeout, wait_until='networkidle')
                    
                    if response and response.status == 200:
                        # Ждем загрузки страницы
                        await page.wait_for_timeout(2000)
                        
                        # Проверяем наличие элементов, указывающих на авторизацию
                        auth_indicators = [
                            '[data-testid="user-menu"]',
                            '.user-menu',
                            '.avatar',
                            '.profile-dropdown',
                            'button[aria-label*="profile"]',
                            'a[href*="/dashboard"]',
                            'a[href*="/settings"]'
                        ]
                        
                        for indicator in auth_indicators:
                            try:
                                element = await page.wait_for_selector(indicator, timeout=3000)
                                if element and await element.is_visible():
                                    await browser.close()
                                    logger.debug("Account validation successful via page elements")
                                    return True
                            except:
                                continue
                    
                    await browser.close()
                    logger.debug("Account validation failed - no valid indicators found")
                    return False
                    
                except PlaywrightTimeoutError:
                    logger.warning("Timeout during account validation")
                    await browser.close()
                    return False
                    
        except Exception as e:
            logger.error(f"Error validating account: {e}")
            return False
    
    async def send_message(self, channel: str, message: str, token: Optional[str] = None, session_token: Optional[str] = None, proxy_url: Optional[str] = None) -> bool:
        """
        Отправка сообщения в чат Kick через Playwright
        
        Args:
            channel: Название канала
            message: Текст сообщения
            token: Bearer token аккаунта
            session_token: Session token из cookies
            proxy_url: URL прокси (только HTTP/HTTPS)
            
        Returns:
            bool: True если сообщение отправлено, False если нет
        """
        try:
            async with async_playwright() as p:
                # Настройка прокси
                browser_options = {
                    'headless': self.headless,
                    'args': [
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor',
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-extensions'
                    ]
                }
                
                # Playwright поддерживает только HTTP/HTTPS прокси
                if proxy_url and (proxy_url.startswith('http://') or proxy_url.startswith('https://')):
                    try:
                        browser_options['proxy'] = {'server': proxy_url}
                    except Exception as e:
                        logger.warning(f"Failed to parse proxy URL {proxy_url}: {e}")
                elif proxy_url:
                    logger.warning(f"Skipping unsupported proxy {proxy_url} - Playwright supports only HTTP/HTTPS")
                
                browser = await p.chromium.launch(**browser_options)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                
                # Устанавливаем cookies/tokens
                if session_token:
                    await context.add_cookies([{
                        'name': '__Secure-next-auth.session-token',
                        'value': session_token,
                        'domain': '.kick.com',
                        'path': '/',
                        'secure': True,
                        'httpOnly': True
                    }])
                
                # Устанавливаем дополнительные заголовки
                headers = {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                if token:
                    headers['Authorization'] = f'Bearer {token}'
                
                await page.set_extra_http_headers(headers)
                
                # Переходим на страницу канала
                try:
                    await page.goto(f'https://kick.com/{channel}', timeout=self.timeout, wait_until='networkidle')
                    
                    # Ждем загрузки страницы и чата
                    await page.wait_for_timeout(3000)
                    
                    # Пробуем различные селекторы для поля ввода сообщения
                    message_input_selectors = [
                        'textarea[placeholder*="Say something"]',
                        'textarea[placeholder*="chat"]', 
                        'input[placeholder*="message"]',
                        'input[placeholder*="Say something"]',
                        '[data-testid="message-input"]',
                        '.chat-input textarea',
                        '.message-input',
                        'textarea[name="message"]',
                        'input[name="message"]',
                        '.chat-send-message textarea',
                        '.chat-send-message input'
                    ]
                    
                    message_input = None
                    for selector in message_input_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                            message_input = page.locator(selector).first
                            if await message_input.is_visible():
                                break
                        except:
                            continue
                    
                    if not message_input:
                        logger.error(f"Could not find message input field on {channel}")
                        await browser.close()
                        return False
                    
                    # Проверяем, что поле доступно для ввода
                    if not await message_input.is_enabled():
                        logger.error(f"Message input field is disabled on {channel}")
                        await browser.close()
                        return False
                    
                    # Очищаем поле и вводим сообщение
                    await message_input.click()
                    await message_input.fill('')
                    await page.wait_for_timeout(500)
                    await message_input.type(message, delay=50)
                    await page.wait_for_timeout(1000)
                    
                    # Отправляем сообщение (Enter или кнопка)
                    await message_input.press('Enter')
                    
                    # Ждем отправки сообщения
                    await page.wait_for_timeout(2000)
                    
                    await browser.close()
                    return True
                    
                except PlaywrightTimeoutError:
                    logger.warning(f"Timeout while sending message to {channel}")
                    await browser.close()
                    return False
                except Exception as e:
                    logger.error(f"Error during message sending to {channel}: {e}")
                    await browser.close()
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending message to {channel}: {e}")
            return False

    async def send_message_phoenix_ws(self, channel: str, message: str, storage_state_path: Optional[str] = None, proxy_url: Optional[str] = None) -> bool:
        """
        Отправка сообщения в чат Kick через Phoenix WebSocket (Playwright).
        Args:
            channel: Название канала
            message: Текст сообщения
            storage_state_path: Путь к storageState для авторизации
            proxy_url: URL прокси (только HTTP/HTTPS)
        Returns:
            bool: True если сообщение отправлено, False если нет
        """
        import json
        try:
            async with async_playwright() as p:
                browser_options = {
                    'headless': self.headless,
                    'args': [
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor',
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-extensions'
                    ]
                }
                if proxy_url and (proxy_url.startswith('http://') or proxy_url.startswith('https://')):
                    try:
                        browser_options['proxy'] = {'server': proxy_url}
                    except Exception as e:
                        logger.warning(f"Failed to parse proxy URL {proxy_url}: {e}")
                elif proxy_url:
                    logger.warning(f"Skipping unsupported proxy {proxy_url} - Playwright supports only HTTP/HTTPS")

                browser = await p.chromium.launch(**browser_options)
                context_args = {
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'viewport': {'width': 1920, 'height': 1080}
                }
                if storage_state_path:
                    context_args['storage_state'] = storage_state_path
                context = await browser.new_context(**context_args)
                page = await context.new_page()
                await page.goto(f'https://kick.com/{channel}', timeout=self.timeout, wait_until='networkidle')
                # Ждём ws-соединения
                try:
                    ws_event = await page.wait_for_event("websocket", lambda ws: "socket/websocket" in ws.url, timeout=10000)
                    ws = ws_event.value
                except Exception as e:
                    logger.error(f"WebSocket connection not found: {e}")
                    await browser.close()
                    return False
                # Получаем channel_id
                try:
                    channel_id = await page.get_attribute('div[data-channel-id]', 'data-channel-id')
                    if not channel_id:
                        logger.error("channel_id not found on page")
                        await browser.close()
                        return False
                except Exception as e:
                    logger.error(f"Failed to get channel_id: {e}")
                    await browser.close()
                    return False
                # phx_join
                join = {
                    "topic": f"chat:lobby:{channel_id}",
                    "event": "phx_join",
                    "payload": {},
                    "ref": "1"
                }
                await ws.send(json.dumps(join))
                # message:new
                msg = {
                    "topic": f"chat:lobby:{channel_id}",
                    "event": "message:new",
                    "payload": {"body": message},
                    "ref": "2"
                }
                await ws.send(json.dumps(msg))
                logger.info(f"Sent message via Phoenix WS: {message}")
                await browser.close()
                return True
        except Exception as e:
            logger.error(f"Error sending message via Phoenix WS: {e}")
            return False


# Singleton instance
_playwright_client = None

def get_playwright_client() -> KickPlaywrightClient:
    """Получить singleton instance клиента Playwright"""
    global _playwright_client
    if _playwright_client is None:
        _playwright_client = KickPlaywrightClient()
    return _playwright_client


async def validate_kick_account_playwright(token: Optional[str] = None, session_token: Optional[str] = None, proxy_url: Optional[str] = None) -> bool:
    """
    Валидация аккаунта Kick через Playwright
    
    Args:
        token: Bearer token аккаунта
        session_token: Session token из cookies
        proxy_url: URL прокси
        
    Returns:
        bool: True если аккаунт валидный, False если нет
    """
    client = get_playwright_client()
    return await client.validate_account(token, session_token, proxy_url)


async def send_kick_message_playwright(channel: str, message: str, token: Optional[str] = None, session_token: Optional[str] = None, proxy_url: Optional[str] = None) -> bool:
    """
    Отправка сообщения в чат Kick через Playwright
    
    Args:
        channel: Название канала
        message: Текст сообщения
        token: Bearer token аккаунта
        session_token: Session token из cookies
        proxy_url: URL прокси
        
    Returns:
        bool: True если сообщение отправлено, False если нет
    """
    client = get_playwright_client()
    return await client.send_message(channel, message, token, session_token, proxy_url) 


async def send_kick_message_phoenix_ws(channel: str, message: str, storage_state_path: Optional[str] = None, proxy_url: Optional[str] = None) -> bool:
    """
    Отправка сообщения в чат Kick через Phoenix WebSocket (Playwright).
    Args:
        channel: Название канала
        message: Текст сообщения
        storage_state_path: Путь к storageState для авторизации
        proxy_url: URL прокси
    Returns:
        bool: True если сообщение отправлено, False если нет
    """
    client = get_playwright_client()
    return await client.send_message_phoenix_ws(channel, message, storage_state_path, proxy_url) 


async def playwright_login_and_save_storage_state(login: str, password: str, storage_state_path: str, proxy_url: str = None) -> bool:
    """
    Логинит в Kick через playwright и сохраняет storage_state в файл.
    Args:
        login: Логин Kick
        password: Пароль Kick
        storage_state_path: Куда сохранить storage_state (json)
        proxy_url: Прокси (если нужен)
    Returns:
        bool: True если успешно, False если нет
    """
    try:
        async with async_playwright() as p:
            browser_options = {
                'headless': True,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-extensions'
                ]
            }
            if proxy_url:
                if proxy_url.startswith('http://') or proxy_url.startswith('https://'):
                    browser_options['proxy'] = {'server': proxy_url}
            browser = await p.chromium.launch(**browser_options)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto('https://kick.com/', timeout=30000)
            # Клик по кнопке логина
            await page.click('text=Log In')
            await page.wait_for_selector('input[name="email"]', timeout=10000)
            await page.fill('input[name="email"]', login)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            # Ждём успешного входа (например, появление user-menu)
            await page.wait_for_selector('[data-testid="user-menu"], .user-menu, .avatar', timeout=15000)
            # Сохраняем storage_state
            os.makedirs(os.path.dirname(storage_state_path), exist_ok=True)
            await context.storage_state(path=storage_state_path)
            await browser.close()
            return True
    except Exception as e:
        import traceback
        print(f"[playwright_login_and_save_storage_state] ERROR: {e}")
        traceback.print_exc()
        return False 