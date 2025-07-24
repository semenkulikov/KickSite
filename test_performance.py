#!/usr/bin/env python3
"""
Тестовый скрипт для проверки производительности отправки сообщений
"""

import asyncio
import time
import json
import websockets
import logging
from concurrent.futures import ThreadPoolExecutor
import threading

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceTester:
    def __init__(self, ws_url="ws://127.0.0.1:8000/ws-kick/chat"):
        self.ws_url = ws_url
        self.websocket = None
        self.message_count = 0
        self.start_time = None
        self.lock = threading.Lock()
        
    async def connect(self):
        """Подключение к WebSocket"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            logger.info(f"Connected to {self.ws_url}")
            
            # Отправляем приветственное сообщение
            await self.websocket.send(json.dumps({
                "event": "KICK_CONNECT",
                "message": "HELLO"
            }))
            
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
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
            
            with self.lock:
                self.message_count += 1
            
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    async def send_batch_messages(self, batch_size=10, delay=0.1):
        """Отправка батча сообщений"""
        tasks = []
        for i in range(batch_size):
            task = self.send_test_message(
                account=f"test_account_{i % 5}",
                channel="test_channel",
                message=f"Test message {i}"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)
        
        logger.info(f"Batch sent: {success_count}/{batch_size} successful")
        return success_count
    
    async def run_performance_test(self, total_messages=100, batch_size=10, delay=0.1):
        """Запуск теста производительности"""
        logger.info(f"Starting performance test: {total_messages} messages, batch_size={batch_size}, delay={delay}s")
        
        self.message_count = 0
        self.start_time = time.time()
        
        batches = total_messages // batch_size
        remaining = total_messages % batch_size
        
        total_sent = 0
        
        # Отправляем полные батчи
        for i in range(batches):
            sent = await self.send_batch_messages(batch_size, delay)
            total_sent += sent
            
            if delay > 0:
                await asyncio.sleep(delay)
            
            # Логируем прогресс каждые 10 батчей
            if (i + 1) % 10 == 0:
                elapsed = time.time() - self.start_time
                rate = total_sent / elapsed if elapsed > 0 else 0
                logger.info(f"Progress: {total_sent}/{total_messages} messages sent, rate: {rate:.2f} msg/s")
        
        # Отправляем оставшиеся сообщения
        if remaining > 0:
            sent = await self.send_batch_messages(remaining, delay)
            total_sent += sent
        
        # Финальная статистика
        elapsed = time.time() - self.start_time
        rate = total_sent / elapsed if elapsed > 0 else 0
        rate_per_minute = rate * 60
        
        logger.info(f"Performance test completed:")
        logger.info(f"  Total messages: {total_sent}")
        logger.info(f"  Time elapsed: {elapsed:.2f}s")
        logger.info(f"  Rate: {rate:.2f} msg/s ({rate_per_minute:.2f} msg/min)")
        
        return {
            'total_sent': total_sent,
            'elapsed_time': elapsed,
            'rate_per_second': rate,
            'rate_per_minute': rate_per_minute
        }
    
    async def close(self):
        """Закрытие соединения"""
        if self.websocket:
            await self.websocket.close()
            logger.info("Connection closed")

async def main():
    """Основная функция"""
    tester = PerformanceTester()
    
    try:
        # Подключаемся
        if not await tester.connect():
            return
        
        # Запускаем тесты с разными параметрами
        test_configs = [
            {'total': 50, 'batch_size': 5, 'delay': 0.1},
            {'total': 100, 'batch_size': 10, 'delay': 0.05},
            {'total': 200, 'batch_size': 20, 'delay': 0.02},
        ]
        
        for config in test_configs:
            logger.info(f"\n{'='*50}")
            logger.info(f"Running test with config: {config}")
            logger.info(f"{'='*50}")
            
            result = await tester.run_performance_test(
                total_messages=config['total'],
                batch_size=config['batch_size'],
                delay=config['delay']
            )
            
            # Проверяем производительность
            if result['rate_per_minute'] >= 1000:
                logger.info("✅ Target performance achieved (1000+ msg/min)")
            else:
                logger.warning(f"❌ Performance below target: {result['rate_per_minute']:.2f} msg/min")
            
            # Пауза между тестами
            await asyncio.sleep(2)
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        await tester.close()

if __name__ == "__main__":
    asyncio.run(main()) 