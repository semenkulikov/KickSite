import {showAccounts, awaitAccounts, showNoAccounts} from "./kick-account";
import {showAlert} from "./alert";
import {workTimer, workTimerId} from "./kick-work";
import {countingSendingPerMinute, averageSendingPerMinuteId} from "./kick-send"
import {intervalSendAutoMessageId, intervalTimerSendAutoMessageId} from "./kick-auto-messages"

const loc = window.location;
let wsStart = 'ws://';

if (loc.protocol === 'https:') {
    wsStart = 'wss://'
}

let endpoint = wsStart + loc.host + '/ws-kick/chat';
const socket = new WebSocket(endpoint);
let awaitAccountsPingStatus;
let workStatus = false;

window.socket = socket;

function connect() {
  socket.onopen = function open() {
    console.log('WebSockets connection created.');
    socket.send(JSON.stringify({
      "event": "KICK_CONNECT",
      "message": "HELLO",
    }));
  };

  socket.onclose = function (e) {
    console.log('Socket is closed. Reconnect will be attempted in 1 second.', e.reason);
    setTimeout(function () {
      connect();
    }, 1000);
  };

  socket.onmessage = function (e) {
    // On getting the message from the server
    // Do the appropriate steps on each event.
    let data = JSON.parse(e.data);
    if (data.payload) data = data.payload;
    let message = data['message'];
    let event = data["event"];

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
      case 'KICK_LOAD_ACCOUNTS':
        showAccounts(message);
        awaitAccountsPingStatus = false;
        break;
      case 'KICK_AWAIT_ACCOUNTS':
        awaitAccountsPingStatus = true;
        awaitAccounts();
        break;
      case 'KICK_STOP_AWAIT_ACCOUNTS':
        awaitAccountsPingStatus = false;
        showNoAccounts();
        break;
      case 'KICK_SHOW_ERROR':
        showAlert(message, "alert-danger")
        break;
      case 'KICK_START_WORK':
        workStatus = true;
        countingSendingPerMinute(message);
        showAlert("You have started work", "alert-success")
        document.getElementById("buttonStartWork").disabled = true
        document.getElementById("buttonEndWork").disabled = false
        workTimer(message["startWorkTime"])
        break;
      case 'KICK_END_WORK':
        workStatus = false;
        showAlert("Have you finished your work", "alert-success")
        clearInterval(workTimerId);
        clearInterval(averageSendingPerMinuteId);
        
        // Stop auto messages if running
        if (intervalSendAutoMessageId) {
          clearInterval(intervalSendAutoMessageId);
        }
        if (intervalTimerSendAutoMessageId) {
          clearInterval(intervalTimerSendAutoMessageId);
        }
        
        // Reset buttons
        document.getElementById("buttonStartWork").disabled = false
        document.getElementById("buttonEndWork").disabled = true
        
        // Turn off auto message sending checkbox
        const autoMessageCheckbox = document.getElementById('sendAutoMessageStatus');
        if (autoMessageCheckbox.checked) {
          autoMessageCheckbox.checked = false;
        }
        
        // Reset UI elements
        document.getElementById("averageSendingPerMinute").innerText = "0.00"
        document.getElementById("timerAutoMessage").innerText = "00:01:00"
        document.getElementById("editAutoMessage").disabled = false;
        
        // Remove auto-send highlighting from accounts
        let accounts = document.getElementsByClassName('account');
        for (let account of accounts) {
          account.classList.remove("account-auto-send");
        }
        break;
      case 'KICK_CRITICAL_ERROR':
        showAlert(message, "alert-danger")
        break;
      default:
        console.log("No event")
    }
  };

  if (socket.readyState == WebSocket.OPEN) {
    socket.onopen(this);
  }
}

export {connect, socket, awaitAccountsPingStatus, workStatus}