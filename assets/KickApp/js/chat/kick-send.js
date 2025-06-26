import {showAlert} from "./alert";
import {addMessageToLogs} from "./kick-input-logs";
import {selectAccount} from "./kick-account";
import {getKickSocket, workStatus} from "./kick-ws";

let averageSendingPerMinuteId;

$('#sendInputMessage').on("click", () => {
  kickSend();
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

    kickSend();
  }
});

function kickSend() {
  let data = checkingConditions()
  if (data) {
    const inputMessageElement = document.getElementById('inputMessage');
    const selectedAccount = document.querySelectorAll('[data-account-selected="true"]')[0];

    if(workStatus) {
      messagesSent++;
      addMessageToLogs(data)
      getKickSocket().send(JSON.stringify({
        "event": "KICK_SEND_MESSAGE",
        "message": data,
      }));

      let currentAccount = document.querySelector(`[id=${selectedAccount.id}]`);
      let currentIndex = ([...document.querySelectorAll('[data-account-selected="true"]')].indexOf(currentAccount) + 1) % document.querySelectorAll('[data-account-selected="true"]').length;
      selectAccount(document.querySelectorAll('[data-account-selected="true"]')[currentIndex].id);
      inputMessageElement.value = "";
    }
    else {
      showAlert("You haven't started work. Click on the \"Start work\" button", "alert-danger")
    }
  }
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
    document.getElementById("averageSendingPerMinute").innerText = messagesPerMinute
    // console.log(`Messages/minute: ${messagesPerMinute}`)
  }, 5000)
}

function checkingConditions() {
  let inputMessage = checkInputMessage()
  let selectedChannel = checkSelectedChannel()
  let selectedAccount = checkSelectedAccount()

  if (selectedChannel && inputMessage && selectedAccount) return {
    "channel": selectedChannel,
    "account": selectedAccount,
    "message": inputMessage,
    "auto": false
  }
  return false
}

function checkInputMessage(){
  const inputValue = document.getElementById('inputMessage').value;
  if (inputValue && inputValue.trim() !== "") {
    return inputValue
  }
  showAlert("You are trying to send an empty message!", "alert-danger")
  return false
}

function checkSelectedChannel() {
  const elementSelectedChannel = document.getElementById("selectedChannel");
  if (elementSelectedChannel.dataset.status === "selected") {
    return elementSelectedChannel.innerText
  }
  showAlert("You have not selected a channel!", "alert-danger")
  return false
}

function checkSelectedAccount() {
  const selectedAccount = document.querySelectorAll('[data-account-selected="true"]')[0];
  if (selectedAccount) {
    return selectedAccount.value;
  }
  showAlert("You have not selected any account!", "alert-danger")
  return false
}

export {countingSendingPerMinute, averageSendingPerMinuteId}
