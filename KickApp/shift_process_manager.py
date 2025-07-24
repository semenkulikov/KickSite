import asyncio
import multiprocessing
import threading
import time
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import json
import signal
import os
from concurrent.futures import ProcessPoolExecutor
from KickApp.async_message_manager import message_manager

logger = logging.getLogger("kick.shift_manager")

class ShiftStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

@dataclass
class ShiftInfo:
    shift_id: str
    user_id: int
    channel: str
    status: ShiftStatus
    process_id: Optional[int] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    messages_sent: int = 0
    messages_failed: int = 0
    auto_messages_active: bool = False
    frequency: int = 1

class ShiftProcessManager:
    """Менеджер для управления сменами в отдельных процессах"""
    
    def __init__(self, max_processes: int = 10):
        self.max_processes = max_processes
        self.active_shifts: Dict[str, ShiftInfo] = {}
        self.process_pool = ProcessPoolExecutor(max_workers=max_processes)
        self._lock = threading.Lock()
        self.shutdown_event = threading.Event()
        
    async def initialize(self):
        """Инициализация менеджера"""
        await message_manager.initialize()
        logger.info(f"ShiftProcessManager initialized with {self.max_processes} max processes")
    
    async def cleanup(self):
        """Очистка ресурсов"""
        # Останавливаем все активные смены
        await self.stop_all_shifts()
        
        # Закрываем пул процессов
        if self.process_pool:
            self.process_pool.shutdown(wait=True)
        
        # Очищаем менеджер сообщений
        await message_manager.cleanup()
        
        logger.info("ShiftProcessManager cleaned up")
    
    async def start_shift(self, shift_id: str, user_id: int, channel: str, 
                         accounts: List[Dict], messages: List[str], 
                         frequency: int = 1, auto_messages: bool = False) -> bool:
        """Запустить смену в отдельном процессе"""
        
        with self._lock:
            if shift_id in self.active_shifts:
                logger.warning(f"Shift {shift_id} is already active")
                return False
            
            # Создаем информацию о смене
            shift_info = ShiftInfo(
                shift_id=shift_id,
                user_id=user_id,
                channel=channel,
                status=ShiftStatus.PENDING,
                start_time=time.time(),
                auto_messages_active=auto_messages,
                frequency=frequency
            )
            
            self.active_shifts[shift_id] = shift_info
        
        try:
            # Запускаем процесс смены
            loop = asyncio.get_event_loop()
            process = await loop.run_in_executor(
                self.process_pool,
                self._run_shift_process,
                shift_id, user_id, channel, accounts, messages, frequency, auto_messages
            )
            
            with self._lock:
                if process and hasattr(process, 'pid'):
                    shift_info.process_id = process.pid
                shift_info.status = ShiftStatus.ACTIVE
            
            logger.info(f"Started shift {shift_id} in process {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start shift {shift_id}: {e}")
            with self._lock:
                shift_info.status = ShiftStatus.ERROR
            return False
    
    def _run_shift_process(self, shift_id: str, user_id: int, channel: str, 
                          accounts: List[Dict], messages: List[str], 
                          frequency: int, auto_messages: bool):
        """Запуск процесса смены (выполняется в отдельном процессе)"""
        try:
            # Устанавливаем обработчик сигналов для корректного завершения
            signal.signal(signal.SIGTERM, lambda signum, frame: self._handle_shutdown_signal())
            signal.signal(signal.SIGINT, lambda signum, frame: self._handle_shutdown_signal())
            
            logger.info(f"Shift process {shift_id} started in PID {os.getpid()}")
            
            # Здесь будет логика работы смены
            # Пока что просто ждем
            while True:
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Shift process {shift_id} error: {e}")
        finally:
            logger.info(f"Shift process {shift_id} finished")
    
    def _handle_shutdown_signal(self):
        """Обработчик сигнала завершения"""
        logger.info(f"Received shutdown signal in process {os.getpid()}")
        # Отменяем все активные запросы
        message_manager.cancel_all_requests()
    
    async def stop_shift(self, shift_id: str) -> bool:
        """Остановить смену"""
        with self._lock:
            if shift_id not in self.active_shifts:
                logger.warning(f"Shift {shift_id} not found")
                return False
            
            shift_info = self.active_shifts[shift_id]
            shift_info.status = ShiftStatus.STOPPING
        
        try:
            # Отменяем все активные запросы для этой смены
            message_manager.cancel_all_requests()
            
            # Завершаем процесс если он запущен
            if shift_info.process_id:
                try:
                    os.kill(shift_info.process_id, signal.SIGTERM)
                    # Ждем завершения процесса
                    for _ in range(10):  # Максимум 10 секунд
                        try:
                            os.waitpid(shift_info.process_id, os.WNOHANG)
                            break
                        except OSError:
                            time.sleep(1)
                except OSError:
                    pass  # Процесс уже завершен
            
            with self._lock:
                shift_info.status = ShiftStatus.STOPPED
                shift_info.end_time = time.time()
            
            logger.info(f"Stopped shift {shift_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop shift {shift_id}: {e}")
            with self._lock:
                shift_info.status = ShiftStatus.ERROR
            return False
    
    async def stop_all_shifts(self):
        """Остановить все активные смены"""
        shift_ids = list(self.active_shifts.keys())
        for shift_id in shift_ids:
            await self.stop_shift(shift_id)
    
    async def pause_shift(self, shift_id: str) -> bool:
        """Приостановить смену"""
        with self._lock:
            if shift_id not in self.active_shifts:
                return False
            
            shift_info = self.active_shifts[shift_id]
            if shift_info.status == ShiftStatus.ACTIVE:
                shift_info.status = ShiftStatus.PAUSED
                return True
        
        return False
    
    async def resume_shift(self, shift_id: str) -> bool:
        """Возобновить смену"""
        with self._lock:
            if shift_id not in self.active_shifts:
                return False
            
            shift_info = self.active_shifts[shift_id]
            if shift_info.status == ShiftStatus.PAUSED:
                shift_info.status = ShiftStatus.ACTIVE
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
            total = len(self.active_shifts)
            active = sum(1 for s in self.active_shifts.values() if s.status == ShiftStatus.ACTIVE)
            paused = sum(1 for s in self.active_shifts.values() if s.status == ShiftStatus.PAUSED)
            stopping = sum(1 for s in self.active_shifts.values() if s.status == ShiftStatus.STOPPING)
            stopped = sum(1 for s in self.active_shifts.values() if s.status == ShiftStatus.STOPPED)
            error = sum(1 for s in self.active_shifts.values() if s.status == ShiftStatus.ERROR)
            
            total_messages = sum(s.messages_sent for s in self.active_shifts.values())
            total_failed = sum(s.messages_failed for s in self.active_shifts.values())
            
            return {
                'total_shifts': total,
                'active': active,
                'paused': paused,
                'stopping': stopping,
                'stopped': stopped,
                'error': error,
                'total_messages_sent': total_messages,
                'total_messages_failed': total_failed,
                'max_processes': self.max_processes
            }

# Глобальный экземпляр менеджера смен
shift_process_manager = ShiftProcessManager(max_processes=20) 