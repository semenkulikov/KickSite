function addMessageToLogs(data) {
    const textAreaInputLogs = document.getElementById("inputLogs");

    let message = `${data.account}${data.auto ? '(auto)' : ''}: ${data.message}`
    console.log(message)
    if (textAreaInputLogs.value !== "") {
        textAreaInputLogs.value =  textAreaInputLogs.value + '\n' + message;
    } else {
        textAreaInputLogs.value = message;
    }
    textAreaInputLogs.scrollTop = textAreaInputLogs.scrollHeight;
}

export {addMessageToLogs}