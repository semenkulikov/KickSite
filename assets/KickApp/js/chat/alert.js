// Добавляем CSS анимации в head
if (!document.getElementById('alert-animations')) {
  const style = document.createElement('style');
  style.id = 'alert-animations';
  style.textContent = `
    @keyframes slideInFromRight {
      from {
        transform: translateX(100%);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }
    
    @keyframes slideOutToRight {
      from {
        transform: translateX(0);
        opacity: 1;
      }
      to {
        transform: translateX(100%);
        opacity: 0;
      }
    }
    
    .alert-curtain {
      background: #ffffff;
      border-left: 5px solid;
      border-radius: 8px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      padding: 12px 16px;
      margin-bottom: 6px;
      transform: translateX(100%);
      transition: transform 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
      max-width: 450px;
      position: relative;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      line-height: 1.4;
      color: #333;
    }
    
    .alert-curtain.show {
      transform: translateX(0);
    }
    
    .alert-curtain.hide {
      transform: translateX(100%);
    }
    
    .alert-curtain::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.05) 100%);
      pointer-events: none;
    }
    
    .alert-curtain .close {
      background: rgba(0,0,0,0.1);
      border: none;
      font-size: 18px;
      font-weight: bold;
      color: #666;
      cursor: pointer;
      padding: 4px;
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      transition: all 0.2s;
      margin-left: 12px;
    }
    
    .alert-curtain .close:hover {
      background: rgba(0,0,0,0.2);
      color: #333;
    }
    
    .alert-curtain .message-content {
      flex: 1;
      margin-right: 8px;
      word-wrap: break-word;
    }
    
    .alert-curtain.alert-curtain-alert-success {
      border-left-color: #28a745;
      background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
    }
    
    .alert-curtain.alert-curtain-alert-danger {
      border-left-color: #dc3545;
      background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
    }
    
    .alert-curtain.alert-curtain-alert-warning {
      border-left-color: #ffc107;
      background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
    }
    
    .alert-curtain.alert-curtain-alert-info {
      border-left-color: #17a2b8;
      background: linear-gradient(135deg, #d1ecf1 0%, #bee5eb 100%);
    }
  `;
  document.head.appendChild(style);
}

function showAlert(message, status, autoHide = true, duration = 3000) {
  // Проверяем, не остановлена ли работа (убираем эту проверку, так как она блокирует все алерты)
  // const workStatus = document.querySelector('[data-work-status="true"]') || 
  //                   document.querySelector('.work-active') ||
  //                   window.workActive;
  
  // Если работа остановлена и это не алерт об успешном завершении, не показываем
  // if (!workStatus && !message.includes('✅ Work completed successfully') && !message.includes('Work stopped')) {
  //   console.log('[showAlert] Work stopped, skipping alert:', message);
  //   return;
  // }
  
  // Create notification container if doesn't exist
  let notificationContainer = document.getElementById('notification-container');
  if (!notificationContainer) {
    notificationContainer = document.createElement('div');
    notificationContainer.id = 'notification-container';
    notificationContainer.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 9999;
      max-width: 450px;
      max-height: 80vh;
      overflow-y: auto;
    `;
    document.body.appendChild(notificationContainer);
  }

  // Ограничиваем количество алертов до 5
  const existingAlerts = notificationContainer.querySelectorAll('.alert-curtain');
  if (existingAlerts.length >= 5) {
    // Удаляем самый старый алерт
    const oldestAlert = existingAlerts[0];
    oldestAlert.classList.add('hide');
    setTimeout(() => {
      if (oldestAlert.parentNode) {
        oldestAlert.parentNode.removeChild(oldestAlert);
      }
    }, 400);
  }

  // Создаем элемент алерта
  let elem = document.createElement('div');
  elem.className = `alert-curtain alert-curtain-${status}`;
  
  // Добавляем содержимое
  elem.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
      <div class="message-content">${message}</div>
      <button type="button" class="close">&times;</button>
    </div>
  `;
  
  notificationContainer.appendChild(elem);
  
  // Устанавливаем позицию снизу (уменьшаем отступ между алертами)
  const currentAlerts = notificationContainer.querySelectorAll('.alert-curtain');
  const alertIndex = currentAlerts.length - 1;
  elem.style.marginTop = `${alertIndex * 6}px`;
  
  // Trigger slide-in animation
  setTimeout(() => {
    elem.classList.add('show');
  }, 10);
  
  // Auto-hide functionality
  if (autoHide) {
    setTimeout(() => {
      if (elem.parentNode) {
        elem.classList.remove('show');
        elem.classList.add('hide');
        setTimeout(() => {
          if (elem.parentNode) {
            elem.parentNode.removeChild(elem);
            // После удаления алерта, сдвигаем остальные вверх
            const remainingAlerts = notificationContainer.querySelectorAll('.alert-curtain');
            remainingAlerts.forEach((alert, index) => {
              alert.style.marginTop = `${index * 6}px`;
            });
          }
        }, 400);
      }
    }, duration);
  }
  
  // Manual close button functionality
  const closeBtn = elem.querySelector('.close');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      elem.classList.remove('show');
      elem.classList.add('hide');
      setTimeout(() => {
        if (elem.parentNode) {
          elem.parentNode.removeChild(elem);
          // После удаления алерта, сдвигаем остальные вверх
          const remainingAlerts = notificationContainer.querySelectorAll('.alert-curtain');
          remainingAlerts.forEach((alert, index) => {
            alert.style.marginTop = `${index * 6}px`;
          });
        }
      }, 400);
    });
  }

  console.log(message);
  if (status === 'alert-danger') {
    console.trace('showAlert (danger):', message);
  }
}

// Функция для получения цвета статуса
function getStatusColor(status) {
  switch(status) {
    case 'alert-success':
      return '#28a745';
    case 'alert-danger':
      return '#dc3545';
    case 'alert-warning':
      return '#ffc107';
    case 'alert-info':
      return '#17a2b8';
    default:
      return '#6c757d';
  }
}

function clearAllAlerts() {
  console.log('[clearAllAlerts] Starting to clear all alerts...');
  const notificationContainer = document.getElementById('notification-container');
  if (notificationContainer) {
    const alerts = notificationContainer.querySelectorAll('.alert-curtain');
    console.log(`[clearAllAlerts] Found ${alerts.length} alerts to clear`);
    alerts.forEach((alert, index) => {
      setTimeout(() => {
        alert.classList.remove('show');
        alert.classList.add('hide');
        setTimeout(() => {
          if (alert.parentNode) {
            alert.parentNode.removeChild(alert);
            console.log(`[clearAllAlerts] Removed alert ${index + 1}`);
          }
        }, 400);
      }, index * 30); // Уменьшаем задержку для более быстрого исчезновения
    });
  } else {
    console.log('[clearAllAlerts] Notification container not found');
  }
}

export {showAlert, clearAllAlerts}