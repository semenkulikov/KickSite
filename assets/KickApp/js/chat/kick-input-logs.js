function addMessageToLogs(data) {
    const textAreaInputLogs = document.getElementById("inputLogs");

    let message = `${data.account}${data.auto ? '(auto)' : ''}: ${data.message}`
    console.log(message)
    
    // Проверяем, существует ли элемент перед обращением к его свойствам
    if (textAreaInputLogs) {
    if (textAreaInputLogs.value !== "") {
        textAreaInputLogs.value =  textAreaInputLogs.value + '\n' + message;
    } else {
        textAreaInputLogs.value = message;
    }
    textAreaInputLogs.scrollTop = textAreaInputLogs.scrollHeight;
    } else {
        console.log('[addMessageToLogs] Element with id "inputLogs" not found in DOM');
    }
}

export {addMessageToLogs}