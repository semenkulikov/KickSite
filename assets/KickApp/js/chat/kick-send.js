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
    const selectedAccounts = document.querySelectorAll('[data-account-selected="true"]');
    console.log(`[kickSend] Found ${selectedAccounts.length} selected accounts`);

    if(workStatus) {
      // Отправляем сообщения со всех выбранных аккаунтов
      selectedAccounts.forEach((accountElement, index) => {
        const accountLogin = accountElement.value;
        const messageData = {
          "channel": data.channel,
          "account": accountLogin,
          "message": data.message,
          "auto": false
        };
        
        console.log(`[kickSend] Sending message from account ${index + 1}/${selectedAccounts.length}: ${accountLogin}`);
        
        messagesSent++;
        addMessageToLogs(messageData);
        
        getKickSocket().send(JSON.stringify({
          "type": "KICK_SEND_MESSAGE",
          "message": messageData,
        }));
      });

      // Очищаем поле ввода только если элемент существует
      const inputMessageElement = document.getElementById('inputMessage');
      if (inputMessageElement) {
        inputMessageElement.value = "";
      }
    }
    else {
      showAlert("You haven't started work. Click on the \"Start work\" button", "alert-danger")
    }
  } else {
    console.log('[kickSend] checkingConditions returned false - some validation failed');
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
  console.log('[checkingConditions] Starting validation...');
  
  let inputMessage = checkInputMessage()
  let selectedChannel = checkSelectedChannel()
  let hasSelectedAccounts = checkSelectedAccount()
  
  let results = {
    inputMessage: inputMessage,
    selectedChannel: selectedChannel,
    selectedAccount: hasSelectedAccounts
  }
  
  console.log('[checkingConditions] Results:', results);
  
  if (inputMessage && selectedChannel && hasSelectedAccounts) {
    console.log('[checkingConditions] All validations passed');
    return {
      "channel": selectedChannel,
      "message": inputMessage,
    }
  }
  else {
    console.log('[checkingConditions] Some validation failed');
    return false
  }
}

function checkInputMessage(){
  console.log('[checkInputMessage] Checking input message...');
  const inputElement = document.getElementById('inputMessage');
  if (!inputElement) {
    console.error('[checkInputMessage] Input element not found');
    showAlert("Input message element not found!", "alert-danger")
    return false
  }
  
  const inputValue = inputElement.value;
  console.log('[checkInputMessage] Input value:', inputValue);
  if (inputValue && inputValue.trim() !== "") {
    return inputValue
  }
  showAlert("You are trying to send an empty message!", "alert-danger")
  return false
}

function checkSelectedChannel() {
  console.log('[checkSelectedChannel] Checking selected channel...');
  const elementSelectedChannel = document.getElementById("selectedChannel");
  if (!elementSelectedChannel) {
    console.error('[checkSelectedChannel] Selected channel element not found');
    showAlert("Selected channel element not found!", "alert-danger")
    return false
  }
  
  console.log('[checkSelectedChannel] Channel element dataset:', elementSelectedChannel.dataset);
  if (elementSelectedChannel.dataset.status === "selected") {
    const channelName = elementSelectedChannel.innerText;
    console.log('[checkSelectedChannel] Selected channel:', channelName);
    return channelName
  }
  showAlert("You have not selected a channel!", "alert-danger")
  return false
}

function checkSelectedAccount() {
  console.log('[checkSelectedAccount] Checking selected account...');
  
  const selectedAccounts = document.querySelectorAll('[data-account-selected="true"]');
  console.log(`[checkSelectedAccount] Found ${selectedAccounts.length} selected accounts`);
  
  if (selectedAccounts.length === 0) {
    showAlert("You haven't selected an account. Select an account.", "alert-danger");
    console.log('[checkSelectedAccount] No accounts selected');
    return false;
  }
  
  console.log(`[checkSelectedAccount] ${selectedAccounts.length} account(s) selected`);
  return true;
}

export {countingSendingPerMinute, averageSendingPerMinuteId}
