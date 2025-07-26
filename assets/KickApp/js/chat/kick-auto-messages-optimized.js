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
let batchSize = 200; // Максимальный размер батча для 4000+ сообщений в минуту
let batchDelay = 5; // Минимальная задержка между батчами

// Оптимизированная функция для массовой отправки сообщений
async function sendBatchMessages(batch) {
    const ws = getKickSocket();
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.warn('[OPTIMIZED_AUTO] WebSocket not available for batch sending');
        return;
    }
    
    // Отправляем все сообщения асинхронно для максимальной скорости
    const promises = batch.map(messageData => {
        return new Promise((resolve) => {
            try {
                ws.send(JSON.stringify({
                    "type": "KICK_SEND_MESSAGE",
                    "message": messageData,
                }));
                resolve();
            } catch (error) {
                console.error('[OPTIMIZED_AUTO] Error sending message:', error);
                resolve();
            }
        });
    });
    
    // Ждем завершения всех отправок
    await Promise.all(promises);
}

// Оптимизированная функция авторассылки
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
        // Создаем батч сообщений для отправки
        const batch = [];
        const currentTime = Date.now();
        
        for (let i = 0; i < batchSize; i++) {
            const accountIndex = (autoMessageIndex + i) % selectedAccounts.length;
            const messageIndex = Math.floor((autoMessageIndex + i) / selectedAccounts.length) % autoMessages.length;
            
            const account = selectedAccounts[accountIndex];
            const message = autoMessages[messageIndex];
            
            const messageData = {
                "channel": document.getElementById("selectedChannel")?.innerText || "default",
                "account": account,
                "message": message,
                "auto": true,
                "messageId": currentTime + i,
                "index": i
            };
            
            batch.push(messageData);
            autoMessagesSent++;
            recordAutoMessageSent();
            addMessageToLogs(messageData);
        }
        
        // Отправляем батч
        await sendBatchMessages(batch);
        
        // Обновляем индекс
        autoMessageIndex = (autoMessageIndex + batchSize) % (selectedAccounts.length * autoMessages.length);
        
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
    

    
    // Рассчитываем интервал для батчей с оптимизацией для 4000+ сообщений в минуту
    const messagesPerMinute = autoMessageFrequency;
    const messagesPerSecond = messagesPerMinute / 60;
    const batchInterval = Math.max(100, (batchSize / messagesPerSecond) * 1000); // минимум 100мс для стабильности
    
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
function setOptimizationParams(newBatchSize = 200, newBatchDelay = 5) {
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