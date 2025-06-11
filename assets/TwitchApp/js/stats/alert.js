function showAlert(message, status) {
  let elem = document.createElement('div');
  elem.classList.add(`${status}`, `${status}`)
  elem.append(alertTemplate.content.cloneNode(true));
  elem.children[0].classList.add(`${status}`)
  elem.children[0].innerHTML = `<span class="alert-message">${message}</span>` + elem.children[0].innerHTML
  document.body.append(elem);

  console.log(message)
  setTimeout(function(){
     elem.remove();
  },10000);
}

export {showAlert}