import {getTwitchChannel} from "./twitch-channel-db";
import {changeViewChannel} from "./twitch-channel";
import {loadAutoMessagesData} from "./twitch-auto-messages";

document.addEventListener('DOMContentLoaded', () => {
  console.log("DOM loaded")

  console.log("Load channel")
  getTwitchChannel().then((channel) => {
    if (channel) {
      changeViewChannel(true, channel.value);
    } else {
      changeViewChannel(false);
    }
    }).catch((error) => {
    console.error('Error:', error);
  });

  console.log("Load auto-messages if exists")
  loadAutoMessagesData()

  $("#inputMessage").focus();

});