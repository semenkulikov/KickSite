import {getKickChannel} from "./kick-channel-db";
import {changeViewChannel} from "./kick-channel";
import {loadAutoMessagesData} from "./kick-auto-messages";
import {getKickSocket} from "./kick-ws";
import {updateChatButtonsState} from "./kick-work";
import {AccountManager} from "./account-manager";

document.addEventListener('DOMContentLoaded', () => {
  console.log("DOM loaded")

  console.log("Load channel")
  getKickChannel().then((channel) => {
    if (channel) {
      changeViewChannel(true, channel.value);
      window.selectedChannel = channel.value;
      if (window.socket && window.socket.readyState === WebSocket.OPEN) {
        window.socket.send(JSON.stringify({
          type: 'KICK_SELECT_CHANNEL',
          channel: channel.value
        }));
      }
    } else {
      changeViewChannel(false);
      window.selectedChannel = '';
    }
    }).catch((error) => {
    console.error('Error loading channel:', error);
  });

  console.log("Load auto-messages if exists")
  loadAutoMessagesData()

  $("#inputMessage").focus();

  // Изначально деактивируем кнопки Chat и Auto Messages до загрузки аккаунтов
  updateChatButtonsState();

  // После загрузки страницы, если канал уже выбран — сразу отправляем событие на ws
  let channel = window.selectedChannel;
  if (!channel) {
    // Пробуем взять из DOM
    const el = document.getElementById('selectedChannel');
    if (el && el.dataset.status === 'selected' && el.innerText) {
      channel = el.innerText.trim();
      window.selectedChannel = channel;
      // Форсируем отправку события на ws
      if (window.selectedChannel && typeof window.selectedChannel === 'string') {
        getKickSocket().send(JSON.stringify({
          type: 'KICK_SELECT_CHANNEL',
          channel: window.selectedChannel
        }));
        console.log('[KICK-WS] Forced KICK_SELECT_CHANNEL after selectedChannel set:', window.selectedChannel);
      }
    }
  }
  // Жёсткая проверка типа
  if (typeof channel !== 'string') {
    console.error('[KICK-WS] selectedChannel is not a string!', channel);
    channel = '';
    window.selectedChannel = '';
  }
  if (channel && typeof channel === 'string') {
    getKickSocket().send(JSON.stringify({
      type: 'KICK_SELECT_CHANNEL',
      channel: channel
    }));
    console.log('[KICK-WS] Auto-sent KICK_SELECT_CHANNEL for already selected channel:', channel);
  }

  // Fallback удален - теперь используется правильная логика обновления кнопок в showAccounts
  
  // Обработчик для завершения работы при перезагрузке страницы или выходе
  window.addEventListener('beforeunload', () => {
    console.log('[KICK-WS] Page is unloading, ending work');
    if (window.socket && window.socket.readyState === WebSocket.OPEN) {
      window.socket.send(JSON.stringify({
        type: 'KICK_END_WORK'
      }));
      // Также отправляем событие выхода
      window.socket.send(JSON.stringify({
        type: 'KICK_LOGOUT'
      }));
    }
  });
  
  // Обработчик для завершения работы при закрытии вкладки
  window.addEventListener('unload', () => {
    console.log('[KICK-WS] Page is unloading (unload event)');
    if (window.socket && window.socket.readyState === WebSocket.OPEN) {
      window.socket.send(JSON.stringify({
        type: 'KICK_END_WORK'
      }));
    }
  });
  
  // Обработчик для кнопки выхода
  document.addEventListener('click', (e) => {
    if (e.target.matches('a[href*="logout"], a[href*="/logout"]')) {
      console.log('[KICK-WS] Logout link clicked, ending work');
      if (window.socket && window.socket.readyState === WebSocket.OPEN) {
        window.socket.send(JSON.stringify({
          type: 'KICK_END_WORK'
        }));
        window.socket.send(JSON.stringify({
          type: 'KICK_LOGOUT'
        }));
      }
    }
  });
});