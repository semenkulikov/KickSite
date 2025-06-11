import {showAccounts, awaitAccounts, showNoAccounts} from "./twitch-account";
import {showAlert} from "./alert";
import {workTimer, workTimerId} from "./twitch-work";
import {countingSendingPerMinute, averageSendingPerMinuteId} from "./twitch-send"
import {intervalSendAutoMessageId, intervalTimerSendAutoMessageId} from "./twitch-auto-messages"

const loc = window.location;
let wsStart = 'ws://';

if (loc.protocol === 'https:') {
    wsStart = 'wss://'
}

let endpoint = wsStart + loc.host + '/ws-twitch/chat';
const socket = new WebSocket(endpoint);
let awaitAccountsPingStatus;
let workStatus = false;

function connect() {
  socket.onopen = function open() {
    console.log('WebSockets connection created.');
    socket.send(JSON.stringify({
      "event": "TWITCH_CONNECT",
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
    data = data["payload"];
    let message = data['message'];
    let event = data["event"];

    switch (event) {
      case 'TWITCH':
        break;
      case 'TWITCH_LOAD_ACCOUNTS':
        showAccounts(message);
        awaitAccountsPingStatus = false;
        break;
      case 'TWITCH_AWAIT_ACCOUNTS':
        awaitAccountsPingStatus = true;
        awaitAccounts();
        break;
      case 'TWITCH_STOP_AWAIT_ACCOUNTS':
        awaitAccountsPingStatus = false;
        showNoAccounts();
        break;
      case 'TWITCH_SHOW_ERROR':
        showAlert(message, "alert-danger")
        break;
      case 'TWITCH_START_WORK':
        workStatus = true;
        countingSendingPerMinute(message);
        showAlert("You have started work", "alert-success")
        document.getElementById("buttonStartWork").disabled = true
        document.getElementById("buttonEndWork").disabled = false
        workTimer(message["startWorkTime"])
        break;
      case 'TWITCH_END_WORK':
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
      case 'TWITCH_CRITICAL_ERROR':
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