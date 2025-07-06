import asyncio
import logging
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class KickPlaywrightClient:
    """Клиент для работы с Kick через Playwright"""
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
    
    async def validate_account(self, token: Optional[str] = None, session_token: Optional[str] = None, proxy_url: Optional[str] = None) -> bool:
        """
        Валидация аккаунта Kick через Playwright
        
        Args:
            token: Bearer token аккаунта
            session_token: Session token из cookies
            proxy_url: URL прокси (socks5://user:pass@host:port)
            
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
                
                if proxy_url:
                    try:
                        # Парсим прокси URL
                        if proxy_url.startswith('socks5://'):
                            proxy_parts = proxy_url.replace('socks5://', '').split('@')
                            if len(proxy_parts) == 2:
                                auth_part, server_part = proxy_parts
                                username, password = auth_part.split(':')
                                server, port = server_part.split(':')
                                browser_options['proxy'] = {
                                    'server': f'socks5://{server}:{port}',
                                    'username': username,
                                    'password': password
                                }
                            else:
                                server, port = proxy_parts[0].split(':')
                                browser_options['proxy'] = {
                                    'server': f'socks5://{server}:{port}'
                                }
                        elif proxy_url.startswith('http://') or proxy_url.startswith('https://'):
                            browser_options['proxy'] = {'server': proxy_url}
                    except Exception as e:
                        logger.warning(f"Failed to parse proxy URL {proxy_url}: {e}")
                
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
                
                if token:
                    # Добавляем Authorization header через CDP
                    await page.set_extra_http_headers({
                        'Authorization': f'Bearer {token}'
                    })
                
                # Переходим на страницу профиля
                try:
                    await page.goto('https://kick.com/settings/profile', timeout=self.timeout)
                    await page.wait_for_load_state('networkidle', timeout=self.timeout)
                    
                    # Проверяем, что мы на странице настроек (значит залогинены)
                    # Ищем элементы, которые есть только у залогиненных пользователей
                    profile_elements = await page.locator('input[name="display_name"], input[name="username"], .profile-form, [data-testid="profile-form"]').count()
                    
                    if profile_elements > 0:
                        await browser.close()
                        return True
                    
                    # Альтернативная проверка - проверяем, что нас не редиректнуло на логин
                    current_url = page.url
                    if 'login' in current_url.lower() or 'auth' in current_url.lower():
                        await browser.close()
                        return False
                    
                    # Проверяем наличие элементов интерфейса залогиненного пользователя
                    user_menu = await page.locator('[data-testid="user-menu"], .user-menu, .avatar-dropdown').count()
                    if user_menu > 0:
                        await browser.close()
                        return True
                    
                    await browser.close()
                    return False
                    
                except PlaywrightTimeoutError:
                    logger.warning("Timeout while validating account")
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
            proxy_url: URL прокси
            
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
                        '--disable-dev-shm-usage'
                    ]
                }
                
                if proxy_url:
                    try:
                        # Парсим прокси URL
                        if proxy_url.startswith('socks5://'):
                            proxy_parts = proxy_url.replace('socks5://', '').split('@')
                            if len(proxy_parts) == 2:
                                auth_part, server_part = proxy_parts
                                username, password = auth_part.split(':')
                                server, port = server_part.split(':')
                                browser_options['proxy'] = {
                                    'server': f'socks5://{server}:{port}',
                                    'username': username,
                                    'password': password
                                }
                            else:
                                server, port = proxy_parts[0].split(':')
                                browser_options['proxy'] = {
                                    'server': f'socks5://{server}:{port}'
                                }
                        elif proxy_url.startswith('http://') or proxy_url.startswith('https://'):
                            browser_options['proxy'] = {'server': proxy_url}
                    except Exception as e:
                        logger.warning(f"Failed to parse proxy URL {proxy_url}: {e}")
                
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
                
                if token:
                    # Добавляем Authorization header через CDP
                    await page.set_extra_http_headers({
                        'Authorization': f'Bearer {token}'
                    })
                
                # Переходим на страницу канала
                try:
                    await page.goto(f'https://kick.com/{channel}', timeout=self.timeout)
                    await page.wait_for_load_state('networkidle', timeout=self.timeout)
                    
                    # Ждем загрузки чата
                    await page.wait_for_selector('textarea[placeholder*="chat"], input[placeholder*="message"], [data-testid="message-input"], .chat-input textarea, .message-input', timeout=self.timeout)
                    
                    # Находим поле ввода сообщения
                    message_input = page.locator('textarea[placeholder*="chat"], input[placeholder*="message"], [data-testid="message-input"], .chat-input textarea, .message-input').first
                    
                    # Вводим сообщение
                    await message_input.fill(message)
                    
                    # Отправляем сообщение (Enter или кнопка)
                    await message_input.press('Enter')
                    
                    # Ждем немного, чтобы сообщение отправилось
                    await page.wait_for_timeout(2000)
                    
                    await browser.close()
                    return True
                    
                except PlaywrightTimeoutError:
                    logger.warning(f"Timeout while sending message to {channel}")
                    await browser.close()
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending message to {channel}: {e}")
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
        bool: True если аккаунт валиден, False если нет
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