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
async function optimizedKickSend() {
    let data = checkingConditions();
    if (!data) {
        console.log('[optimizedKickSend] checkingConditions returned false');
        return;
    }

    const selectedAccounts = document.querySelectorAll('[data-account-selected="true"]');
    console.log(`[optimizedKickSend] Found ${selectedAccounts.length} selected accounts`);

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
                showAlert(`📤 Sending from ${accountLogin}...`, "alert-info");
            }
        } else {
            // Обычный режим - отправляем со всех выбранных аккаунтов
            const messageBatch = [];
            
            selectedAccounts.forEach((accountElement, index) => {
                const accountLogin = accountElement.value;
                const messageData = {
                    "channel": data.channel,
                    "account": accountLogin,
                    "message": data.message,
                    "auto": false,
                    "messageId": messageId,
                    "index": index
                };
                
                console.log(`[optimizedKickSend] Preparing message ${index + 1}/${selectedAccounts.length}: ${accountLogin}`);
                
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
            showAlert(`📤 Sending ${selectedAccounts.length} message(s)...`, "alert-info");
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
        showAlert(`Error sending messages: ${error.message}`, "alert-danger");
    }
}

// Функция для обработки ответов от сервера
function handleMessageResponse(responseData, isSuccess) {
    const account = responseData.account || "unknown";
    
    if (isSuccess) {
        const message = responseData.text || responseData.message || "no message";
        showAlert(`✅ Message sent from ${account}: ${message}`, "alert-success");
    } else {
        const errorMessage = responseData.message || "Unknown error";
        const alertMessage = `❌ Failed to send from ${account}: ${errorMessage}`;
        console.log(`showAlert (danger): ${alertMessage}`);
        showAlert(alertMessage, "alert-danger");
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
    
    const selectedAccounts = document.querySelectorAll('[data-account-selected="true"]');
    console.log(`[checkSelectedAccount] Found ${selectedAccounts.length} selected accounts`);
    
    if (selectedAccounts.length === 0) {
        showAlert("You haven't selected an account. Select an account.", "alert-danger");
        console.log('[checkSelectedAccount] No accounts selected');
        return false;
    }
    
    console.log(`[checkSelectedAccount] ${selectedAccounts.length} account(s) selected`);
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