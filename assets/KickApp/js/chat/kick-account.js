import {socket, awaitAccountsPingStatus} from "./kick-ws";
import {showAlert} from "./alert";

const kickAccounts = document.getElementsByClassName('account__checkbox');

function showAccounts(data) {
    const accountsContainer = document.getElementById("accounts");
    document.getElementById("buttonStartWork").disabled = false

    accountsContainer.innerHTML = "";

    $.each(data, function (index, value) {
        let account = document.createElement("div");
        account.className = "col col-md-3 gy-1 py-1 control account text-center";

        let label = document.createElement("label");
        label.className = "checkbox";

        const input = document.createElement("input");
        input.type = "checkbox";
        input.className = "account__checkbox";
        input.id = `account-${index}`;
        input.value = index;

        const text = document.createTextNode(index);
        label.appendChild(input);
        label.appendChild(text);

        account.appendChild(label);

        account.appendChild(document.createElement("br"));

        let badgeStatus = document.createElement("span");
        badgeStatus.className = `badge ${value ? "bg-success" : "bg-danger"} rounded-pill`;
        badgeStatus.innerText = "S";
        account.appendChild(badgeStatus);

        account.addEventListener("click", function (e) {
            selectAccount(input.id);
        })

        accountsContainer.appendChild(account);

    })
}

function awaitAccounts() {
  console.log("AWAIT ACCOUNTS")
  setInterval(function () {
    if (awaitAccountsPingStatus) {
      socket.send(JSON.stringify({
        "event": "KICK_AWAIT_ACCOUNTS",
        "message": "PING",
      }));
    }
  }, 1000);
}

function selectAccount(id) {
    for (let i = 0; i < kickAccounts.length; i++) {
        if (kickAccounts[i].id === id) {
            kickAccounts[i].setAttribute("data-account-selected", "true")
            kickAccounts[i].parentNode.parentNode.classList.add("account-checked");
        } else {
            kickAccounts[i].setAttribute("data-account-selected", "false")
            kickAccounts[i].parentNode.parentNode.classList.remove("account-checked");
        }
    }
}

function showNoAccounts(){
  const accountsContainer = document.getElementById("accounts");

  accountsContainer.innerHTML = "";
  let message = document.createElement("p");
  message.className = "w-50 text-center alert alert-warning";
  message.innerText = "You don't have any assigned accounts. Contact the administrator"
  accountsContainer.appendChild(message)
}

export {showAccounts, selectAccount, showNoAccounts, awaitAccounts}