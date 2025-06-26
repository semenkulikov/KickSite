import {getKickSocket, awaitAccountsPingStatus} from "./kick-ws";
import {showAlert} from "./alert";

const kickAccounts = document.getElementsByClassName('account__checkbox');

function showAccounts(accounts) {
    console.log('[showAccounts] called with', accounts);
    const accountsContainer = document.getElementById("accounts");
    document.getElementById("buttonStartWork").disabled = false;
    accountsContainer.innerHTML = "";

    if (!accounts.length) return;

    accounts.forEach((acc, idx) => {
        let block = document.createElement("div");
        block.className = "account-block d-flex align-items-center gap-2 mb-2 p-2 rounded bg-dark";

        // Аватар-заглушка (можно заменить на реальный)
        let avatar = document.createElement("div");
        avatar.className = "account-avatar me-2";
        avatar.style = "width:32px;height:32px;border-radius:50%;background:#23232a;display:flex;align-items:center;justify-content:center;font-weight:bold;color:#fff;";
        avatar.innerText = acc.login[0]?.toUpperCase() || "?";
        block.appendChild(avatar);

        // Логин
        let login = document.createElement("span");
        login.className = "account-login fw-bold";
        login.innerText = acc.login;
        block.appendChild(login);

        // Статус
        let badgeStatus = document.createElement("span");
        badgeStatus.className = "badge bg-success ms-2";
        badgeStatus.innerText = "S";
        block.appendChild(badgeStatus);

        // Чекбокс
        let input = document.createElement("input");
        input.type = "checkbox";
        input.className = "account__checkbox ms-2";
        input.id = `account-${acc.id}`;
        input.value = acc.login;
        block.appendChild(input);

        // Клик по блоку — выделяет аккаунт
        block.addEventListener("click", function (e) {
            selectAccount(input.id);
        });

        accountsContainer.appendChild(block);
    });

    // Автовыделение первого аккаунта
    if (accounts.length > 0) {
        selectAccount(`account-${accounts[0].id}`);
    }
}

function awaitAccounts() {
  console.log("AWAIT ACCOUNTS")
  setInterval(function () {
    if (awaitAccountsPingStatus) {
      getKickSocket().send(JSON.stringify({
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
  console.log('[showNoAccounts] called');
  const accountsContainer = document.getElementById("accounts");

  accountsContainer.innerHTML = "";
  let message = document.createElement("p");
  message.className = "w-50 text-center alert alert-warning";
  message.innerText = "You don't have any assigned accounts. Contact the administrator"
  accountsContainer.appendChild(message)
}

window.showAccounts = showAccounts;
window.selectAccount = selectAccount;
window.showNoAccounts = showNoAccounts;
window.awaitAccounts = awaitAccounts;

export { showAccounts, showNoAccounts, awaitAccounts };