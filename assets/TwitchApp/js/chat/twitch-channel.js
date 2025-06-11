import {showAlert} from "./alert";
import {addOrUpdateTwitchChannelDB} from "./twitch-channel-db";

$('#changeChannel').on('click', function() {
  changeChannel()
  setTimeout(function() { $('#editChannelModal').modal('hide'); }, 2);
});

function changeViewChannel(status, channel = undefined) {
    const elementSelectedChannel = document.getElementById("selectedChannel");
    if (status) {
        $("#selectedChannel").removeClass();
        elementSelectedChannel.href = `https://www.twitch.tv/${channel}`
        elementSelectedChannel.target = "_blank"
        elementSelectedChannel.innerHTML = `<span>${channel}</span>`;
        elementSelectedChannel.dataset.status = "selected";
        elementSelectedChannel.classList.add("channel_is-selected");

        const streamEmbedElem = document.getElementById("chat-embed");
        if (streamEmbedElem) {
            //document.getElementById("stream-embed").src = `https://player.twitch.tv/?channel=${channel}&parent=${window.location.hostname}`;
            document.getElementById("chat-embed").src = `https://www.twitch.tv/embed/${channel}/chat?darkpopout&parent=${window.location.hostname}`;
        }

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
    if (linkPattern.test(inputChannel)) {
      let splitInputChannel = inputChannel.split('/')
      inputChannel = splitInputChannel[splitInputChannel.length - 1]
    }
    addOrUpdateTwitchChannelDB(inputChannel);
    changeViewChannel(true, inputChannel);
    showAlert("Channel changed successfully", "alert-success")
  } else {
    showAlert("Are you trying to save an empty channel", "alert-danger")
  }
}

export {changeViewChannel}