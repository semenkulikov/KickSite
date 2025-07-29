#!/usr/bin/env python3
"""
Сервис для автоматической отправки сообщений к активным стримерам
"""

import asyncio
import threading
import logging
import os
import time
from datetime import datetime, timedelta
from django.utils import timezone
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from KickApp.models import StreamerStatus, StreamerMessage, KickAccount, HydraBotSettings
from KickApp.supabase_sync import SupabaseSyncService, run_sync_async
from KickApp.process_message_manager import ProcessMessageManagerFactory, MessageStatus
from StatsApp.models import Shift, MessageLog, ShiftLog

# Настраиваем логирование
def setup_logging():
    """Настраивает логирование для файлов"""
    # Создаем папку для логов если не существует
    logs_dir = 'logs'
    os.makedirs(logs_dir, exist_ok=True)
    
    # Создаем форматтер
    formatter = logging.Formatter(
        '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
    )
    
    # Консольный handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Handler для auto_messaging.log
    auto_handler = logging.FileHandler(f'{logs_dir}/auto_messaging.log')
    auto_handler.setFormatter(formatter)
    auto_handler.setLevel(logging.INFO)
    
    # Handler для shifts.log
    shifts_handler = logging.FileHandler(f'{logs_dir}/shifts.log')
    shifts_handler.setFormatter(formatter)
    shifts_handler.setLevel(logging.INFO)
    
    # Настраиваем логгеры
    auto_logger = logging.getLogger('KickApp.auto_message_sender')
    auto_logger.addHandler(console_handler)  # Добавляем консольный handler
    auto_logger.addHandler(auto_handler)
    auto_logger.setLevel(logging.INFO)
    
    supabase_logger = logging.getLogger('KickApp.supabase_sync')
    supabase_logger.addHandler(console_handler)  # Добавляем консольный handler
    supabase_logger.addHandler(auto_handler)
    supabase_logger.setLevel(logging.INFO)
    
    process_logger = logging.getLogger('KickApp.process_message_manager')
    process_logger.addHandler(console_handler)  # Добавляем консольный handler
    process_logger.addHandler(auto_handler)
    process_logger.setLevel(logging.INFO)
    
    stats_logger = logging.getLogger('StatsApp')
    stats_logger.addHandler(console_handler)  # Добавляем консольный handler
    stats_logger.addHandler(shifts_handler)
    stats_logger.setLevel(logging.INFO)

# Инициализируем логирование
setup_logging()

logger = logging.getLogger('KickApp.auto_message_sender')

User = get_user_model()

class AutoMessageSender:
    """
    Асинхронный отправитель автоматических сообщений
    Работает в отдельном потоке и не блокирует основной сайт
    """
    
    def __init__(self):
        """Инициализация автоматической рассылки"""
        self.is_running = False
        self.settings = HydraBotSettings.get_settings()
        self.current_cycle = 0
        self.managers = {}  # Менеджеры для пользователей
        self._last_sync_time = None
        self.manager_factory = ProcessMessageManagerFactory()  # Фабрика менеджеров
    
    def start(self):
        """Запускает автоматическую отправку сообщений в отдельном потоке"""
        if self.is_running:
            print("⚠️ Автоматическая отправка уже запущена")
            logger.warning("Автоматическая отправка уже запущена")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()
        print("🚀 Запуск автоматической отправки сообщений в фоновом режиме...")
        logger.info("🚀 Запуск автоматической отправки сообщений в фоновом режиме...")
        print("✅ Автоматическая отправка сообщений запущена в фоновом режиме")
        logger.info("✅ Автоматическая отправка сообщений запущена в фоновом режиме")
    
    def stop(self):
        """Останавливает автоматическую отправку сообщений"""
        if not self.is_running:
            return
        
        print("🛑 Останавливаем автоматическую отправку сообщений...")
        logger.info("🛑 Останавливаем автоматическую отправку сообщений...")
        
        self.is_running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        print("✅ Автоматическая отправка сообщений остановлена")
        logger.info("✅ Автоматическая отправка сообщений остановлена")
    
    def _run_async_loop(self):
        """Запускает асинхронный цикл в отдельном потоке"""
        try:
            # Создаем новый event loop для этого потока
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            # Запускаем основной цикл
            self._loop.run_until_complete(self._main_loop())
        except Exception as e:
            logger.error(f"Ошибка в асинхронном цикле: {e}")
        finally:
            if self._loop and not self._loop.is_closed():
                self._loop.close()
    
    async def _main_loop(self):
        """Основной асинхронный цикл"""
        print("🤖 Автоматическая отправка сообщений запущена")
        logger.info("🤖 Автоматическая отправка сообщений запущена")
        
        # Запоминаем предыдущее состояние для отслеживания изменений
        previous_enabled_state = None
        
        while self.is_running:
            try:
                # Обновляем настройки из базы данных
                await sync_to_async(self.settings.refresh_from_db)()
                
                # Проверяем изменение состояния
                current_enabled_state = self.settings.is_enabled
                if previous_enabled_state is not None and previous_enabled_state != current_enabled_state:
                    if current_enabled_state:
                        logger.info("🔄 Бот включен, перезапускаем автоматическую рассылку...")
                        print("🔄 Бот включен, перезапускаем автоматическую рассылку...")
                    else:
                        logger.info("🛑 Бот отключен, останавливаем автоматическую рассылку...")
                        print("🛑 Бот отключен, останавливаем автоматическую рассылку...")
                
                previous_enabled_state = current_enabled_state
                
                if not self.settings.is_enabled:
                    print("⏸️ Автоматическая рассылка отключена, останавливаем сервис...")
                    logger.info("⏸️ Автоматическая рассылка отключена, останавливаем сервис...")
                    # Останавливаем сервис полностью
                    self.is_running = False
                    break
                
                # Логируем текущие настройки для отладки
                logger.info(f"🔄 Настройки Гидры: enabled={self.settings.is_enabled}, cycle_interval={self.settings.cycle_interval}, message_interval={self.settings.message_interval}")
                
                print("🔄 Начинаем цикл автоматической рассылки...")
                self.current_cycle += 1
                
                # Синхронизируем данные
                await self._sync_data()
                
                # Отправляем сообщения
                await self._send_messages_to_active_streamers()
                
                # Интервал между циклами (по умолчанию 3 секунды)
                cycle_interval = getattr(self.settings, 'cycle_interval', 3)  # 3 секунды
                print(f"✅ Цикл {self.current_cycle} завершен, следующий через {cycle_interval} сек")
                
                # Ждем интервал между циклами
                await asyncio.sleep(cycle_interval)
                
            except Exception as e:
                print(f"❌ Ошибка в основном цикле: {e}")
                logger.error(f"Ошибка в основном цикле: {e}")
                await asyncio.sleep(30)  # Ждем 30 секунд перед повтором
        
        # Логируем завершение работы
        print("🛑 Автоматическая рассылка остановлена")
        logger.info("🛑 Автоматическая рассылка остановлена")
    
    async def _sync_data(self):
        """Синхронизирует данные с Supabase"""
        try:
            # Проверяем, включен ли бот
            await sync_to_async(self.settings.refresh_from_db)()
            if not self.settings.is_enabled:
                logger.info("🛑 Автоматическая рассылка отключена, пропускаем синхронизацию")
                return
            
            # Проверяем интервал синхронизации
            current_time = timezone.now()
            if hasattr(self, '_last_sync_time') and self._last_sync_time:
                time_since_last_sync = (current_time - self._last_sync_time).total_seconds()
                if time_since_last_sync < self.settings.sync_interval:
                    return
            
            logger.info("🔄 Начинаем синхронизацию данных...")
            
            # Синхронизируем данные с таймаутом
            try:
                await asyncio.wait_for(
                    run_sync_async(),
                    timeout=60.0  # 60 секунд таймаут для синхронизации
                )
                self._last_sync_time = current_time
                logger.info("✅ Синхронизация завершена, следующая через {} сек".format(self.settings.sync_interval))
                
            except asyncio.TimeoutError:
                logger.error("Таймаут синхронизации данных")
            except Exception as e:
                logger.error(f"Ошибка синхронизации данных: {e}")
                
        except Exception as e:
            logger.error(f"Ошибка в методе синхронизации: {e}")
    
    async def _send_messages_for_streamer(self, streamer, messages, user_accounts):
        """Отправляет сообщения для конкретного стримера"""
        try:
            # Проверяем, включен ли бот
            await sync_to_async(self.settings.refresh_from_db)()
            if not self.settings.is_enabled:
                logger.info(f"🛑 Автоматическая рассылка отключена, пропускаем отправку для {streamer.vid}")
                return
            
            if not messages or not user_accounts:
                return
            
            # Получаем назначенного пользователя
            assigned_user = await sync_to_async(lambda: streamer.assigned_user)()
            if not assigned_user:
                logger.warning(f"Нет назначенного пользователя для стримера {streamer.vid}")
                return
            
            # Создаем одну смену для всех сообщений стримера
            shift = await sync_to_async(Shift.objects.create)(
                user=assigned_user,
                start_time=timezone.now(),
                is_active=True
            )
            
            # Логируем начало смены
            try:
                await sync_to_async(ShiftLog.objects.create)(
                    shift=shift,
                    action_type='shift_start',
                    description=f'Начало автоматической смены для стримера {streamer.vid}',
                    details={
                        'streamer': streamer.vid,
                        'messages_count': len(messages),
                        'accounts_count': len(user_accounts),
                        'cycle': self.current_cycle
                    }
                )
            except Exception as e:
                logger.error(f"Ошибка логирования начала смены: {e}")
            
            sent_count = 0
            failed_count = 0
            
            # Отправляем сообщения с ограничением скорости
            for i, message in enumerate(messages):
                # Проверяем, включен ли бот перед каждым сообщением
                await sync_to_async(self.settings.refresh_from_db)()
                if not self.settings.is_enabled:
                    logger.info(f"🛑 Автоматическая рассылка отключена, прерываем отправку для {streamer.vid}")
                    return
                
                if not message.is_active:
                    continue
                
                # Выбираем аккаунт по кругу (каждое сообщение - отдельный аккаунт)
                account = user_accounts[i % len(user_accounts)]
                
                # Отправляем сообщение с таймаутом
                success = await self._send_message_via_manager(
                    await self._get_streamer_manager(assigned_user),
                    account,
                    streamer.vid,
                    message.message,
                    assigned_user
                )
                
                # Логируем в смену ВСЕ сообщения с ответом от Kick
                await self._log_auto_message_to_shift(shift, streamer.vid, account.login, message.message)
                
                if success:
                    sent_count += 1
                    # Логируем успешную отправку
                    try:
                        await sync_to_async(ShiftLog.objects.create)(
                            shift=shift,
                            action_type='message_sent',
                            description=f'Сообщение отправлено в {streamer.vid}',
                            details={
                                'channel': streamer.vid,
                                'account': account.login,
                                'message': message.message[:100],
                                'status': 'success'
                            }
                        )
                    except Exception as e:
                        logger.error(f"Ошибка логирования успешной отправки: {e}")
                else:
                    failed_count += 1
                    # Логируем неудачную отправку
                    try:
                        await sync_to_async(ShiftLog.objects.create)(
                            shift=shift,
                            action_type='message_error',
                            description=f'Ошибка отправки в {streamer.vid}',
                            details={
                                'channel': streamer.vid,
                                'account': account.login,
                                'message': message.message[:100],
                                'status': 'failed'
                            }
                        )
                    except Exception as e:
                        logger.error(f"Ошибка логирования неудачной отправки: {e}")
                
                # Небольшая пауза между сообщениями чтобы не перегружать
                await asyncio.sleep(0.5)  # Увеличиваем паузу до 0.5 секунд
            
            # Завершаем смену
            if sent_count > 0 or failed_count > 0:
                # Логируем завершение смены
                try:
                    await sync_to_async(ShiftLog.objects.create)(
                        shift=shift,
                        action_type='shift_end',
                        description=f'Завершение автоматической смены для стримера {streamer.vid}',
                        details={
                            'streamer': streamer.vid,
                            'sent_count': sent_count,
                            'failed_count': failed_count,
                            'cycle': self.current_cycle
                        }
                    )
                except Exception as e:
                    logger.error(f"Ошибка логирования завершения смены: {e}")
                
                await sync_to_async(shift.finish)()
                logger.info(f"📤 Отправлено {sent_count} сообщений для {streamer.vid} (неудачно: {failed_count})")
            else:
                # Если не было попыток отправки, удаляем пустую смену
                await sync_to_async(shift.delete)()
                logger.info(f"Пропущена отправка для {streamer.vid} - нет активных сообщений")
                
        except Exception as e:
            logger.error(f"Ошибка отправки сообщений для {streamer.vid}: {e}")
    
    async def _send_messages_to_active_streamers(self):
        """Отправляет сообщения к активным стримерам"""
        try:
            # Проверяем, включен ли бот
            await sync_to_async(self.settings.refresh_from_db)()
            if not self.settings.is_enabled:
                logger.info("🛑 Автоматическая рассылка отключена, пропускаем отправку сообщений")
                return
            
            # Получаем активных стримеров с назначенными пользователями
            streamers_with_users = await sync_to_async(list)(StreamerStatus.objects.filter(
                status='active',
                assigned_user__isnull=False
            ).select_related('assigned_user'))
            
            if not streamers_with_users:
                logger.info("Нет активных стримеров с назначенными пользователями")
                return
            
            # Создаем задачи для каждого стримера
            tasks = []
            for streamer in streamers_with_users:
                # Получаем сообщения и аккаунты для каждого стримера
                messages = await sync_to_async(list)(StreamerMessage.objects.filter(
                    streamer=streamer,
                    is_active=True
                ))
                
                # Получаем аккаунты назначенного пользователя
                assigned_user = await sync_to_async(lambda: streamer.assigned_user)()
                user_accounts = await sync_to_async(list)(KickAccount.objects.filter(
                    assigned_users=assigned_user,
                    status='active'
                ))
                
                if not user_accounts:
                    logger.warning(f"Нет активных аккаунтов у пользователя {assigned_user.username} для стримера {streamer.vid}")
                    continue
                
                task = self._send_messages_for_streamer(streamer, messages, user_accounts)
                tasks.append(task)
            
            # Выполняем все задачи параллельно
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщений к активным стримерам: {e}")
    
    async def _get_streamer_manager(self, user):
        """Получает менеджер для пользователя"""
        try:
            user_id = await sync_to_async(lambda: user.id)()
            if user_id not in self.managers:
                # Используем фабрику для создания менеджера
                self.managers[user_id] = self.manager_factory.get_manager(user_id, max_processes=50)
                logger.info(f"Created new ProcessMessageManager for user {user_id}")
            return self.managers[user_id]
        except Exception as e:
            logger.error(f"Ошибка получения менеджера для пользователя: {e}")
            return None
    
    async def _send_message_via_manager(self, manager, account, channel, message, user):
        """Отправляет сообщение через менеджер"""
        try:
            if not manager:
                logger.error("Менеджер не найден для отправки сообщения")
                return False
                
            account_login = await sync_to_async(lambda: account.login)()
            account_token = await sync_to_async(lambda: account.token)()
            account_session_token = await sync_to_async(lambda: account.session_token)()
            proxy_url = await sync_to_async(lambda: account.proxy_url)() if hasattr(account, 'proxy_url') else None
            
            # Отладочная информация
            logger.info(f"Отправка сообщения: account={account_login}, token_length={len(account_token) if account_token else 0}, token_preview={account_token[:20] if account_token else 'None'}")
            
            # Генерируем уникальный request_id
            request_id = f"auto_{int(time.time() * 1000)}"
            
            # Отправляем сообщение с таймаутом
            try:
                request = await asyncio.wait_for(
                    manager.send_message_async(
                        request_id=request_id,
                        channel=channel,
                        account=account_login,
                        message=message,
                        token=account_token,  # Используем токен аккаунта
                        session_token=account_session_token,
                        proxy_url=proxy_url
                    ),
                    timeout=30.0  # 30 секунд таймаут
                )
                
                # Ждем завершения запроса
                for _ in range(300):  # Ждем максимум 30 секунд
                    if request.status in [MessageStatus.SUCCESS, MessageStatus.FAILED, MessageStatus.CANCELLED]:
                        break
                    await asyncio.sleep(0.1)
                
                # Считаем успешным любое сообщение с ответом от Kick (не только SUCCESS)
                # Главное - что пришел ответ, а не ошибка сети/таймаут
                if request.status == MessageStatus.SUCCESS:
                    return True
                elif request.status == MessageStatus.FAILED and request.error:
                    # Проверяем, что это ошибка от Kick, а не сеть/таймаут
                    error = request.error.lower()
                    if any(keyword in error for keyword in ['banned', 'followers', 'rate limit', 'security', 'kick.com']):
                        # Это ответ от Kick - считаем успешным
                        return True
                    else:
                        # Это ошибка сети/таймаут - считаем неуспешным
                        return False
                else:
                    return False
                
            except asyncio.TimeoutError:
                logger.error(f"Таймаут отправки сообщения для {account_login} в {channel}")
                return False
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения через менеджер: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Ошибка подготовки данных для отправки: {e}")
            return False
    
    async def _log_auto_message_to_shift(self, shift, channel, account, message):
        """Логирует автоматическое сообщение в существующую смену"""
        try:
            if not shift:
                return
                
            # Создаем запись в MessageLog с обработкой ошибок
            try:
                await sync_to_async(MessageLog.objects.create)(
                    shift=shift,
                    channel=channel,
                    account=account,
                    message_type='a',  # auto
                    message=message
                )
                
                # Обновляем статистику смены
                await sync_to_async(shift.add_message)('a')
                
            except Exception as e:
                if "database is locked" in str(e):
                    logger.warning("База данных заблокирована, пропускаем создание MessageLog")
                else:
                    logger.error(f"Ошибка создания MessageLog: {e}")
                return
            
            # Логируем действие в ShiftLog с обработкой ошибок
            try:
                await sync_to_async(ShiftLog.objects.create)(
                    shift=shift,
                    action_type='message_sent',
                    description=f'Автоматическое сообщение отправлено в {channel} (цикл {self.current_cycle})',
                    details={
                        'channel': channel,
                        'account': account,
                        'message': message[:100],  # Первые 100 символов
                        'type': 'auto',
                        'cycle': self.current_cycle
                    }
                )
            except Exception as e:
                if "database is locked" in str(e):
                    logger.warning("База данных заблокирована, пропускаем создание ShiftLog")
                else:
                    logger.error(f"Ошибка создания ShiftLog: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка логирования автоматического сообщения: {e}")
    
    async def _log_auto_message(self, user, channel, account, message):
        """Логирует автоматическое сообщение в систему смен (устаревший метод)"""
        # Этот метод больше не используется, так как смена создается заранее
        pass
    
    async def _should_send_message(self, streamer):
        """Проверяет, можно ли отправлять сообщение для стримера"""
        try:
            # Получаем время последней отправки
            last_sent_time = await sync_to_async(lambda: getattr(streamer, 'last_sent_time', None))()
            
            if not last_sent_time:
                return True
            
            # Проверяем интервал
            current_time = timezone.now()
            time_since_last = (current_time - last_sent_time).total_seconds()
            
            # Используем интервал из настроек или по умолчанию 3 секунды
            min_interval = getattr(self.settings, 'message_interval', 3.0)
            
            return time_since_last >= min_interval
            
        except Exception as e:
            logger.error(f"Ошибка проверки интервала отправки: {e}")
            return False
    
    async def _update_last_sent_time(self, streamer):
        """Обновляет время последней отправки для стримера"""
        try:
            await sync_to_async(setattr)(streamer, 'last_sent_time', timezone.now())
            await sync_to_async(streamer.save)()
        except Exception as e:
            if "database is locked" in str(e):
                logger.warning("База данных заблокирована, пропускаем обновление времени отправки")
            else:
                logger.error(f"Ошибка обновления времени отправки: {e}")
    
    def cleanup(self):
        """Очищает ресурсы"""
        try:
            # Останавливаем все менеджеры
            for manager in self.managers.values():
                if hasattr(manager, 'cleanup'):
                    manager.cleanup()
            
            # Очищаем менеджеры
            self.managers.clear()
            
            # Очищаем Supabase сессию
            if self.supabase_sync:
                self.supabase_sync.cleanup()
                
        except Exception as e:
            logger.error(f"Ошибка очистки ресурсов: {e}")


# Глобальный экземпляр отправителя
_auto_message_sender = None

def get_auto_message_sender():
    """Получает глобальный экземпляр отправителя"""
    global _auto_message_sender
    if _auto_message_sender is None:
        _auto_message_sender = AutoMessageSender()
    return _auto_message_sender

def start_auto_messaging():
    """Запускает автоматическую отправку сообщений"""
    sender = get_auto_message_sender()
    sender.start()

def stop_auto_messaging():
    """Останавливает автоматическую отправку сообщений"""
    sender = get_auto_message_sender()
    sender.stop()

def restart_auto_messaging():
    """Перезапускает автоматическую отправку сообщений"""
    try:
        sender = get_auto_message_sender()
        
        # Проверяем текущее состояние
        if sender.is_running:
            print("🔄 Останавливаем текущий сервис...")
            logger.info("🔄 Останавливаем текущий сервис...")
            sender.stop()
            
            # Ждем полной остановки
            import time
            time.sleep(3)
        
        # Проверяем актуальные настройки из базы данных
        sender.settings.refresh_from_db()
        
        if sender.settings.is_enabled:
            print("🚀 Перезапускаем автоматическую рассылку...")
            logger.info("🚀 Перезапускаем автоматическую рассылку...")
            sender.start()
        else:
            print("⏸️ Бот отключен, перезапуск не требуется")
            logger.info("⏸️ Бот отключен, перезапуск не требуется")
            
    except Exception as e:
        print(f"❌ Ошибка перезапуска: {e}")
        logger.error(f"Ошибка перезапуска: {e}")

def get_auto_messaging_status():
    """Получает статус автоматической отправки сообщений"""
    sender = get_auto_message_sender()
    return {
        'running': sender.is_running,
        'cycle': sender.current_cycle,
        'settings': {
            'is_enabled': sender.settings.is_enabled,
            'message_interval': sender.settings.message_interval,
            'sync_interval': sender.settings.sync_interval,
            'max_concurrent_sends': sender.settings.max_concurrent_sends,
            'min_message_interval': sender.settings.min_message_interval
        }
    } 