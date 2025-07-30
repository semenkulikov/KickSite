#!/usr/bin/env python3
"""
Сервис для автоматической отправки сообщений к активным стримерам в гидре
"""

import asyncio
import logging
import os
import threading
import time
from datetime import datetime
from typing import List, Optional

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from KickApp.models import KickAccount, KickAccountAssignment, StreamerStatus, StreamerHydraSettings, StreamerMessage, HydraBotSettings
from ServiceApp.models import User
from StatsApp.models import Shift
from KickApp.process_message_manager import ProcessMessageManager, MessageStatus
import json

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
    
    # Handler для auto_messaging.log
    auto_handler = logging.FileHandler(f'{logs_dir}/auto_messaging.log')
    auto_handler.setFormatter(formatter)
    auto_handler.setLevel(logging.INFO)
    
    # Handler для shifts.log
    shifts_handler = logging.FileHandler(f'{logs_dir}/shifts.log')
    shifts_handler.setFormatter(formatter)
    shifts_handler.setLevel(logging.INFO)
    
    # Настраиваем логгеры (только файловые, консольный уже настроен в settings.py)
    auto_logger = logging.getLogger('KickApp.auto_message_sender')
    auto_logger.addHandler(auto_handler)
    auto_logger.setLevel(logging.INFO)
    
    stats_logger = logging.getLogger('StatsApp')
    stats_logger.addHandler(shifts_handler)
    stats_logger.setLevel(logging.INFO)

# Инициализируем логирование
setup_logging()

logger = logging.getLogger('KickApp.auto_message_sender')

class AutoMessageSender:
    """Автоматическая отправка сообщений для стримеров в гидре"""
    
    def __init__(self):
        self.is_running = False
        self.settings = None
        self.current_cycle = 0  # Добавляем счетчик циклов
        self._managers_cache = {}  # Кэш для ProcessMessageManager
        self._managers_lock = threading.Lock()
    
    def start(self):
        """Запускает автоматическую отправку сообщений"""
        print("🔍 AutoMessageSender.start() вызван")
        logger.info("🔍 AutoMessageSender.start() вызван")
        
        if self.is_running:
            print("⚠️ Автоматическая отправка сообщений уже запущена")
            logger.warning("⚠️ Автоматическая отправка сообщений уже запущена")
            return
        
        try:
            print("🔍 Получаем настройки...")
            # Получаем настройки
            self.settings = HydraBotSettings.get_settings()
            print(f"🔍 Настройки получены: {self.settings}")
            
            if not self.settings.is_enabled:
                print("⏸️ Автоматическая отправка сообщений отключена в настройках")
                logger.info("🤖 Автоматическая отправка сообщений отключена в настройках")
                return
            
            print(f"🔍 Настройки Гидры: enabled={self.settings.is_enabled}, cycle_interval={self.settings.cycle_interval}, message_interval={self.settings.message_interval}")
            logger.info(f"🔄 Настройки Гидры: enabled={self.settings.is_enabled}, cycle_interval={self.settings.cycle_interval}, message_interval={self.settings.message_interval}")
            
            print("🔍 Устанавливаем is_running = True")
            self.is_running = True
            
            print("🔍 Создаем поток для асинхронного цикла...")
            # Запускаем асинхронный цикл в отдельном потоке
            self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
            print("🔍 Запускаем поток...")
            self.thread.start()
            print("✅ Поток запущен")
            
        except Exception as e:
            print(f"❌ Ошибка запуска автоматической отправки сообщений: {e}")
            logger.error(f"Ошибка запуска автоматической отправки сообщений: {e}")
            import traceback
            traceback.print_exc()
    
    def stop(self):
        """Останавливает автоматическую отправку сообщений"""
        print("🛑 Останавливаем автоматическую рассылку...")
        logger.info("🛑 Останавливаем автоматическую рассылку...")
        
        # Устанавливаем флаг остановки
        self.is_running = False
        
        # Принудительно останавливаем все процессы в менеджерах
        with self._managers_lock:
            for manager in self._managers_cache.values():
                try:
                    print(f"🛑 Отменяем все процессы в менеджере...")
                    manager.cancel_all()
                except Exception as e:
                    print(f"❌ Ошибка отмены процессов: {e}")
                    logger.error(f"Ошибка отмены процессов: {e}")
            self._managers_cache.clear()
        
        # Принудительно останавливаем event loop если он запущен
        if hasattr(self, '_loop') and self._loop and not self._loop.is_closed():
            try:
                print("🛑 Останавливаем event loop...")
                # Проверяем, что мы не в том же потоке, что и event loop
                if threading.current_thread() != self.thread:
                    self._loop.call_soon_threadsafe(self._loop.stop)
                else:
                    # Если мы в том же потоке, просто останавливаем
                    self._loop.stop()
            except Exception as e:
                print(f"❌ Ошибка остановки event loop: {e}")
                logger.error(f"Ошибка остановки event loop: {e}")
        
        # Ждем завершения потока
        if hasattr(self, 'thread') and self.thread and self.thread.is_alive():
            print("🛑 Ждем завершения потока...")
            try:
                self.thread.join(timeout=15)  # Увеличиваем timeout до 15 секунд
                
                # Если поток не завершился, принудительно завершаем
                if self.thread.is_alive():
                    print("⚠️ Поток не завершился, принудительно останавливаем...")
                    # В Python нет прямого способа убить поток, но можно сбросить флаг
                    self.is_running = False
            except Exception as e:
                print(f"❌ Ошибка ожидания завершения потока: {e}")
                logger.error(f"Ошибка ожидания завершения потока: {e}")
        
        # Финальная проверка и сброс флага
        self.is_running = False
        
        print("✅ Автоматическая рассылка остановлена")
        logger.info("✅ Автоматическая рассылка остановлена")
    
    def _get_manager_for_user(self, user_id):
        """Получает или создает ProcessMessageManager для пользователя"""
        with self._managers_lock:
            if user_id not in self._managers_cache:
                from KickApp.process_message_manager import ProcessMessageManagerFactory
                factory = ProcessMessageManagerFactory()
                self._managers_cache[user_id] = factory.get_manager(user_id, max_processes=50)
                logger.info(f"Created new ProcessMessageManager for user {user_id}")
            return self._managers_cache[user_id]
    
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
        """Основной асинхронный цикл - управляет индивидуальными циклами стримеров"""
        print("🤖 Автоматическая отправка сообщений для гидры запущена")
        logger.info("🤖 Автоматическая отправка сообщений для гидры запущена")
        
        # Запоминаем предыдущее состояние для отслеживания изменений
        previous_enabled_state = None
        
        while self.is_running:
            try:
                # Проверяем флаг остановки в начале цикла
                if not self.is_running:
                    print("🛑 Получен сигнал остановки, завершаем цикл...")
                    break
                
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
                        self.is_running = False
                        break
                
                previous_enabled_state = current_enabled_state
                
                if not self.settings.is_enabled:
                    print("⏸️ Автоматическая рассылка отключена, останавливаем сервис...")
                    logger.info("⏸️ Автоматическая рассылка отключена, останавливаем сервис...")
                    # Останавливаем сервис полностью
                    self.is_running = False
                    break
                
                # Проверяем флаг остановки перед обработкой стримеров
                if not self.is_running:
                    print("🛑 Получен сигнал остановки перед обработкой, завершаем...")
                    break
                
                # Логируем текущие настройки для отладки
                logger.info(f"🔄 Настройки Гидры: enabled={self.settings.is_enabled}, cycle_interval={self.settings.cycle_interval}, message_interval={self.settings.message_interval}")
                
                print("🔄 Начинаем обработку стримеров в гидре...")
                
                # Получаем всех активных стримеров в гидре
                streamers = await sync_to_async(list)(StreamerStatus.objects.filter(
                    is_hydra_enabled=True,
                    assigned_user__isnull=False
                ).select_related('assigned_user'))
                
                if not streamers:
                    logger.info("Нет стримеров включенных в гидру")
                    # Ждем немного перед следующей проверкой
                    await asyncio.sleep(10)
                    continue
                
                logger.info(f"🔍 Найдено {len(streamers)} активных стримеров в гидре")
                
                # Создаем задачи для каждого стримера
                tasks = []
                for streamer in streamers:
                    # Проверяем индивидуальные настройки стримера
                    try:
                        hydra_settings = await sync_to_async(StreamerHydraSettings.objects.get)(streamer=streamer)
                        if not await sync_to_async(lambda: hydra_settings.is_active)():
                            logger.info(f"⏸️ Стример {streamer.vid} отключен в индивидуальных настройках")
                            continue
                        logger.info(f"✅ Стример {streamer.vid} активен, настройки: message_interval={await sync_to_async(lambda: hydra_settings.message_interval)()}, cycle_interval={await sync_to_async(lambda: hydra_settings.cycle_interval)()}")
                    except StreamerHydraSettings.DoesNotExist:
                        logger.info(f"✅ Стример {streamer.vid} активен (использует глобальные настройки)")
                    
                    task = asyncio.create_task(self._run_streamer_cycle(streamer))
                    tasks.append(task)
                
                if tasks:
                    # Ждем завершения всех циклов
                    await asyncio.gather(*tasks, return_exceptions=True)
                    logger.info("✅ Все циклы стримеров завершены")
                else:
                    logger.info("⏸️ Нет активных стримеров для обработки")
                
                # Пауза между циклами (используем глобальные настройки)
                cycle_interval = self.settings.cycle_interval or 5
                logger.info(f"⏱️ Пауза между циклами: {cycle_interval} сек")
                await asyncio.sleep(cycle_interval)
                
            except Exception as e:
                print(f"❌ Ошибка в основном цикле: {e}")
                logger.error(f"Ошибка в основном цикле: {e}")
                
                # Проверяем флаг остановки перед повтором
                if not self.is_running:
                    print("🛑 Получен сигнал остановки при ошибке, завершаем...")
                    break
                    
                await asyncio.sleep(30)  # Ждем 30 секунд перед повтором
        
        # Логируем завершение работы
        print("🛑 Автоматическая рассылка для гидры остановлена")
        logger.info("🛑 Автоматическая рассылка для гидры остановлена")
    
    async def _run_streamer_cycle(self, streamer):
        """Запускает цикл отправки сообщений для одного стримера"""
        try:
            logger.info(f"🔄 Начинаем цикл для стримера {streamer.vid}")
            
            # Получаем индивидуальные настройки стримера
            try:
                hydra_settings = await sync_to_async(StreamerHydraSettings.objects.get)(streamer=streamer)
                logger.info(f"⚙️ Индивидуальные настройки для {streamer.vid}: message_interval={await sync_to_async(lambda: hydra_settings.message_interval)()}, cycle_interval={await sync_to_async(lambda: hydra_settings.cycle_interval)()}")
                
                if not await sync_to_async(lambda: hydra_settings.is_active)():
                    logger.info(f"⏸️ Стример {streamer.vid} отключен в индивидуальных настройках")
                    return
            except StreamerHydraSettings.DoesNotExist:
                # Если нет индивидуальных настроек, проверяем основной статус
                if not await sync_to_async(lambda: streamer.is_hydra_enabled)():
                    logger.info(f"⏸️ Стример {streamer.vid} отключен в основном статусе")
                    return
                # Создаем индивидуальные настройки
                try:
                    hydra_settings = await sync_to_async(StreamerHydraSettings.objects.create)(
                        streamer=streamer,
                        is_active=await sync_to_async(lambda: streamer.is_hydra_enabled)(),
                        message_interval=None,
                        cycle_interval=None
                    )
                    logger.info(f"🔄 Созданы индивидуальные настройки для стримера {streamer.vid}: is_active={await sync_to_async(lambda: streamer.is_hydra_enabled)()}")
                except Exception as e:
                    logger.error(f"❌ Ошибка создания индивидуальных настроек для стримера {streamer.vid}: {e}")
                    return
            
            # Дополнительная проверка основного статуса
            if not await sync_to_async(lambda: streamer.is_hydra_enabled)():
                logger.info(f"⏸️ Стример {streamer.vid} отключен в основном статусе")
                return
            
            # Получаем сообщения для стримера
            messages = await sync_to_async(list)(
                StreamerMessage.objects.filter(
                    streamer=streamer,
                    is_active=True
                )
            )
            
            logger.info(f"📝 Найдено {len(messages)} активных сообщений для стримера {streamer.vid}")
            
            if not messages:
                logger.info(f"⏸️ Нет активных сообщений для стримера {streamer.vid}")
                return
            
            # Получаем аккаунты пользователя
            user_accounts = await sync_to_async(list)(
                KickAccount.objects.filter(
                    assignments__user=streamer.assigned_user,
                    assignments__is_active=True,
                    status='active'
                )
            )
            
            if not user_accounts:
                logger.warning(f"❌ Нет активных аккаунтов для пользователя {streamer.assigned_user.username}")
                return
            
            logger.info(f"👤 Найдено {len(user_accounts)} активных аккаунтов для пользователя {streamer.assigned_user.username}")
            
            # Создаем смену для логирования
            from StatsApp.models import Shift
            shift = await sync_to_async(Shift.objects.create)(
                user=streamer.assigned_user,
                is_active=True
            )
            logger.info(f"📊 Создана смена {shift.id} для пользователя {streamer.assigned_user.username}")
            
            # Логируем начало смены
            await self._log_shift_action(shift, 'shift_start', f'Начата смена для стримера {streamer.vid}', {
                'streamer': streamer.vid,
                'total_messages': len(messages),
                'total_accounts': len(user_accounts),
                'message_interval': await sync_to_async(lambda: hydra_settings.get_message_interval())() or self.settings.message_interval or 1
            })
            
            # Логируем настройки
            await self._log_shift_action(shift, 'settings_change', f'Настройки для стримера {streamer.vid}', {
                'streamer': streamer.vid,
                'message_interval': await sync_to_async(lambda: hydra_settings.get_message_interval())() or self.settings.message_interval or 1,
                'cycle_interval': await sync_to_async(lambda: hydra_settings.get_message_interval())() or self.settings.cycle_interval or 3,
                'is_active': await sync_to_async(lambda: hydra_settings.is_active)()
            })
            
            # Отправляем сообщения с учетом индивидуальных настроек
            sent_count = 0
            failed_count = 0
            
            logger.info(f"🔄 Начинаем отправку {len(messages)} сообщений для стримера {streamer.vid}")
            
            for i, message in enumerate(messages):
                # Проверяем флаг остановки перед каждым сообщением
                if not self.is_running:
                    logger.info(f"🛑 Получен сигнал остановки, прерываем цикл для стримера {streamer.vid}")
                    break
                
                logger.info(f"📝 Обрабатываем сообщение {i+1}/{len(messages)} для стримера {streamer.vid}")
                
                if not await sync_to_async(lambda: message.is_active)():
                    logger.info(f"⏸️ Сообщение {i+1} неактивно, пропускаем")
                    continue
                
                # Выбираем аккаунт по кругу
                account = user_accounts[i % len(user_accounts)]
                logger.info(f"👤 Используем аккаунт {await sync_to_async(lambda: account.login)()} для сообщения {i+1}")
                
                # Отправляем сообщение через простую функцию (как в основном сайте)
                success = await self._send_message_simple(
                    account,
                    streamer.vid,
                    await sync_to_async(lambda: message.message)(),
                    streamer.assigned_user # Pass assigned_user here
                )
                
                # Логируем в смену ВСЕ сообщения
                await self._log_auto_message_to_shift(shift, streamer.vid, await sync_to_async(lambda: account.login)(), await sync_to_async(lambda: message.message)())
                
                if success:
                    sent_count += 1
                    # Обновляем статистику после каждого успешного сообщения
                    await sync_to_async(shift.update_speed)()
                    logger.info(f"📊 Статистика обновлена после сообщения {sent_count} для {streamer.vid}")
                    
                    # Логируем успешную отправку
                    await sync_to_async(shift.add_action)('message_success', f'Сообщение успешно отправлено: {await sync_to_async(lambda: account.login)()} -> {streamer.vid}', {
                        'account': await sync_to_async(lambda: account.login)(),
                        'channel': streamer.vid,
                        'message': await sync_to_async(lambda: message.message)()[:50] + '...' if len(await sync_to_async(lambda: message.message)()) > 50 else await sync_to_async(lambda: message.message)(),
                        'message_number': sent_count
                    })
                else:
                    failed_count += 1
                    logger.warning(f"❌ Сообщение {i+1} не отправлено для {streamer.vid}")
                    
                    # Логируем неудачную отправку
                    await sync_to_async(shift.add_action)('message_failed', f'Сообщение не отправлено: {await sync_to_async(lambda: account.login)()} -> {streamer.vid}', {
                        'account': await sync_to_async(lambda: account.login)(),
                        'channel': streamer.vid,
                        'message': await sync_to_async(lambda: message.message)()[:50] + '...' if len(await sync_to_async(lambda: message.message)()) > 50 else await sync_to_async(lambda: message.message)(),
                        'message_number': i + 1
                    })
                
                # Пауза между сообщениями (используем индивидуальные настройки или глобальные)
                message_interval = await sync_to_async(lambda: hydra_settings.get_message_interval())() or self.settings.message_interval or 1
                logger.info(f"⏱️ Интервал между сообщениями для {streamer.vid}: {message_interval} сек (индивидуальный: {await sync_to_async(lambda: hydra_settings.message_interval)()}, глобальный: {self.settings.message_interval})")
                await asyncio.sleep(message_interval)
            
            logger.info(f"✅ Завершен цикл отправки для {streamer.vid}: отправлено {sent_count}, неудачно {failed_count}")
            
            # Завершаем смену
            if sent_count > 0 or failed_count > 0:
                # Логируем завершение смены
                await self._log_shift_action(shift, 'shift_end', f'Завершена смена для стримера {streamer.vid}', {
                    'streamer': streamer.vid,
                    'sent_count': sent_count,
                    'failed_count': failed_count,
                    'total_messages': len(messages),
                    'message_interval': message_interval
                })
                
                await sync_to_async(shift.finish)()
                logger.info(f"📤 Цикл завершен для {streamer.vid}: отправлено {sent_count} сообщений (неудачно: {failed_count})")
                
                # Отправляем статистику смены
                try:
                    from StatsApp.shift_manager import get_shift_manager
                    shift_manager = get_shift_manager(streamer.assigned_user)
                    stats = await sync_to_async(shift_manager.get_shift_statistics)(shift)
                    
                    # Отправляем через WebSocket всем подключенным клиентам
                    try:
                        from channels.layers import get_channel_layer
                        channel_layer = get_channel_layer()
                        await channel_layer.group_send(
                            f"chat_{streamer.assigned_user.id}",
                            {
                                'type': 'send_stats_update',
                                'event': 'KICK_STATS_UPDATE',
                                'message': stats
                            }
                        )
                        logger.info(f"📊 Статистика отправлена в WebSocket для пользователя {streamer.assigned_user.username}")
                    except Exception as ws_error:
                        logger.warning(f"⚠️ Ошибка WebSocket, пробуем HTTP: {ws_error}")
                        
                        # Fallback: отправляем через HTTP запрос
                        try:
                            import aiohttp
                            async with aiohttp.ClientSession() as session:
                                # Отправляем POST запрос для обновления статистики
                                stats_url = f"http://localhost:8000/stats/shifts/{shift.id}/update/"
                                async with session.post(stats_url, json=stats) as response:
                                    if response.status == 200:
                                        logger.info(f"📊 Статистика обновлена через HTTP для смены {shift.id}")
                                    else:
                                        logger.warning(f"⚠️ HTTP обновление статистики вернуло статус {response.status}")
                        except Exception as http_error:
                            logger.error(f"❌ Ошибка HTTP обновления статистики: {http_error}")
                            
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки статистики: {e}")
            else:
                # Если не было попыток отправки, удаляем пустую смену
                await sync_to_async(shift.delete)()
                logger.info(f"Пропущена отправка для {streamer.vid} - нет активных сообщений")
                
        except Exception as e:
            logger.error(f"Ошибка в цикле стримера {streamer.vid}: {e}")
            import traceback
            traceback.print_exc()
    
    async def _send_message_simple(self, account, channel, message, user):
        """Отправляет сообщение используя ProcessMessageManager (как в основном сайте)"""
        try:
            # Получаем данные аккаунта
            account_login = await sync_to_async(lambda: account.login)()
            account_token = await sync_to_async(lambda: account.token)()
            account_session_token = await sync_to_async(lambda: account.session_token)()
            account_proxy = await sync_to_async(lambda: account.proxy)()
            
            # Проверяем обязательные поля
            if not account_session_token:
                logger.warning(f"❌ No session_token for account {account_login}")
                return False

            if not account_proxy:
                logger.warning(f"❌ No proxy assigned to account {account_login}")
                return False
            
            # Получаем URL прокси
            proxy_url = await sync_to_async(lambda: account_proxy.url)() if account_proxy else ""
            
            # Используем кэшированный ProcessMessageManager для пользователя
            manager = self._get_manager_for_user(user.id)
            
            # Создаем уникальный ID для запроса
            import time
            request_id = f"hydra_{account_login}_{channel}_{int(time.time() * 1000)}"
            
            # Логируем отправку сообщения в консоль
            print(f"📤 Отправляем сообщение: {account_login} -> {channel}: {message}")
            logger.info(f"📤 Отправляем сообщение: {account_login} -> {channel}: {message}")
            
            # Отправляем сообщение через ProcessMessageManager (как в основном сайте)
            result = await manager.send_message_async(
                request_id=request_id,
                channel=channel,
                account=account_login,
                message=message,
                token=account_token,
                session_token=account_session_token,
                proxy_url=proxy_url,
                auto=True  # Это авто-сообщение
            )
            
            # Проверяем результат
            if result and result.status.value == 'success':
                print(f"✅ Сообщение успешно отправлено: {account_login} -> {channel}")
                logger.info(f"✅ Сообщение успешно отправлено через {account_login} в {channel}")
                return True
            else:
                error_msg = result.error if result else "Unknown error"
                # Проверяем, что это ошибка от Kick, а не сеть/таймаут
                error = str(error_msg).lower()
                if any(keyword in error for keyword in ['banned', 'followers', 'rate limit', 'security', 'kick.com']):
                    # Это ответ от Kick - считаем успешным
                    print(f"✅ Сообщение отправлено (ответ от Kick): {account_login} -> {channel} - {error_msg}")
                    logger.info(f"✅ Сообщение отправлено (ответ от Kick): {account_login} - {error_msg}")
                    return True
                else:
                    # Это ошибка сети/таймаут - считаем неуспешным
                    print(f"❌ Ошибка сети/таймаут: {account_login} -> {channel} - {error_msg}")
                    logger.warning(f"❌ Ошибка сети/таймаут: {account_login} - {error_msg}")
                    return False
                
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return False
    
    async def _log_auto_message_to_shift(self, shift, channel, account, message):
        """Логирует автоматическое сообщение в смену"""
        try:
            # Добавляем сообщение в статистику смены
            await sync_to_async(shift.add_message)('a')  # 'a' для автоматических сообщений
            
            # Создаем запись в MessageLog
            from StatsApp.models import MessageLog
            await sync_to_async(MessageLog.objects.create)(
                shift=shift,
                channel=channel,
                account=account,
                message_type='a',  # 'a' для автоматических сообщений
                message=message
            )
            
            # Логируем в ShiftLog для отображения в статистике
            await sync_to_async(shift.add_action)('message_sent', f'Сообщение отправлено: {account} -> {channel}', {
                'account': account,
                'channel': channel,
                'message': message[:50] + '...' if len(message) > 50 else message,
                'type': 'auto'
            })
            
            logger.info(f"📝 Сообщение записано в лог смены {shift.id}: {account} -> {channel}: {message[:50]}...")
            
        except Exception as e:
            logger.error(f"Ошибка логирования в смену: {e}")

    async def _log_shift_action(self, shift, action_type, message, data=None):
        """Логирует действие в смене"""
        try:
            await sync_to_async(shift.add_action)(action_type, message, data)
            logger.info(f"�� Действие '{action_type}' записано в смену {shift.id}: {message}")
        except Exception as e:
            logger.error(f"Ошибка логирования действия в смену: {e}")

# Глобальный экземпляр сервиса
_auto_message_sender = None
_restart_lock = threading.Lock()
_last_restart_time = 0
_start_stop_lock = threading.Lock()
_is_starting = False
_is_stopping = False

def get_auto_message_sender():
    """Возвращает глобальный экземпляр сервиса"""
    global _auto_message_sender
    if _auto_message_sender is None:
        _auto_message_sender = AutoMessageSender()
    return _auto_message_sender

def start_auto_messaging():
    """Запускает автоматическую отправку сообщений"""
    global _is_starting
    
    with _start_stop_lock:
        if _is_starting:
            print("⏸️ Запуск уже в процессе, пропускаем")
            return
        _is_starting = True
    
    try:
        print("🔍 start_auto_messaging() вызвана")
        logger.info("🔍 start_auto_messaging() вызвана")
        
        sender = get_auto_message_sender()
        print(f"🔍 Получен sender: {sender}")
        print(f"🔍 sender.is_running: {sender.is_running}")
        logger.info(f"🔍 Получен sender: {sender}")
        logger.info(f"🔍 sender.is_running: {sender.is_running}")
        
        # Проверяем, не запущен ли уже сервис
        if sender.is_running:
            print("⚠️ Автоматическая рассылка уже запущена")
            logger.warning("⚠️ Автоматическая рассылка уже запущена")
            return
        
        print("🚀 Запускаем автоматическую рассылку...")
        logger.info("🚀 Запускаем автоматическую рассылку...")
        sender.start()
        print("✅ Автоматическая рассылка запущена")
        logger.info("✅ Автоматическая рассылка запущена")
        
    except Exception as e:
        print(f"❌ Ошибка в start_auto_messaging: {e}")
        logger.error(f"❌ Ошибка в start_auto_messaging: {e}")
        import traceback
        traceback.print_exc()
    finally:
        with _start_stop_lock:
            _is_starting = False

def stop_auto_messaging():
    """Останавливает автоматическую отправку сообщений"""
    global _is_stopping
    
    with _start_stop_lock:
        if _is_stopping:
            print("⏸️ Остановка уже в процессе, пропускаем")
            return
        _is_stopping = True
    
    try:
        sender = get_auto_message_sender()
        print("🛑 Останавливаем автоматическую рассылку...")
        logger.info("🛑 Останавливаем автоматическую рассылку...")
        sender.stop()
        print("✅ Автоматическая рассылка остановлена")
        logger.info("✅ Автоматическая рассылка остановлена")
    except Exception as e:
        print(f"❌ Ошибка в stop_auto_messaging: {e}")
        logger.error(f"❌ Ошибка в stop_auto_messaging: {e}")
        import traceback
        traceback.print_exc()
    finally:
        with _start_stop_lock:
            _is_stopping = False

def restart_auto_messaging():
    """Перезапускает автоматическую отправку сообщений"""
    global _last_restart_time
    
    # Защита от множественных вызовов
    current_time = time.time()
    with _restart_lock:
        if current_time - _last_restart_time < 10:  # Увеличиваем до 10 секунд между перезапусками
            print("⏸️ Перезапуск пропущен (слишком часто)")
            logger.warning("⏸️ Перезапуск пропущен (слишком часто)")
            return
        _last_restart_time = current_time
    
    try:
        print("🔄 Перезапускаем автоматическую рассылку...")
        logger.info("🔄 Перезапускаем автоматическую рассылку...")
        
        sender = get_auto_message_sender()
        
        # Проверяем текущее состояние
        if sender.is_running:
            print("🔄 Останавливаем текущий сервис...")
            logger.info("🔄 Останавливаем текущий сервис...")
            sender.stop()
            
            # Ждем полной остановки
            time.sleep(8)  # Увеличиваем время ожидания
            
            # Дополнительная проверка
            if sender.is_running:
                print("⚠️ Сервис все еще запущен, принудительно останавливаем...")
                sender.stop()
            time.sleep(3)
        
        # Проверяем актуальные настройки из базы данных
        if sender.settings:
            sender.settings.refresh_from_db()
        
        if sender.settings and sender.settings.is_enabled:
            print("🚀 Перезапускаем автоматическую рассылку...")
            logger.info("🚀 Перезапускаем автоматическую рассылку...")
            sender.start()
        else:
            print("⏸️ Бот отключен, перезапуск не требуется")
            logger.info("⏸️ Бот отключен, перезапуск не требуется")
            
    except Exception as e:
        print(f"❌ Ошибка перезапуска: {e}")
        logger.error(f"Ошибка перезапуска: {e}")
        import traceback
        traceback.print_exc()

def get_auto_messaging_status():
    """Получает статус автоматической отправки сообщений"""
    sender = get_auto_message_sender()
    return {
        'running': sender.is_running,
        'cycle': sender.current_cycle,
        'settings': {
            'is_enabled': sender.settings.is_enabled,
            'message_interval': sender.settings.message_interval,
            'cycle_interval': sender.settings.cycle_interval,
            'max_concurrent_sends': sender.settings.max_concurrent_sends,
            'min_message_interval': sender.settings.min_message_interval
        }
    } 