import {getFrequency, addOrUpdateFrequencyDB} from "./twitch-frequency-db";
import {getAutoMessages, clearAllAutoMessages, addAutoMessages} from "./twitch-auto-messages-db";
import {addMessageToLogs} from "./twitch-input-logs";
import {socket, workStatus} from "./twitch-ws";
import {showAlert} from "./alert";

let intervalSendAutoMessageId;
let intervalTimerSendAutoMessageId;

document.getElementById("editAutoMessage").addEventListener("click", function () {
  console.log("Load auto-messages and frequency from DB if exists");
  document.getElementById("autoMessageTextArea").value = '';
  loadAutoMessagesData();
});

document.getElementById("saveAutoMessages").addEventListener("click", function () {
  console.log("Click save auto messages");
  saveAutoMessages()
});

document.getElementById('sendAutoMessageStatus').addEventListener('click', function () {
  const checkbox = document.getElementById('sendAutoMessageStatus');

  if (workStatus) {
    if (checkbox.checked) {
      let autoMessageTextArea = document.getElementById("autoMessageTextArea");

      let messages = autoMessageTextArea.value.split("\n").map((element) => element.trim()).filter((element) => element !== "");
      let elementSelectedChannel = document.getElementById("selectedChannel");

      if (elementSelectedChannel.dataset.status === "selected") {
        let channel = elementSelectedChannel.innerText;

        let accounts = document.getElementsByClassName("account__checkbox");

        if (accounts.length) {
          if (messages.length) {
            document.getElementById("editAutoMessage").disabled = true;
            let frequency = parseInt(document.getElementById('frequency-send').innerText);
            console.log("Click start new")

            const dateOptions = {
              year: '2-digit', month: '2-digit', day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              timeZone: "UTC"
            };

            let intervalMs = 60000 / frequency; // Calculate interval
            let timer = intervalMs;

            intervalSendAutoMessageId = setInterval(function () {
              const shuffled = [...accounts].sort(() => 0.5 - Math.random());
              // Select only ONE random account
              const selectedAccounts = shuffled.slice(0, 1);

              $.each(selectedAccounts, function (index, value) {
                let accountLogin = value.value
                let data = {
                    "channel": channel,
                    "account": accountLogin,
                    "message": messages[~~(Math.random() * messages.length)],
                    "auto": true
                }
                addMessageToLogs(data);
                socket.send(JSON.stringify({
                    "event": "TWITCH_SEND_MESSAGE",
                    "message": data,
                }));
              });
              selectAutoSendAccounts(selectedAccounts)
              timer = intervalMs; // Reset timer to new interval
            }, intervalMs); // Use dynamic interval

            intervalTimerSendAutoMessageId = setInterval(function () {
              let currentTimer = new Date(timer).toLocaleString('ru-RU', dateOptions)
              document.getElementById("timerAutoMessage").innerText = currentTimer.substr(9, )
              timer -= 1000;
            }, 1000)

          } else {
            $("#sendAutoMessageStatus").prop('checked', false);
            console.log("You don't have any messages to send automatically")
            showAlert("You don't have any messages to send automatically", "alert-danger")
          }
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
      document.getElementById("editAutoMessage").disabled = false;
      console.log("Click stop new")
      clearInterval(intervalSendAutoMessageId);
      clearInterval(intervalTimerSendAutoMessageId);
    }
  } else {
    $("#sendAutoMessageStatus").prop('checked', false);
    showAlert("You haven't started work. Click on the \"Start work\" button", "alert-danger")
  }
});

function loadAutoMessagesData() {
  getFrequency().then((frequency) => {
    if (frequency) {
      changeViewFrequency(frequency.value);
    }
  }).catch((error) => {
    console.error('Error:', error);
  });

  getAutoMessages().then((messages) => {
    changeViewAutoMessages(messages);
  }).catch((error) => {
    console.error('Error:', error);
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
  document.getElementById("autoMessageFrequencyInput").value = frequency
  document.getElementById("frequency-send").innerText = frequency
}

function changeViewAutoMessages(messages) {
  const autoMessageTextArea = document.getElementById("autoMessageTextArea");
  messages.forEach((message) => {
    autoMessageTextArea.value = autoMessageTextArea.value + message + "\n"
  });
}

function saveAutoMessages() {
  const autoMessageTextArea = document.getElementById("autoMessageTextArea");
  const frequencySend = document.getElementById("frequency-send");

  let messages = autoMessageTextArea.value.split("\n").map((element) => element.trim()).filter((element) => element !== "");
  if (messages.length) {
    addOrUpdateFrequencyDB(frequencySend.innerText);

    clearAllAutoMessages().then((result) => {
      // console.log(result);
    }).catch((error) => {
      console.error('Error:', error);
    });

    addAutoMessages(messages).then((result) => {
      showAlert("Messages are saved", "alert-success")
      console.log("Messages are saved");

      setTimeout(function() { $('#editAutoMessageModal').modal('hide'); }, 2);
    }).catch((error) => {
      console.error('Error:', error);
      setTimeout(function() { $('#editAutoMessageModal').modal('hide'); }, 2);
    });

  } else {
    showAlert("Are you trying to save an empty field", "alert-danger")
    console.log("Are you trying to save an empty field")
  }
}

export {intervalSendAutoMessageId, intervalTimerSendAutoMessageId, loadAutoMessagesData}