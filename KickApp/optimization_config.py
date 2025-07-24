"""
Конфигурация оптимизации для высокой производительности отправки сообщений
"""

# Настройки асинхронного менеджера сообщений
MESSAGE_MANAGER_CONFIG = {
    'max_concurrent_requests': 500,  # Максимальное количество одновременных запросов
    'max_workers': 200,              # Максимальное количество потоков
    'request_timeout': 30,           # Таймаут запроса в секундах
    'connection_timeout': 10,        # Таймаут соединения в секундах
    'keepalive_timeout': 30,         # Таймаут keep-alive
    'max_connections': 1000,         # Максимальное количество соединений
    'max_connections_per_host': 100, # Максимальное количество соединений на хост
}

# Настройки менеджера смен
SHIFT_MANAGER_CONFIG = {
    'max_processes': 50,             # Максимальное количество процессов смен
    'process_timeout': 300,          # Таймаут процесса в секундах
    'cleanup_delay': 60,             # Задержка очистки в секундах
}

# Настройки фронтенда
FRONTEND_CONFIG = {
    'batch_size': 20,                # Размер батча сообщений
    'batch_delay': 50,               # Задержка между батчами в мс
    'max_frequency': 4000,           # Максимальная частота сообщений в минуту
    'websocket_batch_size': 50,      # Размер батча для WebSocket
}

# Настройки базы данных
DATABASE_CONFIG = {
    'connection_pool_size': 20,      # Размер пула соединений
    'max_connections': 100,          # Максимальное количество соединений
    'connection_timeout': 30,        # Таймаут соединения
    'query_timeout': 60,             # Таймаут запроса
}

# Настройки логирования
LOGGING_CONFIG = {
    'level': 'INFO',                 # Уровень логирования
    'max_file_size': 100 * 1024 * 1024,  # Максимальный размер файла лога (100MB)
    'backup_count': 5,               # Количество резервных файлов
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

# Настройки производительности
PERFORMANCE_CONFIG = {
    'enable_connection_pooling': True,    # Включить пул соединений
    'enable_compression': True,           # Включить сжатие
    'enable_caching': True,               # Включить кэширование
    'cache_timeout': 300,                 # Таймаут кэша в секундах
    'max_memory_usage': 1024 * 1024 * 1024,  # Максимальное использование памяти (1GB)
}

# Настройки мониторинга
MONITORING_CONFIG = {
    'enable_metrics': True,              # Включить метрики
    'metrics_interval': 60,              # Интервал сбора метрик в секундах
    'enable_health_check': True,         # Включить проверку здоровья
    'health_check_interval': 30,         # Интервал проверки здоровья в секундах
}

# Функция для получения конфигурации
def get_config():
    """Получить полную конфигурацию оптимизации"""
    return {
        'message_manager': MESSAGE_MANAGER_CONFIG,
        'shift_manager': SHIFT_MANAGER_CONFIG,
        'frontend': FRONTEND_CONFIG,
        'database': DATABASE_CONFIG,
        'logging': LOGGING_CONFIG,
        'performance': PERFORMANCE_CONFIG,
        'monitoring': MONITORING_CONFIG,
    }

# Функция для валидации конфигурации
def validate_config(config):
    """Валидировать конфигурацию"""
    errors = []
    
    if config['message_manager']['max_concurrent_requests'] <= 0:
        errors.append("max_concurrent_requests must be positive")
    
    if config['message_manager']['max_workers'] <= 0:
        errors.append("max_workers must be positive")
    
    if config['shift_manager']['max_processes'] <= 0:
        errors.append("max_processes must be positive")
    
    if config['frontend']['batch_size'] <= 0:
        errors.append("batch_size must be positive")
    
    if config['frontend']['max_frequency'] <= 0:
        errors.append("max_frequency must be positive")
    
    return errors

# Функция для применения конфигурации
def apply_config(config):
    """Применить конфигурацию к системе"""
    from KickApp.async_message_manager import message_manager
    from KickApp.shift_process_manager import shift_process_manager
    
    # Применяем настройки к менеджеру сообщений
    message_manager.max_concurrent_requests = config['message_manager']['max_concurrent_requests']
    message_manager.max_workers = config['message_manager']['max_workers']
    
    # Применяем настройки к менеджеру смен
    shift_process_manager.max_processes = config['shift_manager']['max_processes']
    
    return True 