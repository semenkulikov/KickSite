import {awaitAccountsPingStatus, getKickSocket, workStatus} from "./kick-ws";
import {showAlert} from "./alert";

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
    getKickSocket().send(JSON.stringify({
      "type": "KICK_END_WORK",
    "message": "End work",
  }));
    document.getElementById("buttonEndWork").disabled = true;
    updateWorkButtonsState();
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
  
  const activeAccounts = document.querySelectorAll('.account[data-account-status="active"]');
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
  
  const hasSelectedAccounts = document.querySelectorAll('[data-account-selected="true"]').length > 0;
  const canUseButtons = (window.workStatus || workStatus) && hasSelectedAccounts;
  
  console.log('[updateChatButtonsState] workStatus:', window.workStatus || workStatus, 'hasSelectedAccounts:', hasSelectedAccounts, 'canUseButtons:', canUseButtons);
  
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

// Делаем функцию доступной глобально для onclick
window.hideWorkNotification = hideWorkNotification;

export {workTimer, workTimerId, updateWorkButtonsState, updateChatButtonsState, showWorkNotification, hideWorkNotification};