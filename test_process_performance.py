#!/usr/bin/env python3
"""
Тест производительности новой архитектуры с процессами
"""

import asyncio
import time
import json
import logging
import websockets
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProcessPerformanceTester:
    """Тестер производительности для новой архитектуры с процессами"""
    
    def __init__(self, websocket_url="ws://127.0.0.1:8000/ws-kick/chat"):
        self.websocket_url = websocket_url
        self.websocket = None
        self.message_count = 0
        self.start_time = None
        self.lock = asyncio.Lock()
        
    async def connect(self):
        """Подключение к WebSocket"""
        try:
            self.websocket = await websockets.connect(self.websocket_url)
            logger.info("Connected to WebSocket")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def send_test_message(self, account="test_account", channel="test_channel", message="test"):
        """Отправка тестового сообщения"""
        try:
            if not self.websocket:
                logger.error("WebSocket not connected")
                return False
                
            message_data = {
                "type": "KICK_SEND_MESSAGE",
                "message": {
                    "channel": channel,
                    "account": account,
                    "message": message,
                    "auto": False
                }
            }
            
            await self.websocket.send(json.dumps(message_data))
            
            async with self.lock:
                self.message_count += 1
            
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    async def send_batch_messages(self, batch_size=50, accounts=None, channel="test_channel"):
        """Отправка батча сообщений"""
        if accounts is None:
            accounts = [f"test_account_{i}" for i in range(batch_size)]
        
        tasks = []
        for i, account in enumerate(accounts):
            message = f"test_message_{i}_{int(time.time())}"
            task = self.send_test_message(account, channel, message)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)
        
        logger.info(f"Batch sent: {success_count}/{batch_size} messages")
        return success_count
    
    async def run_performance_test(self, total_messages=1000, batch_size=50, delay_between_batches=0.1):
        """Запуск теста производительности"""
        logger.info(f"Starting performance test: {total_messages} messages, batch_size={batch_size}")
        
        self.start_time = time.time()
        self.message_count = 0
        
        batches = total_messages // batch_size
        accounts = [f"test_account_{i}" for i in range(batch_size)]
        
        for batch_num in range(batches):
            batch_start = time.time()
            
            success_count = await self.send_batch_messages(batch_size, accounts, "test_channel")
            
            batch_time = time.time() - batch_start
            batch_rate = success_count / batch_time if batch_time > 0 else 0
            
            logger.info(f"Batch {batch_num + 1}/{batches}: {success_count} messages in {batch_time:.2f}s ({batch_rate:.1f} msg/s)")
            
            if delay_between_batches > 0:
                await asyncio.sleep(delay_between_batches)
        
        total_time = time.time() - self.start_time
        total_rate = self.message_count / total_time if total_time > 0 else 0
        rate_per_min = total_rate * 60
        
        logger.info(f"Performance test completed:")
        logger.info(f"  Total messages: {self.message_count}")
        logger.info(f"  Total time: {total_time:.2f}s")
        logger.info(f"  Rate: {total_rate:.1f} msg/s ({rate_per_min:.0f} msg/min)")
        
        return {
            'total_messages': self.message_count,
            'total_time': total_time,
            'rate_per_second': total_rate,
            'rate_per_minute': rate_per_min
        }
    
    async def test_process_termination(self):
        """Тест быстрого завершения процессов"""
        logger.info("Testing process termination...")
        
        # Запускаем интенсивную отправку
        test_task = asyncio.create_task(
            self.run_performance_test(total_messages=500, batch_size=25, delay_between_batches=0.05)
        )
        
        # Ждем немного и затем "останавливаем"
        await asyncio.sleep(2)
        
        logger.info("Simulating 'End Work' - should stop all processes immediately")
        
        # Отправляем команду остановки
        if self.websocket:
            stop_data = {
                "type": "KICK_END_WORK",
                "message": "End work"
            }
            await self.websocket.send(json.dumps(stop_data))
        
        # Ждем завершения
        try:
            await asyncio.wait_for(test_task, timeout=5)
            logger.info("Test completed normally")
        except asyncio.TimeoutError:
            logger.info("Test was terminated (expected)")
        
        # Проверяем, что сообщения действительно остановились
        await asyncio.sleep(2)
        final_count = self.message_count
        logger.info(f"Final message count: {final_count}")
        
        return final_count
    
    async def close(self):
        """Закрытие соединения"""
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket connection closed")

async def main():
    """Основная функция тестирования"""
    tester = ProcessPerformanceTester()
    
    if not await tester.connect():
        logger.error("Failed to connect, exiting")
        return
    
    try:
        # Тест 1: Базовая производительность
        logger.info("=== TEST 1: Basic Performance ===")
        results = await tester.run_performance_test(
            total_messages=200, 
            batch_size=20, 
            delay_between_batches=0.1
        )
        
        # Тест 2: Высокая нагрузка
        logger.info("=== TEST 2: High Load ===")
        results_high = await tester.run_performance_test(
            total_messages=500, 
            batch_size=50, 
            delay_between_batches=0.05
        )
        
        # Тест 3: Тест остановки процессов
        logger.info("=== TEST 3: Process Termination ===")
        final_count = await tester.test_process_termination()
        
        # Вывод результатов
        logger.info("=== FINAL RESULTS ===")
        logger.info(f"Test 1: {results['rate_per_minute']:.0f} msg/min")
        logger.info(f"Test 2: {results_high['rate_per_minute']:.0f} msg/min")
        logger.info(f"Process termination test: {final_count} messages sent before stop")
        
        if results_high['rate_per_minute'] >= 1000:
            logger.info("✅ Performance target achieved!")
        else:
            logger.warning("⚠️ Performance target not reached")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        await tester.close()

if __name__ == "__main__":
    # Устанавливаем multiprocessing для Windows
    multiprocessing.set_start_method('spawn', force=True)
    
    asyncio.run(main()) 