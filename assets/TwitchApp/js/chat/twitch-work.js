import {awaitAccountsPingStatus, socket, workStatus} from "./twitch-ws";
import {showAlert} from "./alert";

let workTimerId;

document.getElementById("buttonStartWork").addEventListener("click", function () {
  console.log("Start work");
  socket.send(JSON.stringify({
    "event": "TWITCH_START_WORK",
    "message": "Start work",
  }));

});

document.getElementById("buttonEndWork").addEventListener("click", function () {
  console.log("End work");
  socket.send(JSON.stringify({
    "event": "TWITCH_END_WORK",
    "message": "End work",
  }));
  document.getElementById("buttonEndWork").disabled = true
  document.getElementById("buttonStartWork").disabled = false
});

function workTimer(startTime) {
  const dateOptions = {
          year: '2-digit', month: '2-digit', day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          timeZone: "UTC"
        };
  let start = new Date(startTime)



  workTimerId = setInterval(function () {
    if (workStatus) {
      let nowTime = new Date();
      let timeDiff = new Date(Math.abs(nowTime - start));
      document.getElementById("workTimer").innerHTML = timeDiff.toLocaleDateString('ru-RU', dateOptions).substr(10, )
    }
  }, 1000);
}

export {workTimer, workTimerId}