import {getFrequency, addOrUpdateFrequencyDB} from "./kick-frequency-db";
import {getAutoMessages, addAutoMessages, clearAllAutoMessages, openAutoMessagesDB} from "./kick-auto-messages-db";
import {addMessageToLogs} from "./kick-input-logs";
import {getKickSocket, workStatus} from "./kick-ws";
import {showAlert} from "./alert";
import {recordAutoMessageSent, resetAutoSpeed} from "./speed-manager";

let intervalSendAutoMessageId;
let intervalTimerSendAutoMessageId;
let isAutoSendingActive = false;
let autoMessageStartTime = null;
let autoMessagesSent = 0;
let autoMessageFrequency = 0;
let autoMessageIndex = 0;
let selectedAccounts = [];
let autoMessages = [];
let batchSize = 500; // Увеличиваем размер батча для максимальной скорости
let batchDelay = 1; // Минимальная задержка между батчами
let messageWorker = null; // Web Worker для обработки сообщений

// Оптимизированная функция для массовой отправки сообщений - FIRE AND FORGET
function sendBatchMessages(batch) {
    const ws = getKickSocket();
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.warn('[OPTIMIZED_AUTO] WebSocket not available for batch sending');
        return;
    }
    
    // Отправляем все сообщения без ожидания - максимальная скорость
    // Используем более эффективный формат для больших батчей
    const messages = batch.map(messageData => ({
        "type": "KICK_SEND_MESSAGE",
        "message": messageData,
    }));
    
    // Отправляем все сообщения одним батчем
    messages.forEach(msg => {
        try {
            ws.send(JSON.stringify(msg));
        } catch (error) {
            console.error('[OPTIMIZED_AUTO] Error sending message:', error);
        }
    });
}

// Оптимизированная функция авторассылки с Web Worker
async function optimizedAutoMessageSending() {
    if (!isAutoSendingActive || !workStatus || !window.workStatus) {
        console.log('[OPTIMIZED_AUTO] Stopping due to work status:', { isAutoSendingActive, workStatus, windowWorkStatus: window.workStatus });
        stopOptimizedAutoMessageSending();
        return;
    }
    
    if (selectedAccounts.length === 0 || autoMessages.length === 0) {
        console.log('[OPTIMIZED_AUTO] No accounts or messages available');
        return;
    }
    
    try {
        // Используем Web Worker для создания батча в фоне
        if (messageWorker) {
            messageWorker.postMessage({
                type: 'PROCESS_BATCH',
                data: {
                    accounts: selectedAccounts,
                    messages: autoMessages,
                    batchSize: batchSize,
                    startIndex: autoMessageIndex
                }
            });
        } else {
            // Fallback без Web Worker
            const batch = [];
            const currentTime = Date.now();
            const channel = document.getElementById("selectedChannel")?.innerText || "default";
            
            const baseMessageData = {
                "channel": channel,
                "auto": true
            };
            
            for (let i = 0; i < batchSize; i++) {
                const accountIndex = (autoMessageIndex + i) % selectedAccounts.length;
                const messageIndex = Math.floor((autoMessageIndex + i) / selectedAccounts.length) % autoMessages.length;
                
                const messageData = {
                    ...baseMessageData,
                    "account": selectedAccounts[accountIndex],
                    "message": autoMessages[messageIndex],
                    "messageId": currentTime + i
                };
                
                batch.push(messageData);
            }
            
            sendBatchMessages(batch);
            autoMessagesSent += batchSize;
            autoMessageIndex = (autoMessageIndex + batchSize) % (selectedAccounts.length * autoMessages.length);
        }
        
        console.log(`[OPTIMIZED_AUTO] Sent batch of ${batchSize} messages. Total sent: ${autoMessagesSent}`);
        
    } catch (error) {
        console.error('[OPTIMIZED_AUTO] Error sending batch:', error);
    }
}

// Функция для запуска оптимизированной авторассылки
function startOptimizedAutoMessageSending() {
    if (isAutoSendingActive) {
        console.log('[OPTIMIZED_AUTO] Auto sending already active');
        return;
    }
    
    // Инициализируем Web Worker если поддерживается
    if (!messageWorker && typeof Worker !== 'undefined') {
        try {
            messageWorker = new Worker('/static/assets/KickApp/js/chat/message-worker.js');
            // Fallback если не найден
            if (!messageWorker) {
                console.warn('[OPTIMIZED_AUTO] Web Worker not available, using fallback');
                return;
            }
            messageWorker.onmessage = function(e) {
                const { type, batch, nextIndex } = e.data;
                if (type === 'BATCH_READY') {
                    const channel = document.getElementById("selectedChannel")?.innerText || "default";
                    const baseMessageData = {
                        "channel": channel,
                        "auto": true
                    };
                    
                    // Добавляем недостающие поля к сообщениям из Worker
                    const fullBatch = batch.map(msg => ({
                        ...baseMessageData,
                        ...msg
                    }));
                    
                    sendBatchMessages(fullBatch);
                    autoMessagesSent += batchSize;
                    autoMessageIndex = nextIndex;
                }
            };
            console.log('[OPTIMIZED_AUTO] Web Worker initialized');
        } catch (error) {
            console.warn('[OPTIMIZED_AUTO] Web Worker not available, using fallback:', error);
        }
    }
    
    // Получаем выбранные аккаунты
    selectedAccounts = Array.from(document.querySelectorAll('[data-account-selected="true"]'))
        .map(el => el.value);
    
    // Получаем сообщения
    const textarea = document.getElementById("autoMessageTextArea");
    if (textarea) {
        autoMessages = textarea.value.split("\n")
            .map(line => line.trim())
            .filter(line => line !== "");
    }
    

    
    if (selectedAccounts.length === 0) {
        showAlert("No accounts selected for auto sending", "alert-warning", true, 3000);
        return;
    }
    
    if (autoMessages.length === 0) {
        showAlert("No messages configured for auto sending", "alert-warning", true, 3000);
        return;
    }
    
    // Получаем частоту
    const freqElement = document.getElementById("frequency-send");
    if (freqElement) {
        autoMessageFrequency = parseInt(freqElement.value) || 1;
    }
    

    
    // Рассчитываем интервал для батчей с максимальной оптимизацией
    const messagesPerMinute = autoMessageFrequency;
    const messagesPerSecond = messagesPerMinute / 60;
    const batchInterval = Math.max(50, (batchSize / messagesPerSecond) * 1000); // минимум 50мс для максимальной скорости
    
    console.log(`[OPTIMIZED_AUTO] Starting with ${selectedAccounts.length} accounts, ${autoMessages.length} messages, ${autoMessageFrequency} msg/min`);
    console.log(`[OPTIMIZED_AUTO] Batch interval: ${batchInterval}ms`);
    
    isAutoSendingActive = true;
    autoMessageStartTime = Date.now();
    autoMessagesSent = 0;
    autoMessageIndex = 0;
    
    // Запускаем интервал для отправки батчей
    intervalSendAutoMessageId = setInterval(optimizedAutoMessageSending, batchInterval);
    window.optimizedAutoMessageInterval = intervalSendAutoMessageId; // Сохраняем глобально
    
    // Обновляем UI
    const checkbox = document.getElementById('sendAutoMessageStatus');
    if (checkbox) {
        checkbox.checked = true;
    }
    
    const editAutoMessageBtn = document.getElementById("editAutoMessage");
    if (editAutoMessageBtn) {
        editAutoMessageBtn.disabled = true;
    }
    
            showAlert(`🚀 Auto sending started: ${autoMessageFrequency} msg/min`, "alert-success", true, 3000);
}

// Функция для остановки оптимизированной авторассылки
function stopOptimizedAutoMessageSending() {
    console.log('[OPTIMIZED_AUTO] Stopping auto sending...');
    
    // Останавливаем все интервалы агрессивно
    if (intervalSendAutoMessageId) {
        clearInterval(intervalSendAutoMessageId);
        intervalSendAutoMessageId = null;
        console.log('[OPTIMIZED_AUTO] Cleared intervalSendAutoMessageId');
    }
    
    if (intervalTimerSendAutoMessageId) {
        clearInterval(intervalTimerSendAutoMessageId);
        intervalTimerSendAutoMessageId = null;
        console.log('[OPTIMIZED_AUTO] Cleared intervalTimerSendAutoMessageId');
    }
    
    // Очищаем глобальные интервалы
    if (window.intervalSendAutoMessageId) {
        clearInterval(window.intervalSendAutoMessageId);
        window.intervalSendAutoMessageId = null;
        console.log('[OPTIMIZED_AUTO] Cleared global intervalSendAutoMessageId');
    }
    
    if (window.intervalTimerSendAutoMessageId) {
        clearInterval(window.intervalTimerSendAutoMessageId);
        window.intervalTimerSendAutoMessageId = null;
        console.log('[OPTIMIZED_AUTO] Cleared global intervalTimerSendAutoMessageId');
    }
    
    // Сбрасываем состояние
    isAutoSendingActive = false;
    autoMessageStartTime = null;
    autoMessagesSent = 0;
    autoMessageIndex = 0;
    
    // Очищаем Web Worker
    if (messageWorker) {
        messageWorker.terminate();
        messageWorker = null;
        console.log('[OPTIMIZED_AUTO] Web Worker terminated');
    }
    
    // Обновляем UI
    const checkbox = document.getElementById('sendAutoMessageStatus');
    if (checkbox) {
        checkbox.checked = false;
    }
    
    const editAutoMessageBtn = document.getElementById("editAutoMessage");
    if (editAutoMessageBtn) {
        editAutoMessageBtn.disabled = false;
    }
    
    resetAutoSpeed();
    
    // Не показываем алерт здесь, так как он может дублироваться
    console.log('[OPTIMIZED_AUTO] Auto sending stopped completely');
}

// Функция для настройки параметров оптимизации
function setOptimizationParams(newBatchSize = 500, newBatchDelay = 1) {
    batchSize = newBatchSize;
    batchDelay = newBatchDelay;
    console.log(`[OPTIMIZED_AUTO] Optimization params updated: batchSize=${batchSize}, batchDelay=${batchDelay}ms`);
}

// Делаем функции глобально доступными
window.startOptimizedAutoMessageSending = startOptimizedAutoMessageSending;
window.stopOptimizedAutoMessageSending = stopOptimizedAutoMessageSending;
window.setOptimizationParams = setOptimizationParams;

// Экспортируем функции
export {
    startOptimizedAutoMessageSending,
    stopOptimizedAutoMessageSending,
    setOptimizationParams,
    isAutoSendingActive,
    autoMessagesSent,
    autoMessageFrequency
}; 