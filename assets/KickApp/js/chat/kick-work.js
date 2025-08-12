import {awaitAccountsPingStatus, getKickSocket, workStatus} from "./kick-ws";
import {showAlert, clearAllAlerts} from "./alert";
import {startSpeedUpdateInterval, stopSpeedUpdateInterval} from "./speed-manager";

let workTimerId;

const startWorkBtn = document.getElementById("buttonStartWork");
if (startWorkBtn) {
  startWorkBtn.classList.add('btn', 'btn-success', 'mb-2', 'w-100');
  startWorkBtn.disabled = true;
  startWorkBtn.addEventListener("click", function () {
  console.log("Start work");
    // Показываем алерт сразу при нажатии
    showAlert("You have started work", "alert-success");
    
    // Устанавливаем workStatus = true сразу
    window.workStatus = true;
    updateWorkButtonsState();
    updateChatButtonsState();
    
    // Показываем уведомление о работе сразу
    showWorkNotification();
    
    // Запускаем интервал обновления статистики
    startSpeedUpdateInterval();
    
    // Логируем текущую частоту при старте работы
    const freqSend = document.getElementById("frequency-send");
    if (freqSend && freqSend.value) {
      const freqValue = parseInt(freqSend.value) || 1;
      getKickSocket().send(JSON.stringify({
        type: 'KICK_LOG_ACTION',
        action_type: 'settings_change',
        description: `Frequency set at work start: ${freqValue} messages/min`,
        details: {
          action: 'frequency_loaded',
          frequency: freqValue
        }
      }));
    }
    
    getKickSocket().send(JSON.stringify({
      "type": "KICK_START_WORK",
    "message": "Start work",
  }));
});
}

const endWorkBtn = document.getElementById("buttonEndWork");
if (endWorkBtn) {
  endWorkBtn.classList.add('btn', 'btn-danger', 'mb-2', 'w-100');
  endWorkBtn.disabled = true;
  endWorkBtn.addEventListener("click", function () {
  console.log("End work");
    
    // Очищаем все существующие алерты
    clearAllAlerts();
    
    // Показываем один алерт о завершении работы
    setTimeout(() => {
      showAlert("✅ Work completed successfully", "alert-success", true, 5000);
    }, 100);
    
    // Останавливаем интервал обновления статистики
    stopSpeedUpdateInterval();
    
    // Останавливаем автоматическую рассылку
    const autoMessageCheckbox = document.getElementById('sendAutoMessageStatus');
    if (autoMessageCheckbox && autoMessageCheckbox.checked) {
      autoMessageCheckbox.checked = false;
      autoMessageCheckbox.click(); // Это вызовет обработчик события и остановит рассылку
    }
    
    // Сбрасываем AccountManager при остановке работы
    if (window.accountManager) {
      window.accountManager.reset();
    }
    
    // Сбрасываем все галочки в дефолтное положение
    resetAllCheckboxes();
    
    // Останавливаем авторассылку принудительно
    try {
      if (window.stopOptimizedAutoMessageSending) {
        window.stopOptimizedAutoMessageSending();
      }
      if (window.stopAutoMessageSending) {
        window.stopAutoMessageSending();
      }
    } catch (e) {
      console.error('[END_WORK] Error stopping auto messages:', e);
    }
    
    // Отправляем сообщение на сервер
    getKickSocket().send(JSON.stringify({
      "type": "KICK_END_WORK",
      "message": "End work",
    }));
    
    // Сбрасываем workStatus
    window.workStatus = false;
    
    // Обновляем состояние кнопок
    updateWorkButtonsState();
    
    // Скрываем уведомление о работе
    hideWorkNotification();
});
}

function workTimer(startTime) {
  const dateOptions = {
          year: '2-digit', month: '2-digit', day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          timeZone: "UTC"
        };
  let start = new Date(startTime);

  workTimerId = setInterval(function () {
    if (window.workStatus || workStatus) {
      let nowTime = new Date();
      let timeDiff = new Date(Math.abs(nowTime - start));
      document.getElementById("workTimer").innerHTML = timeDiff.toLocaleDateString('ru-RU', dateOptions).substr(10, );
    }
  }, 1000);
}

function updateWorkButtonsState() {
  const startWorkBtn = document.getElementById("buttonStartWork");
  const endWorkBtn = document.getElementById("buttonEndWork");
  
  // Проверяем только активные аккаунты (независимо от выбора)
  const activeAccounts = document.querySelectorAll('.account-block[data-account-status="active"]');
  const hasActiveAccounts = activeAccounts.length > 0;
  const currentWorkStatus = window.workStatus || workStatus;
  
  if (currentWorkStatus) {
    if (startWorkBtn) startWorkBtn.disabled = true;
    if (endWorkBtn) endWorkBtn.disabled = false;
  } else {
    if (startWorkBtn) startWorkBtn.disabled = !hasActiveAccounts;
    if (endWorkBtn) endWorkBtn.disabled = true;
  }
  
  updateChatButtonsState();
}

function updateChatButtonsState() {
  const chatBtn = document.getElementById("sendInputMessage");
  const autoMessagesBtn = document.querySelector('[data-bs-target="#editAutoMessageModal"]');
  const autoMessageCheckbox = document.getElementById('sendAutoMessageStatus');
  
  // Проверяем только активные выбранные аккаунты (видимые)
  const selectedAccounts = document.querySelectorAll('.account-block[data-account-selected="true"]');
  const activeSelectedAccounts = Array.from(selectedAccounts).filter(accountBlock => {
    const status = accountBlock.getAttribute('data-account-status');
    const isVisible = accountBlock.style.display !== 'none';
    return status === 'active' && isVisible;
  });
  
  // Проверяем только видимые активные аккаунты
  const visibleActiveAccounts = document.querySelectorAll('.account-block[data-account-status="active"]');
  const hasVisibleActiveAccounts = Array.from(visibleActiveAccounts).some(block => 
    block.style.display !== 'none'
  );
  
  const hasSelectedAccounts = activeSelectedAccounts.length > 0;
  const autoSwitchEnabled = window.accountManager && window.accountManager.autoSwitchEnabled;
  
  // Кнопки активны только если работа начата И есть выбранные аккаунты
  const workStarted = window.workStatus || workStatus;
  const canUseButtons = workStarted && (autoSwitchEnabled ? hasVisibleActiveAccounts : hasSelectedAccounts);
  
  console.log('[updateChatButtonsState] workStatus:', window.workStatus || workStatus, 'hasSelectedAccounts:', hasSelectedAccounts, 'hasVisibleActiveAccounts:', hasVisibleActiveAccounts, 'autoSwitchEnabled:', autoSwitchEnabled, 'canUseButtons:', canUseButtons);
  
  if (chatBtn) chatBtn.disabled = !canUseButtons;
  if (autoMessagesBtn) autoMessagesBtn.disabled = !canUseButtons;
  if (autoMessageCheckbox) autoMessageCheckbox.disabled = !canUseButtons;
}

// Функции для управления уведомлением о работе
function showWorkNotification() {
  const notification = document.getElementById('workStatusNotification');
  if (notification) {
    notification.style.display = 'block';
    notification.classList.add('show');
    startWorkTimeCounter();
  }
}

function hideWorkNotification() {
  const notification = document.getElementById('workStatusNotification');
  if (notification) {
    notification.style.display = 'none';
    notification.classList.remove('show');
    stopWorkTimeCounter();
  }
}

// Счетчик времени работы в уведомлении
let workTimeCounterInterval = null;
let workStartTime = null;

function startWorkTimeCounter() {
  workStartTime = new Date();
  workTimeCounterInterval = setInterval(() => {
    const now = new Date();
    const diff = Math.floor((now - workStartTime) / 1000);
    const hours = Math.floor(diff / 3600).toString().padStart(2, '0');
    const minutes = Math.floor((diff % 3600) / 60).toString().padStart(2, '0');
    const seconds = (diff % 60).toString().padStart(2, '0');
    
    const counter = document.getElementById('workTimeCounter');
    if (counter) {
      counter.textContent = `${hours}:${minutes}:${seconds}`;
    }
  }, 1000);
}

function stopWorkTimeCounter() {
  if (workTimeCounterInterval) {
    clearInterval(workTimeCounterInterval);
    workTimeCounterInterval = null;
  }
  const counter = document.getElementById('workTimeCounter');
  if (counter) {
    counter.textContent = '00:00:00';
  }
}

// Функция для сброса всех галочек в дефолтное положение
function resetAllCheckboxes() {
  // Сбрасываем галочку автоматической рассылки
  const autoMessageCheckbox = document.getElementById('sendAutoMessageStatus');
  if (autoMessageCheckbox) {
    autoMessageCheckbox.checked = false;
  }
  
  // Сбрасываем галочку авто-переключения аккаунтов
  const autoSwitchCheckbox = document.getElementById('autoSwitchAccounts');
  if (autoSwitchCheckbox) {
    autoSwitchCheckbox.checked = false;
  }
  
  // Сбрасываем галочку случайного режима
  const randomModeCheckbox = document.getElementById('randomMode');
  if (randomModeCheckbox) {
    randomModeCheckbox.checked = false;
  }
  
  // Снимаем выделение со всех аккаунтов
  const accountCheckboxes = document.querySelectorAll('.account__checkbox');
  accountCheckboxes.forEach(checkbox => {
    checkbox.checked = false;
    checkbox.setAttribute('data-account-selected', 'false');
    checkbox.parentNode.classList.remove('account-checked');
  });
  
  // Очищаем поле ввода сообщения
  const inputMessage = document.getElementById('inputMessage');
  if (inputMessage) {
    inputMessage.value = '';
  }
  
  // Сбрасываем счетчик сообщений в минуту
  const averageSendingPerMinute = document.getElementById("averageSendingPerMinute");
  if (averageSendingPerMinute) {
    averageSendingPerMinute.innerText = "0";
  }
  
  // Сбрасываем счетчик автосообщений
  const autoMessagesCount = document.getElementById("autoMessagesCount");
  if (autoMessagesCount) {
    autoMessagesCount.innerText = "0";
  }
  
  // Сбрасываем счетчики скорости
  const chatSpeed = document.getElementById("chatSpeed");
  if (chatSpeed) {
    chatSpeed.innerText = "0.00";
  }
  
  const autoSpeed = document.getElementById("autoSpeed");
  if (autoSpeed) {
    autoSpeed.innerText = "0.00";
  }
  
  // Сбрасываем таймер работы
  const workTimer = document.getElementById("workTimer");
  if (workTimer) {
    workTimer.innerHTML = "00:00:00";
  }
  
  // Сбрасываем таймер автоматических сообщений
  const timerAutoMessage = document.getElementById("timerAutoMessage");
  if (timerAutoMessage) {
    timerAutoMessage.innerText = "00:00";
  }
}

// Делаем функцию доступной глобально для onclick
window.hideWorkNotification = hideWorkNotification;
window.updateChatButtonsState = updateChatButtonsState;

export {workTimer, workTimerId, updateWorkButtonsState, updateChatButtonsState, showWorkNotification, hideWorkNotification, resetAllCheckboxes};