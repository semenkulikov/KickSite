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
            proxy_url: URL прокси (только HTTP/HTTPS)
            
        Returns:
            bool: True если аккаунт валидный, False если нет
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
                
                if token:
                    # Добавляем Authorization header через CDP
                    await page.set_extra_http_headers({
                        'Authorization': f'Bearer {token}'
                    })
                
                # Переходим на главную страницу Kick
                try:
                    await page.goto('https://kick.com', timeout=self.timeout)
                    await page.wait_for_load_state('networkidle', timeout=5000)
                    
                    # Проверяем, залогинены ли мы
                    # Ищем элементы, которые есть только у залогиненных пользователей
                    
                    # 1. Проверяем наличие кнопки "Sign in" или "Login" - если есть, значит не залогинены
                    login_button = await page.locator('a[href*="login"], button:has-text("Sign in"), button:has-text("Login"), a:has-text("Sign in"), a:has-text("Login")').count()
                    if login_button > 0:
                        print(f"DEBUG: Found login button, user not logged in")
                        await browser.close()
                        return False
                    
                    # 2. Проверяем наличие элементов залогиненного пользователя
                    # Аватар пользователя, меню профиля, кнопка "Go Live" и т.д.
                    user_elements = await page.locator('[data-testid="user-menu"], .user-menu, .avatar, .profile-avatar, button:has-text("Go Live"), [data-testid="go-live-button"]').count()
                    if user_elements > 0:
                        print(f"DEBUG: Found user elements ({user_elements}), user is logged in")
                        await browser.close()
                        return True
                    
                    # 3. Проверяем URL - если нас редиректнуло на страницу входа
                    current_url = page.url
                    if 'login' in current_url.lower() or 'auth' in current_url.lower() or 'signin' in current_url.lower():
                        print(f"DEBUG: Redirected to login page: {current_url}")
                        await browser.close()
                        return False
                    
                    # 4. Проверяем наличие любых элементов с текстом пользователя
                    page_content = await page.content()
                    if 'dashboard' in page_content.lower() or 'profile' in page_content.lower():
                        print(f"DEBUG: Found user-related content")
                        await browser.close()
                        return True
                    
                    print(f"DEBUG: No clear indication of login status, assuming not logged in")
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