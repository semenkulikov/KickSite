# Настройка Playwright для валидации аккаунтов Kick

## Проблема
Стандартная валидация аккаунтов Kick через `requests` не работает из-за:
- Cloudflare защиты
- Антибот систем
- Блокировки прямых HTTP запросов

## Решение
Используется Playwright для эмуляции реального браузера.

## Установка

1. Playwright уже добавлен в `requirements.txt`
2. Установите браузеры:
```bash
python -m playwright install chromium
```

## Что изменено

### 1. Новый модуль `KickApp/playwright_utils.py`
- Валидация аккаунтов через headless browser
- Отправка сообщений через реальный браузер
- Поддержка прокси (socks5, http, https)
- Fallback на старые методы если Playwright не работает

### 2. Обновлена модель `KickAccount`
- Метод `check_kick_account_valid()` теперь использует Playwright
- Fallback на requests если Playwright недоступен

### 3. Обновлен `consumers.py`
- Функция `send_kick_message()` использует Playwright
- Добавлена обработка события `KICK_SEND_MESSAGE`
- Fallback на httpx если Playwright не работает

## Как работает

### Валидация аккаунта
1. Открывает браузер с прокси (если есть)
2. Устанавливает cookies/tokens
3. Переходит на страницу профиля Kick
4. Проверяет наличие элементов залогиненного пользователя
5. Возвращает True/False

### Отправка сообщения
1. Открывает браузер с прокси (если есть)
2. Устанавливает cookies/tokens
3. Переходит на страницу канала
4. Находит поле ввода сообщения
5. Вводит и отправляет сообщение

## Настройки

### Прокси
Поддерживаются форматы:
- `socks5://user:pass@host:port`
- `socks5://host:port`
- `http://user:pass@host:port`
- `https://user:pass@host:port`

### Токены
- Bearer токены (без префикса "Bearer")
- Session токены из cookies

## Производительность
- Headless режим для скорости
- Singleton pattern для переиспользования
- Fallback на старые методы при ошибках

## Отладка
Для включения отладки измените в `playwright_utils.py`:
```python
self.headless = False  # Показать браузер
```

## Логи
Все операции логируются в консоль Django для отладки. 