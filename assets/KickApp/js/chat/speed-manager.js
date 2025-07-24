// Speed Manager - управление скоростью сообщений на основе реальных ответов от Kick

let chatMessagesSent = 0; // Счетчик отправленных ручных сообщений
let chatStartTime = null; // Время начала чата
let autoMessagesSent = 0; // Счетчик отправленных автосообщений
let autoMessageStartTime = null; // Время начала авторассылки
let autoMessagesResponded = 0; // Счетчик автосообщений, на которые получен ответ
let autoResponseStartTime = null; // Время первого ответа на автосообщение

// Функции для ручных сообщений
function recordChatMessageSent() {
  if (!chatStartTime) {
    chatStartTime = Date.now();
  }
  chatMessagesSent++;
  updateChatSpeed();
}

function recordChatMessageResponse() {
  // Эта функция вызывается при получении ответа от Kick (успех/ошибка)
  updateChatSpeed();
}

// Функции для автосообщений
function recordAutoMessageSent() {
  if (!autoMessageStartTime) {
    autoMessageStartTime = Date.now();
  }
  autoMessagesSent++;
  updateAutoSpeed();
}

function recordAutoMessageResponse() {
  // Эта функция вызывается при получении ответа от Kick (успех/ошибка)
  if (!autoResponseStartTime) {
    autoResponseStartTime = Date.now();
  }
  autoMessagesResponded++;
  updateAutoSpeed();
}

// Обновление отображения скорости
function updateChatSpeed() {
  const chatSpeedElement = document.getElementById("chatSpeed");
  if (chatSpeedElement && chatStartTime && chatMessagesSent > 0) {
    const elapsedMinutes = (Date.now() - chatStartTime) / 60000;
    const currentChatSpeed = chatMessagesSent / elapsedMinutes;
    chatSpeedElement.innerText = currentChatSpeed.toFixed(2);
  } else if (chatSpeedElement) {
    chatSpeedElement.innerText = "0.00";
  }
}

function updateAutoSpeed() {
  const autoSpeedElement = document.getElementById("autoSpeed");
  if (autoSpeedElement && autoResponseStartTime && autoMessagesResponded > 0) {
    // Используем время первого ответа и количество ответов для расчета скорости
    const elapsedMinutes = (Date.now() - autoResponseStartTime) / 60000;
    const currentAutoSpeed = autoMessagesResponded / elapsedMinutes;
    autoSpeedElement.innerText = currentAutoSpeed.toFixed(2);
  } else if (autoSpeedElement && autoMessageStartTime && autoMessagesSent > 0) {
    // Если еще нет ответов, показываем скорость на основе отправленных
    const elapsedMinutes = (Date.now() - autoMessageStartTime) / 60000;
    const currentAutoSpeed = autoMessagesSent / elapsedMinutes;
    autoSpeedElement.innerText = currentAutoSpeed.toFixed(2);
  } else if (autoSpeedElement) {
    autoSpeedElement.innerText = "0.00";
  }
}

// Сброс счетчиков
function resetChatSpeed() {
  chatMessagesSent = 0;
  chatStartTime = null;
  updateChatSpeed();
}

function resetAutoSpeed() {
  autoMessagesSent = 0;
  autoMessageStartTime = null;
  autoMessagesResponded = 0;
  autoResponseStartTime = null;
  updateAutoSpeed();
}

// Экспорт функций
export {
  recordChatMessageSent,
  recordChatMessageResponse,
  recordAutoMessageSent,
  recordAutoMessageResponse,
  resetChatSpeed,
  resetAutoSpeed,
  updateChatSpeed,
  updateAutoSpeed
};

// Делаем функции доступными глобально
window.resetChatSpeed = resetChatSpeed;
window.resetAutoSpeed = resetAutoSpeed; 