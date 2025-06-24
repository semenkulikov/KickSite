import Chart from 'chart.js/auto';
import {socket} from "./kick-stats-ws";
import {showAlert} from "./alert";

const showMyStatBtn = document.getElementById('showMyStat');
if (showMyStatBtn) {
  showMyStatBtn.addEventListener('click', function () {
  const countStat = document.getElementById("showLastStatCount").innerText
  console.log("SHOW MY STAT")
  console.log(countStat)
  socket.send(JSON.stringify({
    "event": "KICK_STATS_SHOW",
    "message": {
      "user": "yourself",
      "count": countStat
    },
  }));
});
}

const sendShowUserStat = document.getElementById("sendShowUserStat")
if (sendShowUserStat) {
  document.getElementById('sendShowUserStat').addEventListener('click', function () {
    const countStat = document.getElementById("showLastStatCount").innerText
    const inputShowUserStatElement = document.getElementById("inputShowUserStat")
    const inputShowUserStatValue = inputShowUserStatElement.value

    if (inputShowUserStatValue && inputShowUserStatValue.trim() !== "") {
      console.log(`SHOW STAT ${inputShowUserStatValue}`)

      socket.send(JSON.stringify({
        "event": "KICK_STATS_SHOW",
        "message": {
          "user": inputShowUserStatValue,
          "count": countStat
        },
      }));
    } else {
      showAlert("Enter the username for the request", "alert-danger")
    }
  });
}

const dateOptions = {
  year: '2-digit', month: '2-digit', day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  timeZone: "UTC"
};

function showStats(data) {
  const statsContainer = document.getElementById("statsContainer")
  statsContainer.innerHTML = ""
  let statBlockBody;

  if (data.status.code === "success" && data.stat.length) {
    $.each(data.stat, function (index, value) {
      statBlockBody = prepareMarkup(index, value)
      // console.log(statBlockBody)
    })
  } else if (data.status.code === "success") {
    const statsContainer = document.getElementById("statsContainer")
    statsContainer.innerHTML = ""

    const message = document.createElement("div");
    message.className = "w-100 d-flex alert alert-warning";
    message.innerText = "There are no statistics."
    statsContainer.appendChild(message)

  } else {
    showAlert(data.status.text, "alert-danger")
  }

}

function prepareMarkup(index, value) {
  // console.log(index, value)
  const parsedData = parseData(value);
  // console.log(parsedData)
  const statsContainer = document.getElementById("statsContainer")

  const statBlock = document.createElement('div');
  statBlock.className = `row mb-2 stat-id-${index}`;

  const col = document.createElement('div');
  col.className = 'col';

  const accordion = document.createElement('div');
  accordion.className = 'accordion accordion-flush';
  accordion.id = `accordionFlushStatId${index}`;

  const accordionItem = document.createElement('div');
  accordionItem.className = 'accordion-item';

  const accordionHeader = document.createElement('h2');
  accordionHeader.className = 'accordion-header';
  accordionHeader.id = 'flush-headingOne';

  const accordionButton = document.createElement('a');
  accordionButton.className = 'accordion-button collapsed';
  accordionButton.setAttribute('type', 'button');
  accordionButton.setAttribute('data-bs-toggle', 'collapse');
  accordionButton.setAttribute('data-bs-target', `#flush-collapseOneStatId${index}`);
  accordionButton.setAttribute('aria-expanded', 'false');
  accordionButton.setAttribute('aria-controls', `flush-collapseOneStatId${index}`);
  accordionButton.textContent = `Start: ${value.start} | Channel: ${parsedData.channel} | Duration: ${value.duration} | Total messages: ${parsedData.totalMessages}`;

  const accordionCollapse = document.createElement('div');
  accordionCollapse.id = `flush-collapseOneStatId${index}`;
  accordionCollapse.className = 'accordion-collapse collapse';
  accordionCollapse.setAttribute('aria-labelledby', 'flush-headingOne');
  accordionCollapse.setAttribute('data-bs-parent', `#accordionFlushStatId${index}`);

  const accordionBody = document.createElement('div');
  accordionBody.className = 'accordion-body';

  // Chart
  const innerChartRow = document.createElement('div');
  innerChartRow.className = 'row';

  const innerChartCol = document.createElement('div');
  innerChartCol.className = 'col';

  const canvasStat = document.createElement('canvas');
  canvasStat.id = `chartStatId${index}`

  // Extra info
  const innerExtraInfoRow = document.createElement('div');
  innerExtraInfoRow.className = 'row';

  const innerExtraInfoCol = document.createElement('div');
  innerExtraInfoCol.className = 'col';

  // Extra info table

  const extraInfoTable = document.createElement('table');
  extraInfoTable.className = 'table table-striped table-dark table-hover';

  const thead = document.createElement('thead');
  const theadRow = document.createElement('tr');

  const thKey = document.createElement('th');
  thKey.textContent = 'Key';

  const thValue = document.createElement('th');
  thValue.textContent = 'Value';

  const tbody = document.createElement('tbody');

  const rowDataForTableExtraInfo = [
    { key: 'Channel', value: `${parsedData.channel}` },
    { key: 'Work Start', value: `${value.start} (HH:MM:SS)`},
    { key: 'Work End', value: `${value.end} (HH:MM:SS)`},
    { key: 'Work Duration', value: `${value.duration} (HH:MM:SS)`},
    { key: 'Total Messages', value: `${parsedData.totalMessages}`},
    { key: 'Average Messages per Minute', value: `${parsedData.averageNumberMessagesPerMinute.m}`},
    { key: 'Average Auto Messages per Minute', value: `${parsedData.averageNumberMessagesPerMinute.a}`},
  ];

  rowDataForTableExtraInfo.forEach((data) => {
    const tr = document.createElement('tr');
    const tdKey = document.createElement('td');
    tdKey.textContent = data.key;
    tdKey.classList = "text-right"
    const tdValue = document.createElement('td');
    tdValue.textContent = data.value;
    tdValue.classList = "text-left"

    tr.appendChild(tdKey);
    tr.appendChild(tdValue);
    tbody.appendChild(tr);
  });

  // Table added in stat

  theadRow.appendChild(thKey);
  theadRow.appendChild(thValue);
  thead.appendChild(theadRow);
  extraInfoTable.appendChild(thead);
  extraInfoTable.appendChild(tbody);
  innerExtraInfoCol.appendChild(extraInfoTable)
  innerExtraInfoRow.appendChild(innerExtraInfoCol)
  accordionBody.appendChild(innerExtraInfoRow)

  // Chart added in stat

  innerChartCol.appendChild(canvasStat);
  innerChartRow.appendChild(innerChartCol);
  accordionBody.appendChild(innerChartRow);
  accordionCollapse.appendChild(accordionBody);

  accordionItem.appendChild(accordionHeader);
  accordionItem.appendChild(accordionCollapse);

  accordionHeader.appendChild(accordionButton);

  accordion.appendChild(accordionItem);
  col.appendChild(accordion);
  statBlock.appendChild(col);

  statsContainer.appendChild(statBlock);

  drawStatChart(parsedData.messagesPerMinute, canvasStat)

  return {"statId": index, "statBodyBlock": accordionBody}
}

function parseData(work) {
  const messagesPerMinute = {"a": {}, "m": {}};
  let averageNumberMessagesPerMinute = {"a": {}, "m": {}};

  work.messages.forEach(message => {
    const timeParts = message.time.split(" ");
    const time = timeParts[0];
    const minute = time.substring(0, 5);
    if (messagesPerMinute[message["data"]["message_type"]][minute]) {
        messagesPerMinute[message["data"]["message_type"]][minute] += 1;
    } else {
        messagesPerMinute[message["data"]["message_type"]][minute] = 1;
    }
  });

  $.each(messagesPerMinute, function (index, value) {
    averageNumberMessagesPerMinute[index] = Math.round(Object.values(value).reduce((partialSum, a) => partialSum + a, 0) / Object.keys(value).length)
  })

  return {
    "channel": work.messages[0].data.channel,
    "totalMessages": work.messages.length,
    "messagesPerMinute": messagesPerMinute,
    "averageNumberMessagesPerMinute": averageNumberMessagesPerMinute
  }
}

function drawStatChart(data, canvas){
  // console.log(data.a, data.m)
  if (!Boolean(data.a.keys)) {
    // console.log("No auto")
    $.each(Object.keys(data.m), function (index, value) {
      data.a[value] = 0;
    });
  }
  if (Boolean(data.m.keys)) {
    // console.log("No manual")
    $.each(Object.keys(data.a), function (index, value) {
      data.m[value] = 0;
    });
  }

  const ctx = canvas.getContext('2d');

  const labels = Object.keys(data.a);
  const datasetA = {
    label: 'Auto messages',
    data: Object.values(data.a), //
    borderColor: 'rgb(255, 99, 132)',
    borderWidth: 2,
    fill: false
  };
  const datasetM = {
    label: 'Manual messages',
    data: Object.values(data.m),
    borderColor: 'rgb(54, 162, 235)',
    borderWidth: 2,
    fill: false
  };

  const myChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: labels,
        datasets: [datasetA, datasetM]
    },
    options: {
        scales: {
            x: {
                beginAtZero: true
            },
            y: {
                beginAtZero: true
            }
        }
    }
  });

}

export {showStats}