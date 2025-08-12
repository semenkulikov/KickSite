import {showAlert} from "./alert";
import {addMessageToLogs} from "./kick-input-logs";
import {selectAccount} from "./kick-account";
import {getKickSocket, workStatus} from "./kick-ws";
import {isAutoSendingActive} from "./kick-auto-messages";
import {recordChatMessageSent, updateChatSpeed} from "./speed-manager";
import {optimizedKickSend, sendBatchMessages} from "./kick-send-optimized";

let averageSendingPerMinuteId;
let pendingMessages = new Map(); // Отслеживание ожидающих отправки сообщений
// Делаем pendingMessages доступным глобально для очистки при остановке работы
window.pendingMessages = pendingMessages;

// Переменные для отслеживания скорости
let chatMessagesSent = 0;
let chatStartTime = null;

$('#sendInputMessage').on("click", () => {
  optimizedKickSend();
});

const dateOptions = {
          year: '2-digit', month: '2-digit', day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          timeZone: "UTC"
        };

let messagesSent = 0;

$('#inputMessage').on('keydown', function(event) {
  if (event.key === 'Enter') {
    event.preventDefault();

    optimizedKickSend();
  }
});

function kickSend() {
  let data = checkingConditions()
  if (data) {
    // Фильтруем только активные выбранные аккаунты
    const selectedAccounts = document.querySelectorAll('[data-account-selected="true"]');
    const activeSelectedAccounts = Array.from(selectedAccounts).filter(account => {
      const accountBlock = account.closest('.account-block');
      const status = accountBlock ? accountBlock.getAttribute('data-account-status') : 'active';
      return status === 'active';
    });
    
    console.log(`[kickSend] Found ${selectedAccounts.length} selected accounts, ${activeSelectedAccounts.length} are active`);

    if (window.workStatus) {
      const messageId = Date.now(); // Уникальный ID для этой группы сообщений
      let sentCount = 0;
      let totalCount = activeSelectedAccounts.length;
      
      // Проверяем, включено ли автоматическое переключение
      const isAutoSwitchEnabled = window.accountManager && window.accountManager.autoSwitchEnabled;
      
      if (isAutoSwitchEnabled) {
        // В режиме автоматического переключения сначала переключаем на следующий аккаунт
        window.accountManager.switchToNextAccount();
        
        // Затем отправляем с текущего выбранного аккаунта
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
          
          console.log(`[kickSend] Auto-switch mode: sending from ${accountLogin}`);
          console.log(`${accountLogin}: ${data.message}`);
          
          // Добавляем в отслеживание
          pendingMessages.set(`${messageId}_0`, {
            account: accountLogin,
            message: data.message,
            timestamp: Date.now()
          });
          
          messagesSent++;
          recordChatMessageSent(); // Записываем отправку ручного сообщения
          addMessageToLogs(messageData);
          
          getKickSocket().send(JSON.stringify({
            "type": "KICK_SEND_MESSAGE",
            "message": messageData,
          }));
          
          // Показываем прогресс
          showAlert(`📤 Sending from ${accountLogin}...`, "alert-info");
        }
      } else {
        // Обычный режим - отправляем со всех активных выбранных аккаунтов
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
          
          console.log(`[kickSend] Sending message from account ${index + 1}/${activeSelectedAccounts.length}: ${accountLogin}`);
          console.log(`${accountLogin}: ${data.message}`);
          
          // Добавляем в отслеживание
          pendingMessages.set(`${messageId}_${index}`, {
            account: accountLogin,
            message: data.message,
            timestamp: Date.now()
          });
          
          messagesSent++;
          recordChatMessageSent(); // Записываем отправку ручного сообщения
          addMessageToLogs(messageData);
          
          getKickSocket().send(JSON.stringify({
            "type": "KICK_SEND_MESSAGE",
            "message": messageData,
          }));
        });

        // Показываем прогресс
        showAlert(`📤 Sending ${totalCount} message(s)...`, "alert-info");
      }

      // Очищаем поле ввода только если элемент существует
      const inputMessageElement = document.getElementById('inputMessage');
      if (inputMessageElement) {
        inputMessageElement.value = "";
      }
      
      // Таймаут для очистки "зависших" сообщений
      setTimeout(() => {
        pendingMessages.forEach((msg, key) => {
          if (key.startsWith(messageId)) {
            console.warn(`[kickSend] Message timeout: ${msg.account} - ${msg.message}`);
            pendingMessages.delete(key);
            
            // Переключение аккаунта теперь происходит в автоматической рассылке
            // Убираем переключение отсюда, чтобы избежать двойного переключения
          }
        });
      }, 30000); // 30 секунд таймаут
      
    }
    else {
      showAlert("You haven't started work. Click on the \"Start work\" button", "alert-danger")
    }
  } else {
    console.log('[kickSend] checkingConditions returned false - some validation failed');
  }
}

// Функция для обработки ответов от сервера
function handleMessageResponse(responseData, isSuccess) {
  const account = responseData.account || "unknown";
  
  if (isSuccess) {
    // Убираем алерт для успешных сообщений - показываем только ошибки
    // const message = responseData.text || responseData.message || "no message";
    // showAlert(`✅ Message sent from ${account}: ${message}`, "alert-success");
    console.log(`✅ Message sent from ${account}: ${responseData.text || responseData.message || "no message"}`);
  } else {
    // Показываем точно то, что присылает Kick.com
    const errorMessage = responseData.message || "Unknown error";
    const alertMessage = `❌ Failed to send from ${account}: ${errorMessage}`;
    console.log(`showAlert (danger): ${alertMessage}`);
    showAlert(alertMessage, "alert-danger");
  }
  
  // Переключение аккаунта теперь происходит сразу при нажатии на кнопку Chat
  // Убираем переключение отсюда, чтобы избежать двойного переключения
}

function countingSendingPerMinute(data) {
  messagesSent += parseInt(data["messages"])
  const start = new Date(data["startWorkTime"])
  let timeHoursLeft;
  let timeMinutesLeft;
  let timeSecondsLeft;
  let totalMinutes;

  console.log("Start of the average message sending counter")

  averageSendingPerMinuteId = setInterval(function () {
    let nowTime = new Date();
    let timeDiff = new Date(Math.abs(nowTime - start)).toLocaleDateString('ru-RU', dateOptions).substr(10, );
    let timeDiffSplit = timeDiff.split(":")
    timeHoursLeft = parseInt(timeDiffSplit[0]) * 60
    timeMinutesLeft = parseInt(timeDiffSplit[1])
    timeSecondsLeft = parseInt(timeDiffSplit[2]) / 60
    totalMinutes = timeHoursLeft + timeMinutesLeft + timeSecondsLeft

    let messagesPerMinute = totalMinutes > 0 ? (messagesSent / totalMinutes).toFixed(2) : "0.00";
    // Не обновляем averageSendingPerMinute если авторассылка активна
    if (!isAutoSendingActive) {
      document.getElementById("averageSendingPerMinute").innerText = messagesPerMinute;
    }
    
    // Обновляем скорость чата
    updateChatSpeed();
    
    // console.log(`Messages/minute: ${messagesPerMinute}`)
  }, 5000)
}



function checkingConditions() {
  console.log('[checkingConditions] Starting validation...');
  
  let inputMessage = checkInputMessage()
  let selectedChannel = checkSelectedChannel()
  let hasSelectedAccounts = checkSelectedAccount()

  let results = {
    inputMessage: inputMessage,
    selectedChannel: selectedChannel,
    selectedAccount: hasSelectedAccounts
  }
  
  console.log('[checkingConditions] Results:', results);
  
  if (inputMessage && selectedChannel && hasSelectedAccounts) {
    console.log('[checkingConditions] All validations passed');
    return {
    "channel": selectedChannel,
    "message": inputMessage,
    }
  }
  else {
    console.log('[checkingConditions] Some validation failed');
  return false
  }
}

function checkInputMessage(){
  console.log('[checkInputMessage] Checking input message...');
  const inputElement = document.getElementById('inputMessage');
  if (!inputElement) {
    console.error('[checkInputMessage] Input element not found');
    showAlert("Input message element not found!", "alert-danger")
    return false
  }
  
  const inputValue = inputElement.value;
  console.log('[checkInputMessage] Input value:', inputValue);
  if (inputValue && inputValue.trim() !== "") {
    return inputValue
  }
  showAlert("You are trying to send an empty message!", "alert-danger")
  return false
}

function checkSelectedChannel() {
  console.log('[checkSelectedChannel] Checking selected channel...');
  const elementSelectedChannel = document.getElementById("selectedChannel");
  if (!elementSelectedChannel) {
    console.error('[checkSelectedChannel] Selected channel element not found');
    showAlert("Selected channel element not found!", "alert-danger")
    return false
  }
  
  console.log('[checkSelectedChannel] Channel element dataset:', elementSelectedChannel.dataset);
  if (elementSelectedChannel.dataset.status === "selected") {
    const channelName = elementSelectedChannel.innerText;
    console.log('[checkSelectedChannel] Selected channel:', channelName);
    return channelName
  }
  showAlert("You have not selected a channel!", "alert-danger")
  return false
}

function checkSelectedAccount() {
  console.log('[checkSelectedAccount] Checking selected account...');
  
  // Проверяем только активные выбранные аккаунты
  const selectedAccounts = document.querySelectorAll('[data-account-selected="true"]');
  const activeSelectedAccounts = Array.from(selectedAccounts).filter(account => {
    const accountBlock = account.closest('.account-block');
    const status = accountBlock ? accountBlock.getAttribute('data-account-status') : 'active';
    return status === 'active';
  });
  
  console.log(`[checkSelectedAccount] Found ${selectedAccounts.length} selected accounts, ${activeSelectedAccounts.length} are active`);
  
  if (activeSelectedAccounts.length === 0) {
    showAlert("You haven't selected any active accounts. Select an active account.", "alert-danger");
    console.log('[checkSelectedAccount] No active accounts selected');
    return false;
  }
  
  console.log(`[checkSelectedAccount] ${activeSelectedAccounts.length} active account(s) selected`);
  return true;
}

export {countingSendingPerMinute, averageSendingPerMinuteId, handleMessageResponse}
