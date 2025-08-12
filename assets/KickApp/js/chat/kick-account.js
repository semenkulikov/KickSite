import {getKickSocket, awaitAccountsPingStatus} from "./kick-ws";
import {showAlert} from "./alert";
import {updateChatButtonsState, updateWorkButtonsState} from "./kick-work";
import {AccountManager} from "./account-manager";

const kickAccounts = document.getElementsByClassName('account__checkbox');

function showAccounts(accounts) {
    console.log('[showAccounts] called with', accounts);
    const accountsContainer = document.getElementById("accounts");
    
    // Если пришёл один аккаунт (инкрементальная подгрузка)
    if (accounts.length === 1) {
        const acc = accounts[0];
        // Проверяем, есть ли уже блок с этим id
        let existing = document.getElementById(`account-block-${acc.id}`);
        
        if (existing) {
            // Если аккаунт уже существует, только обновляем статус
            existing.setAttribute("data-account-status", acc.status);
            const checkbox = existing.querySelector('.account__checkbox');
            const badgeStatus = existing.querySelector('.ms-2');
            
            // Если аккаунт стал неактивным, снимаем с него выделение
            if (acc.status !== 'active') {
                existing.classList.remove("account-checked");
        
                console.log(`[showAccounts] Removed selection from inactive account: ${acc.login}`);
            }
            
            if (badgeStatus) {
                badgeStatus.className = acc.status === 'active' ? "ms-2 text-success" : "ms-2 text-danger";
                badgeStatus.innerHTML = acc.status === 'active' ? '✔️' : '❌';
            }
        } else {
            // Если аккаунта нет, создаем новый
            let block = document.createElement("div");
            block.className = "account-block";
            block.setAttribute("data-account-status", acc.status);
            block.id = `account-block-${acc.id}`;

            // Логин
            let login = document.createElement("span");
            login.className = "account-login";
            login.innerText = acc.login;
            block.appendChild(login);
            
            // Добавляем hover стили через JavaScript
            block.addEventListener("mouseenter", function (e) {
                console.log(`[hover] Mouse entered: ${acc.login}`);
                if (this.getAttribute("data-account-selected") !== "true") {
                    this.style.backgroundColor = '#1a1a1a';
                    this.style.borderColor = '#2196F3';
                    this.style.borderWidth = '3px';
                    this.style.transform = 'translateY(-4px) scale(1.03)';
                    this.style.boxShadow = '0 8px 20px rgba(33, 150, 243, 0.4)';
                }
            });
            
            block.addEventListener("mouseleave", function (e) {
                console.log(`[hover] Mouse left: ${acc.login}`);
                if (this.getAttribute("data-account-selected") !== "true") {
                    this.style.backgroundColor = '#1a1a1a';
                    this.style.borderColor = '#4a4a5a';
                    this.style.borderWidth = '3px';
                    this.style.transform = 'translateY(0) scale(1)';
                    this.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.4)';
                }
            });
            
            // Клик по блоку — выделяет аккаунт (только если активен)
            block.addEventListener("click", function (e) {
                console.log(`[click] Account block clicked: ${acc.login} (status: ${acc.status})`);
                if (acc.status === 'active') {
                    console.log(`[click] Calling selectAccount for: ${acc.login}`);
                    selectAccount(acc.id, acc.login);
                    updateChatButtonsState();
                } else {
                    console.log(`[click] Cannot select inactive account: ${acc.login}`);
                }
            });
            accountsContainer.appendChild(block);
        }
        
        // Если хотя бы один активный аккаунт — обновить кнопки сразу
        if (acc.status === 'active') {
            updateWorkButtonsState();
        }
        // Убираем крутилку, если есть
        const uploading = document.getElementById('uploading-accounts-indicator');
        if (uploading) uploading.remove();
        return;
    }
    
            // Если массив — полная перерисовка (только при первой загрузке)
        accountsContainer.innerHTML = "";
        if (!accounts.length) {
            showNoAccounts();
            return;
        }
        

        
        accounts.forEach((acc, idx) => {
            let block = document.createElement("div");
            block.className = "account-block";
            block.setAttribute("data-account-status", acc.status);
            block.id = `account-block-${acc.id}`;

            // Логин
            let login = document.createElement("span");
            login.className = "account-login";
            login.innerText = acc.login;
            block.appendChild(login);
            // По умолчанию никто не выбран
            block.setAttribute("data-account-selected", "false");

            // Добавляем hover стили через JavaScript
            block.addEventListener("mouseenter", function (e) {
                console.log(`[hover] Mouse entered: ${acc.login}`);
                if (this.getAttribute("data-account-selected") !== "true") {
                    this.style.backgroundColor = '#1a1a1a';
                    this.style.borderColor = '#2196F3';
                    this.style.borderWidth = '3px';
                    this.style.transform = 'translateY(-4px) scale(1.03)';
                    this.style.boxShadow = '0 8px 20px rgba(33, 150, 243, 0.4)';
                }
            });
            
            block.addEventListener("mouseleave", function (e) {
                console.log(`[hover] Mouse left: ${acc.login}`);
                if (this.getAttribute("data-account-selected") !== "true") {
                    this.style.backgroundColor = '#1a1a1a';
                    this.style.borderColor = '#4a4a5a';
                    this.style.borderWidth = '3px';
                    this.style.transform = 'translateY(0) scale(1)';
                    this.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.4)';
                }
            });
            
            // Клик по блоку — выделяет аккаунт (только если активен)
            block.addEventListener("click", function (e) {
                console.log(`[click] Account block clicked: ${acc.login} (status: ${acc.status})`);
                if (acc.status === 'active') {
                    console.log(`[click] Calling selectAccount for: ${acc.login}`);
                    selectAccount(acc.id, acc.login);
                    updateChatButtonsState();
                } else {
                    console.log(`[click] Cannot select inactive account: ${acc.login}`);
                }
            });
            accountsContainer.appendChild(block);
        });
        
        // Обновляем информацию о выбранных аккаунтах
        if (window.accountManager) {
            window.accountManager.updateCurrentAccountInfo(`${accounts.length} active accounts available`);
        } else {
            // Инициализируем AccountManager если он еще не создан
            window.accountManager = new AccountManager();
            window.accountManager.updateCurrentAccountInfo(`${accounts.length} active accounts available`);
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

function selectAccount(id, login) {
    console.log(`[selectAccount] Called for account ${login} (ID: ${id})`);
    
    const accountBlock = document.getElementById(`account-block-${id}`);
    if (!accountBlock) {
        console.log(`[selectAccount] Account block not found for ID: ${id}`);
        return;
    }
    
    // Проверяем статус аккаунта перед выбором
    const status = accountBlock.getAttribute('data-account-status');
    console.log(`[selectAccount] Account status: ${status}`);
    
    if (status !== 'active') {
        console.log(`[selectAccount] Cannot select inactive account: ${login}`);
        return;
    }
    
    // Переключаем состояние выбранного аккаунта
    const isCurrentlySelected = accountBlock.getAttribute("data-account-selected") === "true";
    const newState = !isCurrentlySelected; // Переключаем состояние
    
    console.log(`[selectAccount] Toggling account ${login}: ${isCurrentlySelected} -> ${newState}`);
    
    // Обновляем состояние для кликнутого аккаунта
    accountBlock.setAttribute("data-account-selected", newState ? "true" : "false");
    console.log(`[selectAccount] Set data-account-selected to: ${newState ? "true" : "false"}`);
    
    // Принудительно применяем стили через JavaScript
    if (newState) {
        accountBlock.style.backgroundColor = '#2e7d32';
        accountBlock.style.borderColor = '#4CAF50';
        accountBlock.style.borderWidth = '2px';
        accountBlock.style.boxShadow = '0 6px 20px rgba(76, 175, 80, 0.5)';
        accountBlock.style.transform = 'translateY(-2px) scale(1.02)';
    } else {
        accountBlock.style.backgroundColor = '#1a1a1a';
        accountBlock.style.borderColor = '#4a4a5a';
        accountBlock.style.borderWidth = '2px';
        accountBlock.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.4)';
        accountBlock.style.transform = 'translateY(0) scale(1)';
    }
    
    // Проверяем, применились ли CSS стили
    setTimeout(() => {
        const computedStyle = window.getComputedStyle(accountBlock);
        console.log(`[selectAccount] Computed background-color: ${computedStyle.backgroundColor}`);
        console.log(`[selectAccount] Computed border-color: ${computedStyle.borderColor}`);
        console.log(`[selectAccount] Computed transform: ${computedStyle.transform}`);
    }, 100);
    
    // Обновляем время последнего использования для сортировки
    if (newState && window.accountManager) {
        window.accountManager.updateAccountLastUsed(id, login);
    }
    
    // Сортируем аккаунты после изменения состояния (выбор или снятие выделения)
    if (window.accountManager) {
        setTimeout(() => {
            window.accountManager.sortAccountsByLastUsed();
        }, 100);
    }
    
    // Обновляем информацию о выбранных аккаунтах
    if (window.accountManager) {
        const selectedAccounts = document.querySelectorAll('.account-block[data-account-selected="true"]');
        if (selectedAccounts.length === 0) {
            window.accountManager.updateCurrentAccountInfo('None selected');
        } else if (selectedAccounts.length === 1) {
            const loginElement = selectedAccounts[0].querySelector('.account-login');
            const login = loginElement ? loginElement.textContent : 'Unknown';
            window.accountManager.updateCurrentAccountInfo(`Selected: ${login}`);
        } else {
            window.accountManager.updateCurrentAccountInfo(`${selectedAccounts.length} accounts selected`);
        }
    }
    
    // Обновляем состояние кнопок
    updateChatButtonsState();
}

function deselectAccount(id, login) {
    console.log(`[deselectAccount] Called for account ${login} (ID: ${id})`);
    
    const accountBlock = document.getElementById(`account-block-${id}`);
    if (!accountBlock) {
        console.log(`[deselectAccount] Account block not found for ID: ${id}`);
        return;
    }
    
    // Снимаем выделение с аккаунта
    accountBlock.setAttribute("data-account-selected", "false");
    console.log(`[deselectAccount] Set data-account-selected to: false`);
    
    // Применяем стили для невыбранного состояния
    accountBlock.style.backgroundColor = '#1a1a1a';
    accountBlock.style.borderColor = '#4a4a5a';
    accountBlock.style.borderWidth = '2px';
    accountBlock.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.4)';
    accountBlock.style.transform = 'translateY(0) scale(1)';
    
    // Сортируем аккаунты после снятия выделения
    if (window.accountManager) {
        setTimeout(() => {
            window.accountManager.sortAccountsByLastUsed();
        }, 100);
    }
    
    // Обновляем информацию о выбранных аккаунтах
    if (window.accountManager) {
        const selectedAccounts = document.querySelectorAll('.account-block[data-account-selected="true"]');
        if (selectedAccounts.length === 0) {
            window.accountManager.updateCurrentAccountInfo('None selected');
        } else if (selectedAccounts.length === 1) {
            const loginElement = selectedAccounts[0].querySelector('.account-login');
            const login = loginElement ? loginElement.textContent : 'Unknown';
            window.accountManager.updateCurrentAccountInfo(`Selected: ${login}`);
        } else {
            window.accountManager.updateCurrentAccountInfo(`${selectedAccounts.length} accounts selected`);
        }
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
window.deselectAccount = deselectAccount;
window.showNoAccounts = showNoAccounts;
window.awaitAccounts = awaitAccounts;

export { showAccounts, showNoAccounts, awaitAccounts, selectAccount, deselectAccount };