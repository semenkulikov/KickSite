import {getFrequency, addOrUpdateFrequencyDB} from "./kick-frequency-db";
import {getAutoMessages, addAutoMessages, clearAllAutoMessages, openAutoMessagesDB} from "./kick-auto-messages-db";
import {addMessageToLogs} from "./kick-input-logs";
import {getKickSocket, workStatus} from "./kick-ws";
import {showAlert} from "./alert";
import {recordAutoMessageSent, resetAutoSpeed} from "./speed-manager";
import {startOptimizedAutoMessageSending, stopOptimizedAutoMessageSending, setOptimizationParams} from "./kick-auto-messages-optimized";

let intervalSendAutoMessageId;
let intervalTimerSendAutoMessageId;
let isAutoSendingActive = false; // Глобальная переменная для отслеживания состояния авторассылки
let autoMessageStartTime = null; // Время начала авторассылки
let autoMessagesSent = 0; // Счетчик отправленных автосообщений
let autoMessageFrequency = 0; // Частота автосообщений
let autoMessageIndex = 0; // Индекс текущего сообщения для последовательной отправки

if (document.getElementById("editAutoMessage")) {
document.getElementById("editAutoMessage").addEventListener("click", function () {
  console.log("Load auto-messages and frequency from DB if exists");
  document.getElementById("autoMessageTextArea").value = '';
  loadAutoMessagesData();
});
}

// Добавляем обработчик для обновления preview при вводе
document.addEventListener('DOMContentLoaded', function() {
  initializeMessagePreview();
  
  // Добавляем обработчик для модального окна
  const modal = document.getElementById('editAutoMessageModal');
  if (modal) {
    modal.addEventListener('shown.bs.modal', function() {
      console.log('[Modal] Modal shown, updating preview');
      setTimeout(updateMessagePreview, 100);
    });
  }
  
  // Добавляем обработчик изменения frequency через слайдер
  const frequencyInput = document.getElementById("autoMessageFrequencyInput");
  if (frequencyInput) {
    frequencyInput.addEventListener('input', function() {
      const freqValue = parseInt(this.value) || 1;
      const freqSend = document.getElementById("frequency-send");
      if (freqSend) {
        freqSend.value = freqValue;
      }
      
      // Логируем изменение frequency в смену
      const ws = getKickSocket();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'KICK_LOG_ACTION',
          action_type: 'settings_change',
          description: `Frequency changed to ${freqValue} messages/min`,
          details: {
            action: 'frequency_change',
            frequency: freqValue
          }
        }));
      }
    });
  }
  
  // Добавляем обработчик изменения frequency через input поле
  const freqSend = document.getElementById("frequency-send");
  if (freqSend) {
    freqSend.addEventListener('input', function() {
      const freqValue = parseInt(this.value) || 1;
      
      // Логируем изменение frequency в смену
      const ws = getKickSocket();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'KICK_LOG_ACTION',
          action_type: 'settings_change',
          description: `Frequency changed to ${freqValue} messages/min`,
          details: {
            action: 'frequency_change',
            frequency: freqValue
          }
        }));
      }
    });
  }
});

function initializeMessagePreview() {
  const textarea = document.getElementById("autoMessageTextArea");
  if (textarea) {
    console.log('[initializeMessagePreview] Setting up event listeners for textarea');
    textarea.addEventListener('input', updateMessagePreview);
    textarea.addEventListener('keyup', updateMessagePreview);
    textarea.addEventListener('change', updateMessagePreview);
    textarea.addEventListener('paste', updateMessagePreview);
    
    // Initial update
    setTimeout(updateMessagePreview, 100);
  } else {
    console.error('[initializeMessagePreview] Textarea not found');
  }
}

// Загружаем данные при старте страницы
document.addEventListener('DOMContentLoaded', function() {
  // Небольшая задержка, чтобы DOM полностью загрузился
  setTimeout(function() {
    loadAutoMessagesData();
  }, 100);
});

if (document.getElementById("saveAutoMessages")) {
document.getElementById("saveAutoMessages").addEventListener("click", function () {
  console.log("Click save auto messages");
  saveAutoMessages()
  setTimeout(function() {
    const modal = bootstrap.Modal.getInstance(document.getElementById('editAutoMessageModal'));
    if (modal) {
      modal.hide();
      document.body.classList.remove('modal-open');
      document.body.style = '';
      document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
    }
  }, 200);
});
}

if (document.getElementById('sendAutoMessageStatus')) {
document.getElementById('sendAutoMessageStatus').addEventListener("click", function () {
  const checkbox = document.getElementById('sendAutoMessageStatus');

  if (window.workStatus) {
    if (checkbox.checked) {
      // Логируем включение auto messages
      const ws = getKickSocket();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'KICK_LOG_ACTION',
          action_type: 'auto_start',
          description: 'Auto messages enabled',
          details: {
            action: 'auto_messages_enabled'
          }
        }));
      }
      let elementSelectedChannel = document.getElementById("selectedChannel");

      if (elementSelectedChannel.dataset.status === "selected") {
        let channel = elementSelectedChannel.innerText;

        let accounts = document.querySelectorAll('.account-block[data-account-status="active"]');

        if (accounts.length) {
          // Загружаем сообщения из базы данных
          getAutoMessages().then((messages) => {
            if (messages && messages.length) {
                              // Получаем частоту из базы данных
                getFrequency().then((frequency) => {
                  let freq = frequency && frequency.value ? parseInt(frequency.value) || 1 : 1;
                  autoMessageFrequency = freq;
                  
                  // Принудительно обновляем отображение Messages/minutes
                  const averageSendingPerMinute = document.getElementById("averageSendingPerMinute");
                  if (averageSendingPerMinute) {
                    averageSendingPerMinute.innerText = freq.toString();
                  }
                  
                  // Логируем frequency в смену при запуске авторассылки
                  const ws = getKickSocket();
                  if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                      type: 'KICK_LOG_ACTION',
                      action_type: 'settings_change',
                      description: `Auto messages started with frequency ${freq} messages/min`,
                      details: {
                        action: 'auto_frequency_set',
                        frequency: freq
                      }
                    }));
                  }

                
                const editAutoMessageBtn = document.getElementById("editAutoMessage");
                if (editAutoMessageBtn) {
                  editAutoMessageBtn.disabled = true;
                }
                console.log("Click start new")

                // Показываем алерт о начале авторассылки
                showAlert(`Automatic message sending started! Frequency: ${freq} messages/min`, "alert-success");

                // Устанавливаем флаг авторассылки
                isAutoSendingActive = true;

                // Сохраняем время начала авторассылки
                autoMessageStartTime = Date.now();

                let intervalMs = Math.floor(60000 / freq); // Calculate interval in milliseconds
                let timer = intervalMs;

                console.log(`Starting auto-send with frequency: ${freq} messages/min, interval: ${intervalMs}ms`);

                intervalSendAutoMessageId = setInterval(function () {
                  // Проверяем, включен ли auto switch режим
                  const isAutoSwitchEnabled = window.accountManager && window.accountManager.autoSwitchEnabled;
                  
                  if (isAutoSwitchEnabled) {
                    // В auto switch режиме переключаем на следующий аккаунт
                    window.accountManager.switchToNextAccount();
                    
                    // Получаем текущий выбранный аккаунт
                    const currentSelectedAccount = document.querySelector('.account-block[data-account-selected="true"]');
                    
                    if (currentSelectedAccount && messages && messages.length > 0) {
                      const loginElement = currentSelectedAccount.querySelector('.account-login');
                      let accountLogin = loginElement ? loginElement.textContent : '';
                      // Выбираем следующее сообщение по порядку
                      let message = messages[autoMessageIndex % messages.length];
                      let data = {
                          "channel": channel,
                          "account": accountLogin,
                          "message": message,
                          "auto": true
                      }
                      // Возвращаем логи в глобальные
                      addMessageToLogs(data);
                      recordAutoMessageSent(); // Записываем отправку автосообщения
                      getKickSocket().send(JSON.stringify({
                          "type": "KICK_SEND_MESSAGE",
                          "message": data,
                      }));
                      
                      // Увеличиваем индекс для следующего сообщения
                      autoMessageIndex++;
                    }
                  } else {
                    // Новая логика для обычного режима
                    const selectedAccounts = document.querySelectorAll('.account-block[data-account-selected="true"]');
                    
                    if (selectedAccounts.length > 0 && messages && messages.length > 0) {
                      // Выбираем случайный выбранный аккаунт
                      const randomIndex = Math.floor(Math.random() * selectedAccounts.length);
                      const selectedAccount = selectedAccounts[randomIndex];
                      
                      if (selectedAccount) {
                        const loginElement = selectedAccount.querySelector('.account-login');
                        let accountLogin = loginElement ? loginElement.textContent : '';
                        // Выбираем следующее сообщение по порядку
                        let message = messages[autoMessageIndex % messages.length];
                        let data = {
                            "channel": channel,
                            "account": accountLogin,
                            "message": message,
                            "auto": true
                        }
                        // Возвращаем логи в глобальные
                        addMessageToLogs(data);
                        recordAutoMessageSent(); // Записываем отправку автосообщения
                        getKickSocket().send(JSON.stringify({
                            "type": "KICK_SEND_MESSAGE",
                            "message": data,
                        }));
                        
                        // Увеличиваем индекс для следующего сообщения
                        autoMessageIndex++;
                      }
                    }
                  }
                  
                  // Сбрасываем таймер на полный интервал
                  timer = intervalMs;
                }, intervalMs); // Use dynamic interval

                intervalTimerSendAutoMessageId = setInterval(function () {
                  const timerElement = document.getElementById("timerAutoMessage");
                  if (timerElement && autoMessageStartTime) {
                    // Показываем время работы авторассылки (не обратный отсчет)
                    const now = Date.now();
                    const elapsed = now - autoMessageStartTime;
                    const minutes = Math.floor(elapsed / 60000);
                    const seconds = Math.floor((elapsed % 60000) / 1000);
                    timerElement.innerText = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                  }
                }, 1000)
              }).catch((error) => {
                console.error('Error loading frequency:', error);
                $("#sendAutoMessageStatus").prop('checked', false);
                showAlert("Error loading frequency settings", "alert-danger");
              });
            } else {
              $("#sendAutoMessageStatus").prop('checked', false);
              console.log("You don't have any messages to send automatically")
              showAlert("You don't have any messages to send automatically", "alert-danger")
            }
          }).catch((error) => {
            console.error('Error loading messages:', error);
            $("#sendAutoMessageStatus").prop('checked', false);
            showAlert("Error loading auto messages", "alert-danger");
          });
        } else {
          $("#sendAutoMessageStatus").prop('checked', false);
          console.log("You don't have any uploaded accounts")
          showAlert("You don't have any uploaded accounts", "alert-danger")
        }
      } else {
        $("#sendAutoMessageStatus").prop('checked', false);
        console.log("You have not selected a channel");
        showAlert("You have not selected a channel", "alert-danger")
      }
    } else {
      // Логируем отключение auto messages
      const ws = getKickSocket();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'KICK_LOG_ACTION',
          action_type: 'auto_stop',
          description: 'Auto messages disabled',
          details: {
            action: 'auto_messages_disabled'
          }
        }));
      }
      
      const editAutoMessageBtn = document.getElementById("editAutoMessage");
      if (editAutoMessageBtn) {
        editAutoMessageBtn.disabled = false;
      }
      console.log("Click stop new")
      clearInterval(intervalSendAutoMessageId);
      clearInterval(intervalTimerSendAutoMessageId);
      
      // Показываем алерт о прекращении авторассылки
      showAlert("Automatic message sending stopped", "alert-warning");
      // Сбрасываем флаг авторассылки
      isAutoSendingActive = false;
      autoMessageStartTime = null;
    }
  } else {
    $("#sendAutoMessageStatus").prop('checked', false);
    showAlert("You haven't started work. Click on the \"Start work\" button", "alert-danger")
  }
});
}

// Функция для запуска авторассылки при получении KICK_START_WORK
function startAutoMessageSending() {
  const checkbox = document.getElementById('sendAutoMessageStatus');
  if (checkbox && checkbox.checked) {
    // Настраиваем параметры оптимизации для высокой производительности
    setOptimizationParams(50, 50); // 50 сообщений в батче, 50мс задержка
    
    // Запускаем оптимизированную авторассылка
    startOptimizedAutoMessageSending();
  }
}

// Функция для остановки авторассылки при получении KICK_END_WORK
function stopAutoMessageSending() {
  console.log('[stopAutoMessageSending] Stopping auto message sending...');
  
  // Останавливаем оптимизированную авторассылка
  if (window.stopOptimizedAutoMessageSending) {
    window.stopOptimizedAutoMessageSending();
  }
  
  // Очищаем все интервалы
  if (window.intervalSendAutoMessageId) {
    clearInterval(window.intervalSendAutoMessageId);
    window.intervalSendAutoMessageId = null;
  }
  if (window.intervalTimerSendAutoMessageId) {
    clearInterval(window.intervalTimerSendAutoMessageId);
    window.intervalTimerSendAutoMessageId = null;
  }
  
  // Сбрасываем чекбокс
  const checkbox = document.getElementById('sendAutoMessageStatus');
  if (checkbox) {
    checkbox.checked = false;
  }
  
  console.log('[stopAutoMessageSending] Auto message sending stopped');
}

// Делаем функцию глобально доступной
window.stopAutoMessageSending = stopAutoMessageSending;



function updateMessagePreview() {
  const textarea = document.getElementById("autoMessageTextArea");
  const preview = document.getElementById("messagePreview");
  const count = document.getElementById("messageCount");
  
  if (textarea && preview && count) {
    const messages = textarea.value.split("\n").map(line => line.trim()).filter(line => line !== "");
    
    console.log('[updateMessagePreview] Messages count:', messages.length);
    console.log('[updateMessagePreview] Messages:', messages);
    
    // Обновляем счетчик
    count.innerText = messages.length;
    
    // Обновляем preview
    if (messages.length > 0) {
      let previewHtml = '';
      messages.forEach((message, index) => {
        previewHtml += `<div class="mb-1"><small class="text-muted">${index + 1}.</small> <span class="text-white">${message.substring(0, 50)}${message.length > 50 ? '...' : ''}</span></div>`;
      });
      preview.innerHTML = previewHtml;
    } else {
      preview.innerHTML = '<small class="text-muted">Messages will appear here...</small>';
    }
  } else {
    console.error('[updateMessagePreview] Required elements not found:', {
      textarea: !!textarea,
      preview: !!preview,
      count: !!count
    });
  }
}

function loadAutoMessagesData() {
  console.log('Loading auto messages data...');
  
  getFrequency().then((frequency) => {
    console.log('Frequency loaded:', frequency);
    if (frequency && frequency.value) {
      const freqValue = parseInt(frequency.value) || 1;
      changeViewFrequency(freqValue);
      // Обновляем отображение Messages/minutes при загрузке
      const averageSendingPerMinute = document.getElementById("averageSendingPerMinute");
      if (averageSendingPerMinute) {
        averageSendingPerMinute.innerText = freqValue.toString();
        console.log('Set averageSendingPerMinute to:', freqValue);
      }
      
      // Логируем загруженную frequency в смену с задержкой для установки WebSocket
      setTimeout(() => {
        const ws = getKickSocket();
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: 'KICK_LOG_ACTION',
            action_type: 'settings_change',
            description: `Frequency loaded: ${freqValue} messages/min`,
            details: {
              action: 'frequency_loaded',
              frequency: freqValue
            }
          }));
        }
      }, 1000);
    } else {
      // Если данных нет, устанавливаем значение по умолчанию
      const averageSendingPerMinute = document.getElementById("averageSendingPerMinute");
      if (averageSendingPerMinute) {
        averageSendingPerMinute.innerText = "1";
        console.log('Set averageSendingPerMinute to default: 1');
      }
    }
  }).catch((error) => {
    console.error('Error loading frequency:', error);
    // При ошибке устанавливаем значение по умолчанию
    const averageSendingPerMinute = document.getElementById("averageSendingPerMinute");
    if (averageSendingPerMinute) {
      averageSendingPerMinute.innerText = "1";
      console.log('Set averageSendingPerMinute to default after error: 1');
    }
  });

  getAutoMessages().then((messages) => {
    console.log('Messages loaded:', messages);
    if (messages && messages.length > 0) {
      changeViewAutoMessages(messages);
      
      // Обновляем отображение количества автосообщений в новом элементе
      const autoMessagesElement = document.getElementById("autoMessagesCount");
      if (autoMessagesElement) {
        autoMessagesElement.innerText = messages.length;
      }
    } else {
      // Если нет сообщений, показываем 0
      const autoMessagesElement = document.getElementById("autoMessagesCount");
      if (autoMessagesElement) {
        autoMessagesElement.innerText = "0";
      }
    }
  }).catch((error) => {
    console.error('Error loading messages:', error);
    // При ошибке показываем 0
    const autoMessagesElement = document.getElementById("autoMessagesCount");
    if (autoMessagesElement) {
      autoMessagesElement.innerText = "0";
    }
  });
}

function selectAutoSendAccounts(selectedAccounts) {
  let accounts = document.getElementsByClassName('account__checkbox');
  $.each(accounts, function (index, value) {
    value.parentNode.classList.remove("account-auto-send");
  });
  $.each(selectedAccounts, function (index, value) {
    value.parentNode.classList.add("account-auto-send");
  });
}

function changeViewFrequency(frequency) {
  const freqValue = parseInt(frequency) || 1;
  const freqInput = document.getElementById("autoMessageFrequencyInput");
  const freqSend = document.getElementById("frequency-send");
  if (freqInput) freqInput.value = freqValue;
  if (freqSend) freqSend.value = freqValue;
}

function changeViewAutoMessages(messages) {
  const autoMessageTextArea = document.getElementById("autoMessageTextArea");
  if (autoMessageTextArea) {
    // Очищаем textarea перед добавлением сообщений
    autoMessageTextArea.value = '';
    messages.forEach((message) => {
      autoMessageTextArea.value = autoMessageTextArea.value + message + "\n"
    });
    // Обновляем preview после загрузки сообщений
    console.log('[changeViewAutoMessages] Messages loaded, updating preview');
    setTimeout(updateMessagePreview, 50);
  }
}

function saveAutoMessages() {
  const autoMessageTextArea = document.getElementById("autoMessageTextArea");
  const frequencySend = document.getElementById("frequency-send");

  if (!autoMessageTextArea || !frequencySend) {
    showAlert("Error: Required elements not found", "alert-danger");
    return;
  }

  let messages = autoMessageTextArea.value.split("\n").map((element) => element.trim()).filter((element) => element !== "");
  if (messages.length) {
    const freqValue = parseInt(frequencySend.value) || 1;
    addOrUpdateFrequencyDB(freqValue);

    // Логируем изменение частоты и сообщений
    const ws = getKickSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'KICK_LOG_ACTION',
        action_type: 'settings_change',
        description: `Frequency changed to ${freqValue} messages/min, ${messages.length} messages saved`,
        details: {
          action: 'frequency_and_messages_change',
          frequency: freqValue,
          messages_count: messages.length
        }
      }));
    }

    // Сначала очищаем старые сообщения, потом добавляем новые
    clearAllAutoMessages().then(() => {
      addAutoMessages(messages).then((result) => {
        showAlert("Messages are saved", "alert-success")
        console.log("Messages are saved");
        
        // Обновляем отображение количества автосообщений в новом элементе
        const autoMessagesElement = document.getElementById("autoMessagesCount");
        if (autoMessagesElement) {
          autoMessagesElement.innerText = messages.length;
        }

        // Обновляем отображение frequency
        const averageSendingPerMinute = document.getElementById("averageSendingPerMinute");
        if (averageSendingPerMinute) {
          averageSendingPerMinute.innerText = freqValue.toString();
        }

        setTimeout(function() { 
          const modal = bootstrap.Modal.getInstance(document.getElementById('editAutoMessageModal'));
          if (modal) {
            modal.hide();
          }
        }, 2);
      }).catch((error) => {
        console.error('Error adding messages:', error);
        setTimeout(function() { 
          const modal = bootstrap.Modal.getInstance(document.getElementById('editAutoMessageModal'));
          if (modal) {
            modal.hide();
          }
        }, 2);
      });
    }).catch((error) => {
      console.error('Error clearing messages:', error);
    });

  } else {
    showAlert("Are you trying to save an empty field", "alert-danger")
    console.log("Are you trying to save an empty field")
  }
}

export {intervalSendAutoMessageId, intervalTimerSendAutoMessageId, loadAutoMessagesData, isAutoSendingActive, startAutoMessageSending, stopAutoMessageSending}