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
    // this.selectAllBtn = document.getElementById('selectAllAccounts'); // Закомментировано
    // this.deselectAllBtn = document.getElementById('deselectAllAccounts'); // Закомментировано
    this.currentAccountInfo = document.getElementById('currentAccountInfo');
    
    // Привязка событий
    this.autoSwitchCheckbox?.addEventListener('change', (e) => this.toggleAutoSwitch(e.target.checked));
    this.randomModeCheckbox?.addEventListener('change', (e) => this.toggleRandomMode(e.target.checked));
    // this.selectAllBtn?.addEventListener('click', () => this.selectAllAccounts()); // Закомментировано
    // this.deselectAllBtn?.addEventListener('click', () => this.deselectAllAccounts()); // Закомментировано
    
    // Инициализация поиска аккаунтов
    this.initAccountSearch();
    
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
  
  // Получение активных аккаунтов (видимых)
  getActiveAccounts() {
    const accountBlocks = document.querySelectorAll('.account-block[data-account-status="active"]');
    const accounts = [];
    
    accountBlocks.forEach(block => {
      // Проверяем, что аккаунт видим (не скрыт поиском)
      if (block.style.display !== 'none') {
        const checkbox = block.querySelector('.account__checkbox');
        if (checkbox) {
          accounts.push({
            id: checkbox.id,
            login: checkbox.value,
            element: checkbox
          });
        }
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
    
    // Выбираем нужный аккаунт (только если он активен)
    const targetCheckbox = document.getElementById(accountId);
    if (targetCheckbox) {
      const accountBlock = targetCheckbox.closest('.account-block');
      const status = accountBlock ? accountBlock.getAttribute('data-account-status') : 'active';
      
      if (status === 'active') {
        targetCheckbox.checked = true;
        targetCheckbox.setAttribute('data-account-selected', 'true');
        targetCheckbox.parentNode.classList.add('account-checked');
      } else {
        console.log(`[AccountManager] Cannot select inactive account: ${accountId}`);
      }
    }
    
    // Обновляем состояние кнопок
    if (window.updateChatButtonsState) {
      setTimeout(() => {
        window.updateChatButtonsState();
      }, 50);
    }
  }
  
  // Выбор всех видимых активных аккаунтов
  selectAllAccounts() {
    // Выбираем только видимые активные аккаунты
    const activeCheckboxes = document.querySelectorAll('.account__checkbox:not(:disabled)');
    const visibleActiveAccounts = Array.from(activeCheckboxes).filter(checkbox => {
      const accountBlock = checkbox.closest('.account-block');
      const status = accountBlock ? accountBlock.getAttribute('data-account-status') : 'active';
      const isVisible = accountBlock ? accountBlock.style.display !== 'none' : true;
      return status === 'active' && isVisible;
    });
    
    // Обрабатываем все видимые активные аккаунты батчами для избежания зависания UI
    this.processCheckboxesInBatches(visibleActiveAccounts, true, visibleActiveAccounts.length);
  }
  
  // Обработка чекбоксов батчами для избежания зависания UI
  processCheckboxesInBatches(checkboxes, checked, totalCount) {
    const batchSize = 1000; // Увеличиваем размер батча для максимальной скорости
    let processed = 0;
    
    const processBatch = () => {
      const batch = checkboxes.slice(processed, processed + batchSize);
      
      // Используем более эффективную обработку
      const operations = batch.map(checkbox => () => {
        checkbox.checked = checked;
        checkbox.setAttribute('data-account-selected', checked ? 'true' : 'false');
        checkbox.parentNode.classList.toggle('account-checked', checked);
      });
      
      // Выполняем все операции сразу
      operations.forEach(op => op());
      
      processed += batch.length;
      
      // Обновляем прогресс реже для снижения нагрузки
      if (processed % 2000 === 0 || processed >= totalCount) {
        if (checked) {
          this.updateCurrentAccountInfo(`Processing: ${processed}/${totalCount} accounts...`);
        } else {
          this.updateCurrentAccountInfo(`Deselecting: ${processed}/${totalCount} accounts...`);
        }
      }
      
      if (processed < totalCount) {
        // Планируем следующий батч без задержки для максимальной скорости
        requestAnimationFrame(processBatch);
      } else {
        // Завершили обработку
        if (checked) {
          this.updateCurrentAccountInfo(`${totalCount} accounts selected`);
          console.log(`[AccountManager] Selected ${totalCount} accounts`);
          
          // Логируем действие в WebSocket
          const ws = getKickSocket();
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              type: 'KICK_LOG_ACTION',
              action_type: 'checkbox_toggle',
              description: `Выбраны аккаунты (${totalCount} шт.)`,
              details: {
                action: 'select_all',
                count: totalCount
              }
            }));
          }
        } else {
          this.updateCurrentAccountInfo('None selected');
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
                count: totalCount
              }
            }));
          }
        }
        
        if (window.updateChatButtonsState) {
          window.updateChatButtonsState();
        }
      }
    };
    
    // Запускаем обработку
    processBatch();
  }
  
  // Снятие выделения со всех аккаунтов
  deselectAllAccounts() {
    const allCheckboxes = document.querySelectorAll('.account__checkbox');
    
    // Обрабатываем батчами для избежания зависания UI
    this.processCheckboxesInBatches(Array.from(allCheckboxes), false, allCheckboxes.length);
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
  
  // Инициализация поиска аккаунтов
  initAccountSearch() {
    const searchInput = document.getElementById('accountSearch');
    const clearButton = document.getElementById('clearSearch');
    
    if (searchInput) {
      // Добавляем обработчик события input для поиска в реальном времени
      searchInput.addEventListener('input', (e) => {
        const query = e.target.value;
        this.filterAccounts(query);
        this.updateClearButton(query);
      });
      
      // Добавляем обработчик события keydown для очистки при нажатии Escape
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          searchInput.value = '';
          this.filterAccounts('');
          this.updateClearButton('');
        }
      });
      
      // Добавляем обработчик для кнопки очистки
      if (clearButton) {
        clearButton.addEventListener('click', () => {
          searchInput.value = '';
          this.filterAccounts('');
          this.updateClearButton('');
          searchInput.focus();
        });
      }
      
      console.log('[AccountManager] Account search initialized');
    }
  }
  
  // Обновление видимости кнопки очистки
  updateClearButton(query) {
    const clearButton = document.getElementById('clearSearch');
    if (clearButton) {
      clearButton.style.display = query.trim() ? 'block' : 'none';
    }
  }
  
  // Фильтрация аккаунтов по поисковому запросу
  filterAccounts(query) {
    const accountsContainer = document.getElementById('accounts');
    const searchQuery = query.toLowerCase().trim();
    
    console.log(`[AccountManager] Filtering accounts with query: "${searchQuery}"`);
    
    // Получаем все блоки аккаунтов
    const accountBlocks = accountsContainer.querySelectorAll('.account-block');
    console.log(`[AccountManager] Found ${accountBlocks.length} account blocks to filter`);
    
    let visibleCount = 0;
    let activeVisibleCount = 0;
    
    accountBlocks.forEach((block) => {
      const loginElement = block.querySelector('.account-login');
      const login = loginElement ? loginElement.textContent.toLowerCase() : '';
      const status = block.getAttribute('data-account-status');
      
      // Проверяем, соответствует ли аккаунт поисковому запросу
      const matches = searchQuery === '' || login.includes(searchQuery);
      
      // Отладочная информация о текущем состоянии элемента
      const currentDisplay = window.getComputedStyle(block).display;
      console.log(`[AccountManager] Account ${login}: current display = ${currentDisplay}, matches = ${matches}`);
      
      if (matches) {
        // Элемент соответствует поиску - показываем его
        block.style.setProperty('display', '', 'important');
        console.log(`[AccountManager] Showing account: ${login}`);
        visibleCount++;
        if (status === 'active') {
          activeVisibleCount++;
        }
      } else {
        // Элемент не соответствует поиску - скрываем его
        block.style.setProperty('display', 'none', 'important');
        console.log(`[AccountManager] Hiding account: ${login}`);
      }
    });
    
    // Обновляем информацию о видимых аккаунтах
    if (searchQuery === '') {
      this.updateCurrentAccountInfo(`${activeVisibleCount} active accounts available`);
    } else {
      this.updateCurrentAccountInfo(`${activeVisibleCount} active accounts match "${query}"`);
    }
    
    console.log(`[AccountManager] Hidden ${accountBlocks.length - visibleCount} accounts, showed ${visibleCount} accounts (${activeVisibleCount} active)`);
    
    // Обновляем состояние кнопок после фильтрации
    if (window.updateChatButtonsState) {
      setTimeout(() => {
        window.updateChatButtonsState();
      }, 100);
    }
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