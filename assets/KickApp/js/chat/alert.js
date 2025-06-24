function showAlert(message, status) {
  // Create notification container if doesn't exist
  let notificationContainer = document.getElementById('notification-container');
  if (!notificationContainer) {
    notificationContainer = document.createElement('div');
    notificationContainer.id = 'notification-container';
    notificationContainer.style.cssText = `
      position: fixed;
      top: 10px;
      right: 10px;
      z-index: 9999;
      max-width: 400px;
    `;
    document.body.appendChild(notificationContainer);
  }

  let elem = document.createElement('div');
  elem.classList.add(`${status}`, `${status}`)
  elem.append(alertTemplate.content.cloneNode(true));
  elem.children[0].classList.add(`${status}`)
  elem.children[0].innerHTML = `<span class="alert-message">${message}</span>` + elem.children[0].innerHTML
  
  // Add margin for spacing between notifications
  elem.style.cssText = `
    margin-bottom: 10px;
    position: relative;
    animation: slideIn 0.3s ease-out;
  `;
  
  // Add to container instead of body
  notificationContainer.appendChild(elem);

  console.log(message)
  if (status === 'alert-danger') {
    console.trace('showAlert (danger):', message);
  }
  setTimeout(function(){
     elem.style.animation = 'slideOut 0.3s ease-in';
     setTimeout(() => {
       if (elem.parentNode) {
         elem.remove();
       }
     }, 300);
  }, 6000);
}

export {showAlert}