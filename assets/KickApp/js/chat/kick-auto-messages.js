import {getFrequency, addOrUpdateFrequencyDB} from "./kick-frequency-db";
import {getAutoMessages, addAutoMessages, clearAllAutoMessages, openAutoMessagesDB} from "./kick-auto-messages-db";
import {addMessageToLogs} from "./kick-input-logs";
import {getKickSocket, workStatus} from "./kick-ws";
import {showAlert} from "./alert";

let intervalSendAutoMessageId;
let intervalTimerSendAutoMessageId;
let isAutoSendingActive = false; // Глобальная переменная для отслеживания состояния авторассылки

if (document.getElementById("editAutoMessage")) {
document.getElementById("editAutoMessage").addEventListener("click", function () {
  console.log("Load auto-messages and frequency from DB if exists");
  document.getElementById("autoMessageTextArea").value = '';
  loadAutoMessagesData();
});
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
document.getElementById('sendAutoMessageStatus').addEventListener('click', function () {
  const checkbox = document.getElementById('sendAutoMessageStatus');

  if (window.workStatus) {
    if (checkbox.checked) {
      let elementSelectedChannel = document.getElementById("selectedChannel");

      if (elementSelectedChannel.dataset.status === "selected") {
        let channel = elementSelectedChannel.innerText;

        let accounts = document.getElementsByClassName("account__checkbox");

        if (accounts.length) {
          // Загружаем сообщения из базы данных
          getAutoMessages().then((messages) => {
            if (messages && messages.length) {
              // Получаем частоту из базы данных
              getFrequency().then((frequency) => {
                let freq = frequency ? frequency.value : 1;
                
                // Принудительно обновляем отображение Messages/minutes
                const averageSendingPerMinute = document.getElementById("averageSendingPerMinute");
                if (averageSendingPerMinute) {
                  averageSendingPerMinute.innerText = freq;
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

                const dateOptions = {
                  year: '2-digit', month: '2-digit', day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                  timeZone: "UTC"
                };

                let intervalMs = Math.floor(60000 / freq); // Calculate interval in milliseconds
                let timer = intervalMs;

                console.log(`Starting auto-send with frequency: ${freq} messages/min, interval: ${intervalMs}ms`);

                intervalSendAutoMessageId = setInterval(function () {
                  // Получаем только выбранные аккаунты
                  const selectedAccounts = document.querySelectorAll('.account__checkbox:checked');
                  
                  if (selectedAccounts.length > 0 && messages && messages.length > 0) {
                    // Выбираем случайный выбранный аккаунт
                    const randomIndex = Math.floor(Math.random() * selectedAccounts.length);
                    const selectedAccount = selectedAccounts[randomIndex];
                    
                    if (selectedAccount && selectedAccount.value) {
                      let accountLogin = selectedAccount.value;
                      // Выбираем случайное сообщение из массива
                      let randomMessage = messages[Math.floor(Math.random() * messages.length)];
                      let data = {
                          "channel": channel,
                          "account": accountLogin,
                          "message": randomMessage,
                          "auto": true
                      }
                      // Возвращаем логи в глобальные
                      addMessageToLogs(data);
                      getKickSocket().send(JSON.stringify({
                          "type": "KICK_SEND_MESSAGE",
                          "message": data,
                      }));
                    }
                  }
                  
                  // Сбрасываем таймер на полный интервал
                  timer = intervalMs;
                }, intervalMs); // Use dynamic interval

                intervalTimerSendAutoMessageId = setInterval(function () {
                  const timerElement = document.getElementById("timerAutoMessage");
                  if (timerElement) {
                    // Показываем обратный отсчет в формате MM:SS
                    const minutes = Math.floor(timer / 60000);
                    const seconds = Math.floor((timer % 60000) / 1000);
                    timerElement.innerText = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                  }
                  timer -= 1000;
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
    }
  } else {
    $("#sendAutoMessageStatus").prop('checked', false);
    showAlert("You haven't started work. Click on the \"Start work\" button", "alert-danger")
  }
});
}

function loadAutoMessagesData() {
  console.log('Loading auto messages data...');
  
  getFrequency().then((frequency) => {
    console.log('Frequency loaded:', frequency);
    if (frequency && frequency.value) {
      changeViewFrequency(frequency.value);
      // Обновляем отображение Messages/minutes при загрузке
      const averageSendingPerMinute = document.getElementById("averageSendingPerMinute");
      if (averageSendingPerMinute) {
        averageSendingPerMinute.innerText = frequency.value;
        console.log('Set averageSendingPerMinute to:', frequency.value);
      }
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
    }
  }).catch((error) => {
    console.error('Error loading messages:', error);
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
  const freqInput = document.getElementById("autoMessageFrequencyInput");
  const freqSend = document.getElementById("frequency-send");
  if (freqInput) freqInput.value = frequency;
  if (freqSend) freqSend.value = frequency;
}

function changeViewAutoMessages(messages) {
  const autoMessageTextArea = document.getElementById("autoMessageTextArea");
  if (autoMessageTextArea) {
    // Очищаем textarea перед добавлением сообщений
    autoMessageTextArea.value = '';
    messages.forEach((message) => {
      autoMessageTextArea.value = autoMessageTextArea.value + message + "\n"
    });
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
    addOrUpdateFrequencyDB(frequencySend.value);

    // Сначала очищаем старые сообщения, потом добавляем новые
    clearAllAutoMessages().then(() => {
      addAutoMessages(messages).then((result) => {
        showAlert("Messages are saved", "alert-success")
        console.log("Messages are saved");
        
        // Обновляем отображение Messages/minutes
        const averageSendingPerMinute = document.getElementById("averageSendingPerMinute");
        if (averageSendingPerMinute) {
          averageSendingPerMinute.innerText = frequencySend.value;
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

export {intervalSendAutoMessageId, intervalTimerSendAutoMessageId, loadAutoMessagesData, isAutoSendingActive}