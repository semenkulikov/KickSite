import {showStats} from "./show";

const loc = window.location;
let wsStart = 'ws://';

if (loc.protocol === 'https:') {
    wsStart = 'wss://'
}

let endpoint = wsStart + loc.host + '/ws-twitch/stats';
const socket = new WebSocket(endpoint);

function connect() {
  socket.onopen = function open() {
    console.log('WebSockets connection created.');
    socket.send(JSON.stringify({
      "event": "TWITCH_CONNECT",
      "message": "HELLO",
    }));
  };

  socket.onclose = function (e) {
    console.log('Socket is closed. Reconnect will be attempted in 1 second.', e.reason);
    setTimeout(function () {
      connect();
    }, 1000);
  };

  socket.onmessage = function (e) {
    // On getting the message from the server
    // Do the appropriate steps on each event.
    let data = JSON.parse(e.data);
    data = data["payload"];
    let message = data['message'];
    let event = data["event"];

    switch (event) {
      case 'TWITCH':
        break;
      case 'TWITCH_STATS_SHOW':
        console.log("SHOW STATS")
        showStats(message)
        break;
      default:
        console.log("No event")
    }
  };

  if (socket.readyState == WebSocket.OPEN) {
    socket.onopen(this);
  }
}

export {connect, socket}