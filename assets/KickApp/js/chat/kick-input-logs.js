function addMessageToLogs(data) {
    const textAreaInputLogs = document.getElementById("inputLogs");

    // Создаем временную метку
    const now = new Date();
    const timestamp = now.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    
    // Формируем сообщение с временной меткой и каналом
    let message = `[${timestamp}] ${data.account}${data.auto ? '(auto)' : ''} → ${data.channel}: ${data.message}`;
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