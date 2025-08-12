import {showAlert} from "./alert";
import {addMessageToLogs} from "./kick-input-logs";
import {selectAccount} from "./kick-account";
import {getKickSocket, workStatus} from "./kick-ws";
import {isAutoSendingActive} from "./kick-auto-messages";
import {recordChatMessageSent, updateChatSpeed} from "./speed-manager";

let averageSendingPerMinuteId;
let pendingMessages = new Map();
window.pendingMessages = pendingMessages;

let chatMessagesSent = 0;
let chatStartTime = null;

// Оптимизированная функция для массовой отправки сообщений
async function sendBatchMessages(messageBatch) {
    const promises = messageBatch.map(messageData => {
        return new Promise((resolve) => {
            const ws = getKickSocket();
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    "type": "KICK_SEND_MESSAGE",
                    "message": messageData,
                }));
                resolve();
            } else {
                resolve();
            }
        });
    });
    
    await Promise.all(promises);
}

// Оптимизированная функция отправки
// Флаг для предотвращения повторного вызова
let isSending = false;

async function optimizedKickSend() {
    // Защита от повторного вызова
    if (isSending) {
        console.log('[optimizedKickSend] Already sending, skipping...');
        return;
    }
    
    isSending = true;
    
    let data = checkingConditions();
    if (!data) {
        console.log('[optimizedKickSend] checkingConditions returned false');
        isSending = false;
        return;
    }

    // Фильтруем только активные выбранные аккаунты (видимые)
    const selectedAccounts = document.querySelectorAll('[data-account-selected="true"]');
    const activeSelectedAccounts = Array.from(selectedAccounts).filter(account => {
        const accountBlock = account.closest('.account-block');
        const status = accountBlock ? accountBlock.getAttribute('data-account-status') : 'active';
        const isVisible = accountBlock ? accountBlock.style.display !== 'none' : true;
        return status === 'active' && isVisible;
    });
    
    console.log(`[optimizedKickSend] Found ${selectedAccounts.length} selected accounts, ${activeSelectedAccounts.length} are active and visible`);

    if (!window.workStatus) {
        showAlert("You haven't started work. Click on the \"Start work\" button", "alert-danger");
        return;
    }

    const messageId = Date.now();
    const isAutoSwitchEnabled = window.accountManager && window.accountManager.autoSwitchEnabled;
    
    try {
        if (isAutoSwitchEnabled) {
            // Режим автоматического переключения
            window.accountManager.switchToNextAccount();
            
            const currentSelectedAccount = document.querySelector('[data-account-selected="true"]');
            if (currentSelectedAccount) {
                const accountLogin = currentSelectedAccount.value;
                const messageData = {
                    "channel": data.channel,
                    "account": accountLogin,
                    "message": data.message,
                    "auto": false,
                    "messageId": messageId,
                    "index": 0
                };
                
                console.log(`[optimizedKickSend] Auto-switch mode: sending from ${accountLogin}`);
                
                pendingMessages.set(`${messageId}_0`, {
                    account: accountLogin,
                    message: data.message,
                    timestamp: Date.now()
                });
                
                chatMessagesSent++;
                recordChatMessageSent();
                addMessageToLogs(messageData);
                
                await sendBatchMessages([messageData]);
                // Не показываем алерт здесь, так как он может дублироваться
            }
        } else {
            // Обычный режим - отправляем со всех активных выбранных аккаунтов
            const messageBatch = [];
            
            activeSelectedAccounts.forEach((accountElement, index) => {
                const accountLogin = accountElement.value;
                const messageData = {
                    "channel": data.channel,
                    "account": accountLogin,
                    "message": data.message,
                    "auto": false,
                    "messageId": messageId,
                    "index": index
                };
                
                console.log(`[optimizedKickSend] Preparing message ${index + 1}/${activeSelectedAccounts.length}: ${accountLogin}`);
                
                pendingMessages.set(`${messageId}_${index}`, {
                    account: accountLogin,
                    message: data.message,
                    timestamp: Date.now()
                });
                
                chatMessagesSent++;
                recordChatMessageSent();
                addMessageToLogs(messageData);
                
                messageBatch.push(messageData);
            });
            
            // Отправляем все сообщения одним батчем
            await sendBatchMessages(messageBatch);
            // Не показываем алерт здесь, так как он может дублироваться
        }

        // Очищаем поле ввода
        const inputMessageElement = document.getElementById('inputMessage');
        if (inputMessageElement) {
            inputMessageElement.value = "";
        }
        
        // Таймаут для очистки "зависших" сообщений
        setTimeout(() => {
            pendingMessages.forEach((msg, key) => {
                if (key.startsWith(messageId.toString())) {
                    console.warn(`[optimizedKickSend] Message timeout: ${msg.account} - ${msg.message}`);
                    pendingMessages.delete(key);
                }
            });
        }, 30000);
        
    } catch (error) {
        console.error('[optimizedKickSend] Error:', error);
        // Не показываем алерт здесь, так как он может дублироваться
    } finally {
        // Сбрасываем флаг в любом случае
        isSending = false;
    }
}

// Функция для обработки ответов от сервера
function handleMessageResponse(responseData, isSuccess) {
    const account = responseData.account || "unknown";
    
    if (isSuccess) {
        const message = responseData.text || responseData.message || "no message";
        // Не показываем алерт об успехе, так как он уже показывается в kick-ws.js
        console.log(`✅ Message sent from ${account}: ${message}`);
    } else {
        const errorMessage = responseData.message || "Unknown error";
        const alertMessage = `❌ Failed to send from ${account}: ${errorMessage}`;
        console.log(`showAlert (danger): ${alertMessage}`);
        // Не показываем алерт здесь, так как он уже показывается в kick-ws.js
    }
}

function countingSendingPerMinute(data) {
    chatMessagesSent += parseInt(data["messages"]);
    const start = new Date(data["startWorkTime"]);
    
    const dateOptions = {
        year: '2-digit', month: '2-digit', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        timeZone: "UTC"
    };

    console.log("Start of the average message sending counter");

    averageSendingPerMinuteId = setInterval(function () {
        let nowTime = new Date();
        let timeDiff = new Date(Math.abs(nowTime - start)).toLocaleDateString('ru-RU', dateOptions).substr(10, );
        let timeDiffSplit = timeDiff.split(":");
        let timeHoursLeft = parseInt(timeDiffSplit[0]) * 60;
        let timeMinutesLeft = parseInt(timeDiffSplit[1]);
        let timeSecondsLeft = parseInt(timeDiffSplit[2]) / 60;
        let totalMinutes = timeHoursLeft + timeMinutesLeft + timeSecondsLeft;

        let messagesPerMinute = totalMinutes > 0 ? (chatMessagesSent / totalMinutes).toFixed(2) : "0.00";
        
        if (!isAutoSendingActive) {
            document.getElementById("averageSendingPerMinute").innerText = messagesPerMinute;
        }
        
        updateChatSpeed();
    }, 5000);
}

function checkingConditions() {
    console.log('[checkingConditions] Starting validation...');
    
    let inputMessage = checkInputMessage();
    let selectedChannel = checkSelectedChannel();
    let hasSelectedAccounts = checkSelectedAccount();

    let results = {
        inputMessage: inputMessage,
        selectedChannel: selectedChannel,
        selectedAccount: hasSelectedAccounts
    };
    
    console.log('[checkingConditions] Results:', results);
    
    if (inputMessage && selectedChannel && hasSelectedAccounts) {
        console.log('[checkingConditions] All validations passed');
        return {
            "channel": selectedChannel,
            "message": inputMessage,
        };
    } else {
        console.log('[checkingConditions] Some validation failed');
        return false;
    }
}

function checkInputMessage() {
    console.log('[checkInputMessage] Checking input message...');
    const inputElement = document.getElementById('inputMessage');
    if (!inputElement) {
        console.error('[checkInputMessage] Input element not found');
        showAlert("Input message element not found!", "alert-danger");
        return false;
    }
    
    const inputValue = inputElement.value;
    console.log('[checkInputMessage] Input value:', inputValue);
    if (inputValue && inputValue.trim() !== "") {
        return inputValue;
    }
    showAlert("You are trying to send an empty message!", "alert-danger");
    return false;
}

function checkSelectedChannel() {
    console.log('[checkSelectedChannel] Checking selected channel...');
    const elementSelectedChannel = document.getElementById("selectedChannel");
    if (!elementSelectedChannel) {
        console.error('[checkSelectedChannel] Selected channel element not found');
        showAlert("Selected channel element not found!", "alert-danger");
        return false;
    }
    
    console.log('[checkSelectedChannel] Channel element dataset:', elementSelectedChannel.dataset);
    if (elementSelectedChannel.dataset.status === "selected") {
        const channelName = elementSelectedChannel.innerText;
        console.log('[checkSelectedChannel] Selected channel:', channelName);
        return channelName;
    }
    showAlert("You have not selected a channel!", "alert-danger");
    return false;
}

function checkSelectedAccount() {
    console.log('[checkSelectedAccount] Checking selected account...');
    
    // Проверяем только активные выбранные аккаунты (видимые)
    const selectedAccounts = document.querySelectorAll('[data-account-selected="true"]');
    const activeSelectedAccounts = Array.from(selectedAccounts).filter(account => {
        const accountBlock = account.closest('.account-block');
        const status = accountBlock ? accountBlock.getAttribute('data-account-status') : 'active';
        const isVisible = accountBlock ? accountBlock.style.display !== 'none' : true;
        return status === 'active' && isVisible;
    });
    
    console.log(`[checkSelectedAccount] Found ${selectedAccounts.length} selected accounts, ${activeSelectedAccounts.length} are active and visible`);
    
    if (activeSelectedAccounts.length === 0) {
        showAlert("You haven't selected any active accounts. Select an active account.", "alert-danger");
        console.log('[checkSelectedAccount] No active accounts selected');
        return false;
    }
    
    console.log(`[checkSelectedAccount] ${activeSelectedAccounts.length} active account(s) selected`);
    return true;
}

// Добавляем обработчики событий
document.addEventListener('DOMContentLoaded', function() {
    $('#sendInputMessage').on("click", () => {
        optimizedKickSend();
    });

    $('#inputMessage').on('keydown', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            optimizedKickSend();
        }
    });
});

export {
    optimizedKickSend,
    countingSendingPerMinute,
    averageSendingPerMinuteId,
    handleMessageResponse,
    sendBatchMessages
}; 