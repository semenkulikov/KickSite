import {awaitAccountsPingStatus, getKickSocket, workStatus} from "./kick-ws";
import {showAlert} from "./alert";

let workTimerId;

const startWorkBtn = document.getElementById("buttonStartWork");
if (startWorkBtn) {
  startWorkBtn.classList.add('btn', 'btn-success', 'mb-2', 'w-100');
  startWorkBtn.addEventListener("click", function () {
    console.log("Start work");
    getKickSocket().send(JSON.stringify({
      "event": "KICK_START_WORK",
      "message": "Start work",
    }));
  });
}

const endWorkBtn = document.getElementById("buttonEndWork");
if (endWorkBtn) {
  endWorkBtn.classList.add('btn', 'btn-danger', 'mb-2', 'w-100');
  endWorkBtn.addEventListener("click", function () {
    console.log("End work");
    getKickSocket().send(JSON.stringify({
      "event": "KICK_END_WORK",
      "message": "End work",
    }));
    document.getElementById("buttonEndWork").disabled = true
    document.getElementById("buttonStartWork").disabled = false
  });
}

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