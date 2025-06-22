import {addOrUpdateKickChannelDB} from "./kick-channel-db";
import {showAlert} from "./alert";
import {socket} from "./kick-ws";

$('#changeChannel').on('click', function() {
  changeChannel()
  setTimeout(function() { $('#editChannelModal').modal('hide'); }, 2);
});

async function changeViewChannel(status, channel = undefined) {
    const elementSelectedChannel = document.getElementById("selectedChannel");
    if (status) {
        channel = (channel || "").trim();
        $("#selectedChannel").removeClass();
        elementSelectedChannel.href = `https://kick.com/${encodeURIComponent(channel)}`
        elementSelectedChannel.target = "_blank"
        elementSelectedChannel.innerHTML = `<span>${channel}</span>`;
        elementSelectedChannel.dataset.status = "selected";
        elementSelectedChannel.classList.add("channel_is-selected");

        const streamEmbedElem = document.getElementById("chat-embed");
        if (streamEmbedElem) {
            const channelNameWithoutSpaces = channel.replace(/\s/g, '');
            streamEmbedElem.src = `https://kick.com/popout/${encodeURIComponent(channelNameWithoutSpaces.toLowerCase())}/chat`;
        }

        await addOrUpdateKickChannelDB(channel);
    } else {
        $("#selectedChannel").removeClass();
        elementSelectedChannel.innerHTML = "Not selected";
        elementSelectedChannel.dataset.status = "not-selected";
        elementSelectedChannel.classList.add("channel_is-not-selected");
    }
    return true;
}

function changeChannel() {
  const linkPattern = /^https?:\/\/\S+/i;
  let inputChannel = document.getElementById("inputChannel").value

  if (inputChannel && inputChannel.trim() !== "") {
    inputChannel = inputChannel.trim();
    if (inputChannel.startsWith("@")) {
      inputChannel = inputChannel.slice(1);
    }
    if (linkPattern.test(inputChannel)) {
      let splitInputChannel = inputChannel.split('/')
      inputChannel = splitInputChannel[splitInputChannel.length - 1]
    }
    inputChannel = inputChannel.replace(/^@+/, '');
    addOrUpdateKickChannelDB(inputChannel);
    changeViewChannel(true, inputChannel);
    showAlert("Channel changed successfully", "alert-success")
    if (window.socket && window.socket.readyState === 1) {
      window.socket.send(JSON.stringify({
        "event": "KICK_SELECT_CHANNEL",
        "message": {"channel": inputChannel}
      }));
    } else if (socket && socket.readyState === 1) {
      socket.send(JSON.stringify({
        "event": "KICK_SELECT_CHANNEL",
        "message": {"channel": inputChannel}
      }));
    } else {
      showAlert("WebSocket is not connected!", "alert-danger");
    }
  } else {
    showAlert("Are you trying to save an empty channel", "alert-danger")
  }
}

export {changeViewChannel, changeChannel}
window.changeChannel = changeChannel;