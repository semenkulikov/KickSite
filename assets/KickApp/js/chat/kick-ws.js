console.log('kick-ws.js LOADED');
import {showAccounts, awaitAccounts, showNoAccounts} from "./kick-account";
import {showAlert} from "./alert";
import {workTimer, workTimerId, updateWorkButtonsState, updateChatButtonsState, showWorkNotification, hideWorkNotification} from "./kick-work";
import {countingSendingPerMinute, averageSendingPerMinuteId} from "./kick-send"
import {intervalSendAutoMessageId, intervalTimerSendAutoMessageId} from "./kick-auto-messages"

let _kickSocket = null;
let _kickSocketInitialized = false;
let awaitAccountsPingStatus = false;
let workStatus = false;

function getKickSocket() {
  if (_kickSocket) return _kickSocket;

const loc = window.location;
  let wsStart = loc.protocol === 'https:' ? 'wss://' : 'ws://';
let endpoint = wsStart + loc.host + '/ws-kick/chat';
const socket = new WebSocket(endpoint);

  // === DEBUG LOGGING ===
  console.log('[KICK-WS] init kick-ws.js');
  console.log('[KICK-WS] KICK_WS_URL =', endpoint);

  socket.onopen = function open() {
    console.log('[KICK-WS] WS OPEN');
    socket.send(JSON.stringify({
      "event": "KICK_CONNECT",
      "message": "HELLO",
    }));
  };

  socket.onclose = function (e) {
    console.warn('[KICK-WS] CLOSE', e);
    console.log('Socket is closed. Reconnect will be attempted in 1 second.', e.reason);
    setTimeout(function () {
      getKickSocket();
    }, 1000);
  };

  socket.onerror = function (e) {
    console.error('[KICK-WS] ERROR', e);
  };

  if (!_kickSocketInitialized) {
  socket.onmessage = function (e) {
      console.log('[KICK-WS] onmessage FIRED', e.data);
      const data = JSON.parse(e.data);
      let event = data["event"] || data["type"];
      let message = data['message'] || data['accounts'];
      console.log('[KICK-WS] event:', event, 'message:', message);
    switch (event) {
      case 'KICK':
        break;
      case 'KICK_CHANNEL_INFO':
        if (message) {
          console.log("KICK_CHANNEL_INFO", message);
          showAlert(`Channel loaded: ${message.username || message.slug || ''}`, "alert-success");
        } else if (data.error) {
          showAlert(`Channel error: ${data.error}`, "alert-danger");
        }
        break;
        case 'KICK_ACCOUNTS':
          import('./kick-account').then(mod => {
            let accountsList = Array.isArray(message) ? message : (message && message.accounts ? message.accounts : []);
            console.log('kick-account module:', mod);
            if (mod.showAccounts) mod.showAccounts(accountsList);
            else if (mod.default && mod.default.showAccounts) mod.default.showAccounts(accountsList);
            else console.error('showAccounts not found in kick-account module', mod);
            // Обновляем состояние кнопок после загрузки аккаунтов
            setTimeout(() => updateWorkButtonsState(), 100);
          });
          awaitAccountsPingStatus = false;
          break;
      case 'KICK_LOAD_ACCOUNTS':
          import('./kick-account').then(mod => {
            if (mod.showAccounts) mod.showAccounts(message);
            else if (mod.default && mod.default.showAccounts) mod.default.showAccounts(message);
            else console.error('showAccounts not found in kick-account module', mod);
          });
        awaitAccountsPingStatus = false;
        break;
      case 'KICK_AWAIT_ACCOUNTS':
        awaitAccountsPingStatus = true;
          import('./kick-account').then(mod => {
            if (mod.awaitAccounts) mod.awaitAccounts();
            else if (mod.default && mod.default.awaitAccounts) mod.default.awaitAccounts();
            else console.error('awaitAccounts not found in kick-account module', mod);
          });
        break;
      case 'KICK_STOP_AWAIT_ACCOUNTS':
        awaitAccountsPingStatus = false;
          import('./kick-account').then(mod => {
            if (mod.showNoAccounts) mod.showNoAccounts();
            else if (mod.default && mod.default.showNoAccounts) mod.default.showNoAccounts();
            else console.error('showNoAccounts not found in kick-account module', mod);
          });
        break;
      case 'KICK_SHOW_ERROR':
        showAlert(message, "alert-danger")
        break;
      case 'KICK_START_WORK':
        console.log('[KICK-WS] KICK_START_WORK received, setting workStatus = true');
        workStatus = true;
        countingSendingPerMinute(message);
        showAlert("You have started work", "alert-success")
        showWorkNotification(); // Показываем уведомление о запуске работы
        updateWorkButtonsState();
        updateChatButtonsState();
        workTimer(message["startWorkTime"])
        break;
      case 'KICK_END_WORK':
        workStatus = false;
        showAlert("Have you finished your work", "alert-success")
        hideWorkNotification(); // Скрываем уведомление о работе
        clearInterval(workTimerId);
        clearInterval(averageSendingPerMinuteId);
        // Stop auto messages if running
        if (intervalSendAutoMessageId) {
          clearInterval(intervalSendAutoMessageId);
        }
        if (intervalTimerSendAutoMessageId) {
          clearInterval(intervalTimerSendAutoMessageId);
        }
        // Turn off auto message sending checkbox
        const autoMessageCheckbox = document.getElementById('sendAutoMessageStatus');
        if (autoMessageCheckbox.checked) {
          autoMessageCheckbox.checked = false;
        }
        // Reset UI elements
        document.getElementById("averageSendingPerMinute").innerText = "0.00"
        document.getElementById("timerAutoMessage").innerText = "00:01:00"
        // Remove auto-send highlighting from accounts
        let accounts = document.getElementsByClassName('account');
        for (let account of accounts) {
          account.classList.remove("account-auto-send");
        }
        // Update button states
        updateWorkButtonsState();
        break;
      case 'KICK_CRITICAL_ERROR':
        showAlert(message, "alert-danger")
        break;
      default:
          console.log("No event", event, data);
    }
  };
    _kickSocketInitialized = true;
  }

  // selectedChannel observer
  function observeSelectedChannel(callback) {
    let value = window.selectedChannel;
    Object.defineProperty(window, 'selectedChannel', {
      get() { return value; },
      set(newValue) {
        value = newValue;
        callback(newValue);
      },
      configurable: true
    });
  }

  observeSelectedChannel(function(channel) {
    console.log('[KICK-WS] selectedChannel changed:', channel);
    if (socket.readyState === WebSocket.OPEN && channel) {
      socket.send(JSON.stringify({
        type: 'KICK_SELECT_CHANNEL',
        channel: channel
      }));
      console.log('[KICK-WS] Sent KICK_SELECT_CHANNEL:', channel);
    }
  });

  _kickSocket = socket;
  return socket;
}

export {getKickSocket, awaitAccountsPingStatus, workStatus};