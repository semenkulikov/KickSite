// Speed Manager - управление скоростью сообщений на основе реальных ответов от Kick

let chatMessagesResponded = 0; // Счетчик ручных сообщений, на которые получен ответ
let chatResponseStartTime = null; // Время первого ответа на ручное сообщение
let autoMessagesResponded = 0; // Счетчик автосообщений, на которые получен ответ
let autoResponseStartTime = null; // Время первого ответа на автосообщение
let updateInterval = null; // Интервал для обновления статистики

// Функции для ручных сообщений
function recordChatMessageSent() {
  // Эта функция больше не используется для подсчета статистики
  // Статистика считается только по ответам от Kick
}

function recordChatMessageResponse() {
  // Эта функция вызывается при получении ответа от Kick (успех/ошибка)
  if (!chatResponseStartTime) {
    chatResponseStartTime = Date.now();
  }
  chatMessagesResponded++;
  updateChatSpeed();
}

// Функции для автосообщений
function recordAutoMessageSent() {
  // Эта функция больше не используется для подсчета статистики
  // Статистика считается только по ответам от Kick
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
  if (chatSpeedElement && chatResponseStartTime && chatMessagesResponded > 0) {
    const elapsedMinutes = (Date.now() - chatResponseStartTime) / 60000;
    const currentChatSpeed = chatMessagesResponded / elapsedMinutes;
    chatSpeedElement.innerText = currentChatSpeed.toFixed(2);
  } else if (chatSpeedElement) {
    chatSpeedElement.innerText = "0.00";
  }
}

function updateAutoSpeed() {
  const autoSpeedElement = document.getElementById("autoSpeed");
  if (autoSpeedElement && autoResponseStartTime && autoMessagesResponded > 0) {
    const elapsedMinutes = (Date.now() - autoResponseStartTime) / 60000;
    const currentAutoSpeed = autoMessagesResponded / elapsedMinutes;
    autoSpeedElement.innerText = currentAutoSpeed.toFixed(2);
  } else if (autoSpeedElement) {
    autoSpeedElement.innerText = "0.00";
  }
}

// Запуск интервала обновления статистики
function startSpeedUpdateInterval() {
  if (updateInterval) {
    clearInterval(updateInterval);
  }
  updateInterval = setInterval(() => {
    updateChatSpeed();
    updateAutoSpeed();
  }, 1000); // Обновляем каждую секунду
}

// Остановка интервала обновления статистики
function stopSpeedUpdateInterval() {
  if (updateInterval) {
    clearInterval(updateInterval);
    updateInterval = null;
  }
}

// Сброс счетчиков
function resetChatSpeed() {
  chatMessagesResponded = 0;
  chatResponseStartTime = null;
  updateChatSpeed();
}

function resetAutoSpeed() {
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
  updateAutoSpeed,
  startSpeedUpdateInterval,
  stopSpeedUpdateInterval,

};

// Делаем функции доступными глобально
window.resetChatSpeed = resetChatSpeed;
window.resetAutoSpeed = resetAutoSpeed;
window.startSpeedUpdateInterval = startSpeedUpdateInterval;
window.stopSpeedUpdateInterval = stopSpeedUpdateInterval;
 