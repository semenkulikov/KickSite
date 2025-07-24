import asyncio
import multiprocessing
import time
import logging
import threading
import signal
import os
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("kick.shift_process_manager")

class ShiftStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"

@dataclass
class ShiftInfo:
    shift_id: str
    user_id: int
    status: ShiftStatus
    process: Optional[multiprocessing.Process] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[str] = None

def run_shift_process(shift_data):
    """Функция для запуска смены в отдельном процессе"""
    import asyncio
    import json
    import websockets
    from KickApp.process_message_manager import process_message_manager
    
    try:
        # Устанавливаем обработчик сигнала для возможности отмены
        def signal_handler(signum, frame):
            logger.info(f"Shift process {os.getpid()} received signal {signum}, shutting down...")
            os._exit(1)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Извлекаем данные смены
        user_id = shift_data['user_id']
        shift_id = shift_data['shift_id']
        websocket_url = shift_data['websocket_url']
        
        logger.info(f"[SHIFT_PROCESS] Starting shift {shift_id} for user {user_id}")
        
        async def shift_worker():
            """Основная функция смены"""
            try:
                # Инициализируем менеджер процессов
                await process_message_manager.initialize()
                
                # Подключаемся к WebSocket
                async with websockets.connect(websocket_url) as websocket:
                    logger.info(f"[SHIFT_PROCESS] Connected to WebSocket for shift {shift_id}")
                    
                    # Отправляем сообщение о начале смены
                    await websocket.send(json.dumps({
                        'type': 'SHIFT_STARTED',
                        'shift_id': shift_id,
                        'user_id': user_id
                    }))
                    
                    # Основной цикл смены
                    while True:
                        try:
                            # Проверяем сообщения от WebSocket
                            message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            data = json.loads(message)
                            
                            if data.get('type') == 'SHIFT_STOP':
                                logger.info(f"[SHIFT_PROCESS] Received stop signal for shift {shift_id}")
                                break
                                
                        except asyncio.TimeoutError:
                            # Таймаут - продолжаем работу
                            continue
                        except Exception as e:
                            logger.error(f"[SHIFT_PROCESS] WebSocket error: {e}")
                            break
                    
                    # Отправляем сообщение о завершении смены
                    await websocket.send(json.dumps({
                        'type': 'SHIFT_ENDED',
                        'shift_id': shift_id,
                        'user_id': user_id
                    }))
                    
            except Exception as e:
                logger.error(f"[SHIFT_PROCESS] Error in shift worker: {e}")
            finally:
                # Очищаем ресурсы
                await process_message_manager.cleanup()
        
        # Запускаем асинхронную функцию в процессе
        asyncio.run(shift_worker())
        
    except Exception as e:
        logger.error(f"[SHIFT_PROCESS] Exception in shift process: {e}")
        return f"Exception: {str(e)}"

class ShiftProcessManagerV2:
    """Менеджер смен с использованием отдельных процессов"""
    
    def __init__(self, max_concurrent_shifts: int = 10):
        self.max_concurrent_shifts = max_concurrent_shifts
        self.active_shifts: Dict[str, ShiftInfo] = {}
        self.executor = multiprocessing.Pool(processes=max_concurrent_shifts)
        self.cancellation_event = threading.Event()
        self._lock = threading.Lock()
        self._shutdown = False
        
    async def initialize(self):
        """Инициализация менеджера"""
        logger.info(f"ShiftProcessManagerV2 initialized with {self.max_concurrent_shifts} concurrent shifts")
    
    async def cleanup(self):
        """Очистка ресурсов"""
        self._shutdown = True
        await self.stop_all_shifts()
        
        if self.executor:
            self.executor.close()
            self.executor.join()
        logger.info("ShiftProcessManagerV2 cleaned up")
    
    async def start_shift(self, shift_id: str, user_id: int, websocket_url: str) -> bool:
        """Запустить смену в отдельном процессе"""
        
        if self._shutdown:
            logger.error("Manager is shutting down, cannot start shift")
            return False
        
        with self._lock:
            if shift_id in self.active_shifts:
                logger.error(f"Shift {shift_id} is already running")
                return False
            
            # Создаем информацию о смене
            shift_info = ShiftInfo(
                shift_id=shift_id,
                user_id=user_id,
                status=ShiftStatus.PENDING,
                start_time=time.time()
            )
            
            self.active_shifts[shift_id] = shift_info
        
        try:
            # Подготавливаем данные для процесса
            process_data = {
                'shift_id': shift_id,
                'user_id': user_id,
                'websocket_url': websocket_url
            }
            
            # Запускаем процесс
            process = multiprocessing.Process(
                target=run_shift_process,
                args=(process_data,),
                name=f"shift_{shift_id}"
            )
            
            process.start()
            
            # Обновляем информацию о смене
            with self._lock:
                shift_info.process = process
                shift_info.status = ShiftStatus.RUNNING
            
            logger.info(f"Started shift {shift_id} in process {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting shift {shift_id}: {e}")
            with self._lock:
                shift_info.status = ShiftStatus.ERROR
                shift_info.error = str(e)
                if shift_id in self.active_shifts:
                    del self.active_shifts[shift_id]
            return False
    
    async def stop_shift(self, shift_id: str) -> bool:
        """Остановить смену"""
        with self._lock:
            if shift_id not in self.active_shifts:
                logger.warning(f"Shift {shift_id} not found")
                return False
            
            shift_info = self.active_shifts[shift_id]
            
            if shift_info.status == ShiftStatus.STOPPED:
                return True
            
            # Убиваем процесс если он существует
            if shift_info.process and shift_info.process.is_alive():
                try:
                    shift_info.process.terminate()
                    shift_info.process.kill()  # Принудительное завершение
                    logger.info(f"Killed process {shift_info.process.pid} for shift {shift_id}")
                except Exception as e:
                    logger.error(f"Error killing process for shift {shift_id}: {e}")
            
            shift_info.status = ShiftStatus.STOPPED
            shift_info.end_time = time.time()
            
            # Удаляем из активных смен
            del self.active_shifts[shift_id]
            
            logger.info(f"Stopped shift {shift_id}")
            return True
    
    async def stop_all_shifts(self):
        """Остановить все смены"""
        logger.info("Stopping all shifts...")
        
        with self._lock:
            shift_ids = list(self.active_shifts.keys())
        
        for shift_id in shift_ids:
            await self.stop_shift(shift_id)
        
        logger.info("All shifts stopped")
    
    async def pause_shift(self, shift_id: str) -> bool:
        """Приостановить смену"""
        with self._lock:
            if shift_id not in self.active_shifts:
                return False
            
            shift_info = self.active_shifts[shift_id]
            if shift_info.status == ShiftStatus.RUNNING:
                shift_info.status = ShiftStatus.PAUSED
                logger.info(f"Paused shift {shift_id}")
                return True
        
        return False
    
    async def resume_shift(self, shift_id: str) -> bool:
        """Возобновить смену"""
        with self._lock:
            if shift_id not in self.active_shifts:
                return False
            
            shift_info = self.active_shifts[shift_id]
            if shift_info.status == ShiftStatus.PAUSED:
                shift_info.status = ShiftStatus.RUNNING
                logger.info(f"Resumed shift {shift_id}")
                return True
        
        return False
    
    def get_shift_info(self, shift_id: str) -> Optional[ShiftInfo]:
        """Получить информацию о смене"""
        with self._lock:
            return self.active_shifts.get(shift_id)
    
    def get_all_shifts(self) -> List[ShiftInfo]:
        """Получить все активные смены"""
        with self._lock:
            return list(self.active_shifts.values())
    
    def get_stats(self) -> Dict:
        """Получить статистику менеджера"""
        with self._lock:
            stats = {
                'active_shifts': len(self.active_shifts),
                'max_shifts': self.max_concurrent_shifts,
                'shutdown': self._shutdown,
                'cancellation_event_set': self.cancellation_event.is_set()
            }
        return stats

# Создаем глобальный экземпляр
shift_process_manager_v2 = ShiftProcessManagerV2() 