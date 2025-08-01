import threading
import time
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import StreamerStatus, StreamerHydraSettings, HydraBotSettings

# Глобальная переменная для отслеживания последнего срабатывания сигнала
_last_signal_time = 0
_signal_lock = threading.Lock()

def _is_signal_throttled():
    """Проверяет, не слишком ли часто срабатывают сигналы"""
    global _last_signal_time
    current_time = time.time()
    with _signal_lock:
        if current_time - _last_signal_time < 5:  # Увеличиваем до 5 секунд между сигналами
            return True
        _last_signal_time = current_time
        return False

@receiver(post_save, sender=StreamerStatus, weak=False)
def update_streamer_hydra_settings(sender, instance, created, **kwargs):
    """
    Обновляет настройки Гидры для стримера при изменении статуса
    """
    if _is_signal_throttled():
        print(f"⏸️ Сигнал пропущен (throttled) для стримера {instance.vid}")
        return
        
    try:
        print(f"🔔 Сигнал сработал для стримера {instance.vid}, is_hydra_enabled={instance.is_hydra_enabled}")
        
        # Создаем или обновляем индивидуальные настройки
        hydra_settings, created = StreamerHydraSettings.objects.get_or_create(
            streamer=instance,
            defaults={
                'is_active': instance.is_hydra_enabled,
                'message_interval': None,
                'cycle_interval': None
            }
        )
        
        if not created:
            # Обновляем существующие настройки
            hydra_settings.is_active = instance.is_hydra_enabled
            hydra_settings.save()
        
        print(f"🔄 Обновлены настройки Гидры для стримера {instance.vid}: is_active={hydra_settings.is_active}")
        
        # Не останавливаем всю Hydra при отключении стримера
        # Hydra сама проверит статусы стримеров в следующем цикле
        if not instance.is_hydra_enabled:
            print(f"⏸️ Стример {instance.vid} отключен, но Hydra продолжает работать для других стримеров")
        
    except Exception as e:
        print(f"❌ Ошибка обновления настроек Гидры для {instance.vid}: {e}")


@receiver(post_save, sender=StreamerHydraSettings)
def restart_hydra_on_streamer_settings_change(sender, instance, created, **kwargs):
    """
    Перезапускает бота Гидру при изменении индивидуальных настроек стримера
    """
    if _is_signal_throttled():
        print(f"⏸️ Сигнал пропущен (throttled) для настроек стримера {instance.streamer.vid}")
        return
        
    try:
        print(f"🔔 Сигнал: стример {instance.streamer.vid}, is_active={instance.is_active}, global_enabled=True")
        
        # Импортируем здесь чтобы избежать циклических импортов
        from .auto_message_sender import restart_auto_messaging, get_auto_message_sender, stop_auto_messaging
        
        # Запускаем перезапуск в отдельном потоке
        def restart_in_thread():
            import time as time_module
            time_module.sleep(3)  # Увеличиваем паузу для применения изменений
            
            # Проверяем актуальные настройки из базы данных
            instance.refresh_from_db()
            
            # Получаем текущий статус сервиса
            sender = get_auto_message_sender()
            current_running = sender.is_running
            
            # Проверяем глобальные настройки Гидры
            from .models import HydraBotSettings
            global_settings = HydraBotSettings.get_settings()
            
            print(f"🔔 Сигнал: стример {instance.streamer.vid}, is_active={instance.is_active}, global_enabled={global_settings.is_enabled}")
            
            # Проверяем, есть ли активные стримеры в гидре (только с активным статусом)
            active_streamers = StreamerStatus.objects.filter(
                is_hydra_enabled=True,
                assigned_user__isnull=False,
                status='active'  # Добавляем фильтр по статусу
            ).count()
            
            print(f"🔍 Активных стримеров в гидре: {active_streamers}")
            
            # Проверяем, должен ли этот стример быть активным
            should_be_active = global_settings.is_enabled and instance.is_active
            
            if should_be_active:
                if current_running:
                    print(f"🔄 Перезапускаем бота Гидру после изменения настроек стримера {instance.streamer.vid}...")
                    restart_auto_messaging()
                else:
                    print(f"🚀 Запускаем бота Гидру после изменения настроек стримера {instance.streamer.vid}...")
                    restart_auto_messaging()
            else:
                # Не останавливаем всю Hydra при отключении стримера
                # Hydra сама проверит статусы стримеров в следующем цикле
                print(f"⏸️ Стример {instance.streamer.vid} отключен, но Hydra продолжает работать для других стримеров")
        
        threading.Thread(target=restart_in_thread, daemon=True).start()
        
    except Exception as e:
        print(f"Ошибка перезапуска Гидры после изменения настроек стримера: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=HydraBotSettings)
def restart_hydra_on_settings_change(sender, instance, created, **kwargs):
    """
    Перезапускает бота Гидру при изменении настроек
    """
    if _is_signal_throttled():
        print(f"⏸️ Сигнал HydraBotSettings пропущен (throttled)")
        return
        
    print(f"🔔 СИГНАЛ СРАБОТАЛ: HydraBotSettings post_save")
    print(f"🔔 created={created}, is_enabled={instance.is_enabled}")
    
    # Не срабатываем при создании новой записи
    if created:
        print("⏸️ Пропускаем создание новой записи")
        return
        
    try:
        print(f"🔔 Сигнал HydraBotSettings: is_enabled={instance.is_enabled}")
        
        # Импортируем здесь чтобы избежать циклических импортов
        from .auto_message_sender import restart_auto_messaging, get_auto_message_sender, stop_auto_messaging
        
        # Запускаем перезапуск в отдельном потоке
        def restart_in_thread():
            import time as time_module
            time_module.sleep(3)  # Увеличиваем паузу для применения изменений
            
            # Проверяем актуальные настройки из базы данных
            instance.refresh_from_db()
            
            # Получаем текущий статус сервиса
            sender = get_auto_message_sender()
            current_running = sender.is_running
            
            print(f"🔍 Проверка статуса: is_enabled={instance.is_enabled}, current_running={current_running}")
            
            if instance.is_enabled:
                if current_running:
                    print("🔄 Перезапускаем бота Гидру...")
                    restart_auto_messaging()
                else:
                    print("🚀 Запускаем бота Гидру...")
                    restart_auto_messaging()
            else:
                if current_running:
                    print("🛑 Отключаем бота Гидру...")
                    stop_auto_messaging()
                    
                    # Дополнительная проверка
                    time_module.sleep(5)  # Увеличиваем время ожидания
                    if sender.is_running:
                        print("⚠️ Сервис все еще запущен, принудительно останавливаем...")
                        sender.stop()
                else:
                    print("⏸️ Бот Гидра уже отключен")
        
        threading.Thread(target=restart_in_thread, daemon=True).start()
        
    except Exception as e:
        print(f"❌ Ошибка перезапуска Гидры: {e}")
        import traceback
        traceback.print_exc() 