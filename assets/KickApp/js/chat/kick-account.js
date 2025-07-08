import {getKickSocket, awaitAccountsPingStatus} from "./kick-ws";
import {showAlert} from "./alert";
import {updateChatButtonsState, updateWorkButtonsState} from "./kick-work";

const kickAccounts = document.getElementsByClassName('account__checkbox');

function showAccounts(accounts) {
    console.log('[showAccounts] called with', accounts);
    const accountsContainer = document.getElementById("accounts");
    accountsContainer.innerHTML = "";

    if (!accounts.length) return;

    accounts.forEach((acc, idx) => {
        let block = document.createElement("div");
        block.className = "account-block account d-flex align-items-center gap-2 mb-2 p-2 rounded bg-dark";
        block.setAttribute("data-account-status", acc.status);

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
        badgeStatus.className = acc.status === 'active' ? "ms-2 text-success" : "ms-2 text-danger";
        badgeStatus.innerHTML = acc.status === 'active' ? '✔️' : '❌';
        block.appendChild(badgeStatus);

        // Чекбокс
        let input = document.createElement("input");
        input.type = "checkbox";
        input.className = "account__checkbox ms-2";
        input.id = `account-${acc.id}`;
        input.value = acc.login;
        input.setAttribute("data-account-selected", "false");
        if (acc.status !== 'active') input.disabled = true;
        block.appendChild(input);

        // Клик по блоку — выделяет аккаунт (только если активен)
        block.addEventListener("click", function (e) {
            if (acc.status === 'active') {
                selectAccount(input.id);
                updateChatButtonsState();
            }
        });

        accountsContainer.appendChild(block);
    });

    // Обновляем состояние кнопок после загрузки аккаунтов
    updateWorkButtonsState();
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
    const clickedAccount = document.getElementById(id);
    if (!clickedAccount) return;
    
    // Переключаем состояние выбранного аккаунта
    const isCurrentlySelected = clickedAccount.getAttribute("data-account-selected") === "true";
    const newState = !isCurrentlySelected;
    
    console.log(`[selectAccount] Toggling account ${id}: ${isCurrentlySelected} -> ${newState}`);
    
    // Обновляем состояние для кликнутого аккаунта
    clickedAccount.setAttribute("data-account-selected", newState ? "true" : "false");
    clickedAccount.checked = newState;
    
    if (newState) {
        clickedAccount.parentNode.classList.add("account-checked");
    } else {
        clickedAccount.parentNode.classList.remove("account-checked");
    }
    
    // Обновляем состояние кнопок
    updateChatButtonsState();
}

function showNoAccounts(){
  console.log('[showNoAccounts] called');
  const accountsContainer = document.getElementById("accounts");

  accountsContainer.innerHTML = "";
  let message = document.createElement("p");
  message.className = "w-50 text-center alert alert-warning";
  message.innerText = "You don't have any assigned accounts. Contact the administrator"
  accountsContainer.appendChild(message)
  
  // Обновляем состояние кнопок когда нет аккаунтов
  updateWorkButtonsState();
}

window.showAccounts = showAccounts;
window.selectAccount = selectAccount;
window.showNoAccounts = showNoAccounts;
window.awaitAccounts = awaitAccounts;

export { showAccounts, showNoAccounts, awaitAccounts, selectAccount };