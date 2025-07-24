import { getKickSocket } from "./kick-ws";

// Account Manager - автоматическое переключение между аккаунтами

class AccountManager {
  constructor() {
    this.autoSwitchEnabled = false;
    this.randomMode = false;
    this.selectedAccounts = [];
    this.usedAccounts = new Set(); // Для отслеживания использованных в рандомном режиме
    this.currentAccountIndex = 0;
    this.autoSwitchInterval = null;
    
    this.init();
  }
  
  init() {
    // Инициализация элементов управления
    this.autoSwitchCheckbox = document.getElementById('autoSwitchAccounts');
    this.randomModeCheckbox = document.getElementById('randomMode');
    this.selectAllBtn = document.getElementById('selectAllAccounts');
    this.deselectAllBtn = document.getElementById('deselectAllAccounts');
    this.currentAccountInfo = document.getElementById('currentAccountInfo');
    
    // Привязка событий
    this.autoSwitchCheckbox?.addEventListener('change', (e) => this.toggleAutoSwitch(e.target.checked));
    this.randomModeCheckbox?.addEventListener('change', (e) => this.toggleRandomMode(e.target.checked));
    this.selectAllBtn?.addEventListener('click', () => this.selectAllAccounts());
    this.deselectAllBtn?.addEventListener('click', () => this.deselectAllAccounts());
    
    // Обновляем состояние элементов управления
    this.updateControlsState();
  }
  
  // Включение/выключение автоматического переключения
  toggleAutoSwitch(enabled) {
    this.autoSwitchEnabled = enabled;
    
    if (enabled) {
      this.startAutoSwitch();
      this.randomModeCheckbox.disabled = false;
    } else {
      this.stopAutoSwitch();
      this.randomModeCheckbox.disabled = true;
      this.randomModeCheckbox.checked = false;
      this.randomMode = false;
    }
    
    this.updateControlsState();
    console.log(`[AccountManager] Auto switch ${enabled ? 'enabled' : 'disabled'}`);
    
    // Логируем действие в WebSocket
    const ws = getKickSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'KICK_LOG_ACTION',
        action_type: 'checkbox_toggle',
        description: `Auto switch accounts ${enabled ? 'enabled' : 'disabled'}`,
        details: {
          action: 'auto_switch_toggle',
          enabled: enabled
        }
      }));
    }
    
    // Обновляем состояние кнопок после изменения режима
    if (window.updateChatButtonsState) {
      setTimeout(() => {
        window.updateChatButtonsState();
      }, 100);
    }
  }
  
  // Включение/выключение рандомного режима
  toggleRandomMode(enabled) {
    this.randomMode = enabled;
    this.usedAccounts.clear(); // Сбрасываем список использованных аккаунтов
    
    if (enabled) {
      console.log('[AccountManager] Random mode enabled');
    } else {
      console.log('[AccountManager] Sequential mode enabled');
    }
    
    // Логируем действие в WebSocket
    const ws = getKickSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'KICK_LOG_ACTION',
        action_type: 'checkbox_toggle',
        description: `Random mode ${enabled ? 'enabled' : 'disabled'}`,
        details: {
          action: 'random_mode_toggle',
          enabled: enabled
        }
      }));
    }
  }
  
  // Запуск автоматического переключения
  startAutoSwitch() {
    if (this.autoSwitchInterval) {
      clearInterval(this.autoSwitchInterval);
      this.autoSwitchInterval = null;
    }
    
    // Сразу переключаем на первый аккаунт
    this.switchToNextAccount();
    
    console.log('[AccountManager] Auto switch enabled - will switch after message send');
  }
  
  // Остановка автоматического переключения
  stopAutoSwitch() {
    if (this.autoSwitchInterval) {
      clearInterval(this.autoSwitchInterval);
      this.autoSwitchInterval = null;
    }
    
    // Снимаем выделение со всех аккаунтов
    this.deselectAllAccounts();
  }
  
  // Переключение на следующий аккаунт
  switchToNextAccount() {
    const activeAccounts = this.getActiveAccounts();
    
    if (activeAccounts.length === 0) {
      console.log('[AccountManager] No active accounts available');
      this.updateCurrentAccountInfo('No active accounts');
      return;
    }
    
    let nextAccount;
    
    if (this.randomMode) {
      // Рандомный режим без повторений
      const availableAccounts = activeAccounts.filter(acc => !this.usedAccounts.has(acc.id));
      
      if (availableAccounts.length === 0) {
        // Все аккаунты использованы, сбрасываем список
        this.usedAccounts.clear();
        console.log('[AccountManager] All accounts used, resetting random cycle');
        nextAccount = activeAccounts[Math.floor(Math.random() * activeAccounts.length)];
      } else {
        nextAccount = availableAccounts[Math.floor(Math.random() * availableAccounts.length)];
      }
      
      this.usedAccounts.add(nextAccount.id);
    } else {
      // Последовательный режим
      nextAccount = activeAccounts[this.currentAccountIndex % activeAccounts.length];
      this.currentAccountIndex++;
    }
    
    // Выбираем аккаунт
    this.selectSingleAccount(nextAccount.id);
    this.updateCurrentAccountInfo(nextAccount.login);
    
    console.log(`[AccountManager] Switched to account: ${nextAccount.login}`);
  }
  
  // Переключение аккаунта после отправки сообщения
  switchAfterMessageSend() {
    if (!this.autoSwitchEnabled) {
      return;
    }
    
    console.log('[AccountManager] Switching account after message send');
    this.switchToNextAccount();
  }
  
  // Получение активных аккаунтов
  getActiveAccounts() {
    const accountBlocks = document.querySelectorAll('.account-block[data-account-status="active"]');
    const accounts = [];
    
    accountBlocks.forEach(block => {
      const checkbox = block.querySelector('.account__checkbox');
      if (checkbox) {
        accounts.push({
          id: checkbox.id,
          login: checkbox.value,
          element: checkbox
        });
      }
    });
    
    return accounts;
  }
  
  // Выбор одного аккаунта (снимает выделение с остальных)
  selectSingleAccount(accountId) {
    // Снимаем выделение со всех аккаунтов
    const allCheckboxes = document.querySelectorAll('.account__checkbox');
    allCheckboxes.forEach(checkbox => {
      checkbox.checked = false;
      checkbox.setAttribute('data-account-selected', 'false');
      checkbox.parentNode.classList.remove('account-checked');
    });
    
    // Выбираем нужный аккаунт
    const targetCheckbox = document.getElementById(accountId);
    if (targetCheckbox) {
      targetCheckbox.checked = true;
      targetCheckbox.setAttribute('data-account-selected', 'true');
      targetCheckbox.parentNode.classList.add('account-checked');
    }
    
    // Обновляем состояние кнопок
    if (window.updateChatButtonsState) {
      setTimeout(() => {
        window.updateChatButtonsState();
      }, 50);
    }
  }
  
  // Выбор всех аккаунтов
  selectAllAccounts() {
    const activeCheckboxes = document.querySelectorAll('.account__checkbox:not(:disabled)');
    
    activeCheckboxes.forEach(checkbox => {
      checkbox.checked = true;
      checkbox.setAttribute('data-account-selected', 'true');
      checkbox.parentNode.classList.add('account-checked');
    });
    
    this.updateCurrentAccountInfo(`${activeCheckboxes.length} accounts selected`);
    
    if (window.updateChatButtonsState) {
      window.updateChatButtonsState();
    }
    
    console.log(`[AccountManager] Selected ${activeCheckboxes.length} accounts`);
    
    // Логируем действие в WebSocket
    const ws = getKickSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'KICK_LOG_ACTION',
        action_type: 'checkbox_toggle',
        description: `Выбраны все аккаунты (${activeCheckboxes.length} шт.)`,
        details: {
          action: 'select_all',
          count: activeCheckboxes.length
        }
      }));
    }
  }
  
  // Снятие выделения со всех аккаунтов
  deselectAllAccounts() {
    const allCheckboxes = document.querySelectorAll('.account__checkbox');
    
    allCheckboxes.forEach(checkbox => {
      checkbox.checked = false;
      checkbox.setAttribute('data-account-selected', 'false');
      checkbox.parentNode.classList.remove('account-checked');
    });
    
    this.updateCurrentAccountInfo('None selected');
    
    if (window.updateChatButtonsState) {
      window.updateChatButtonsState();
    }
    
    console.log('[AccountManager] Deselected all accounts');
    
    // Логируем действие в WebSocket
    const ws = getKickSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'KICK_LOG_ACTION',
        action_type: 'checkbox_toggle',
        description: 'Снято выделение со всех аккаунтов',
        details: {
          action: 'deselect_all',
          count: allCheckboxes.length
        }
      }));
    }
  }
  
  // Обновление информации о текущем аккаунте
  updateCurrentAccountInfo(info) {
    if (this.currentAccountInfo) {
      this.currentAccountInfo.textContent = info;
    }
  }
  
  // Обновление состояния элементов управления
  updateControlsState() {
    if (this.randomModeCheckbox) {
      this.randomModeCheckbox.disabled = !this.autoSwitchEnabled;
    }
  }
  
  // Получение текущего состояния
  getState() {
    return {
      autoSwitchEnabled: this.autoSwitchEnabled,
      randomMode: this.randomMode,
      currentAccountIndex: this.currentAccountIndex,
      usedAccountsCount: this.usedAccounts.size
    };
  }
  
  // Сброс состояния
  reset() {
    this.stopAutoSwitch();
    this.autoSwitchEnabled = false;
    this.randomMode = false;
    this.usedAccounts.clear();
    this.currentAccountIndex = 0;
    
    if (this.autoSwitchCheckbox) this.autoSwitchCheckbox.checked = false;
    if (this.randomModeCheckbox) {
      this.randomModeCheckbox.checked = false;
      this.randomModeCheckbox.disabled = true;
    }
    
    this.updateControlsState();
    this.updateCurrentAccountInfo('None selected');
  }
}

// Создаем глобальный экземпляр
let accountManager;

// Инициализация после загрузки DOM
document.addEventListener('DOMContentLoaded', () => {
  accountManager = new AccountManager();
  window.accountManager = accountManager; // Делаем доступным глобально
});

// Экспорт для использования в других модулях
export { AccountManager }; 