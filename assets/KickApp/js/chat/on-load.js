import {getKickChannel} from "./kick-channel-db";
import {changeViewChannel} from "./kick-channel";
import {loadAutoMessagesData} from "./kick-auto-messages";

document.addEventListener('DOMContentLoaded', () => {
  console.log("DOM loaded")

  console.log("Load channel")
  getKickChannel().then((channel) => {
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