function openTwitchChannelDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('twitch_channel_db', 1);

    request.onerror = function (event) {
      reject(event.target.error);
    };

    request.onsuccess = function (event) {
      const db = event.target.result;
      resolve(db);
    };

    request.onupgradeneeded = function (event) {
      const db = event.target.result;

      if (!db.objectStoreNames.contains('channel')) {
        db.createObjectStore("channel", { keyPath: "id" });
      }
    };
  });
}

async function getTwitchChannel() {
    try {
        const db = await openTwitchChannelDB();
        const transaction = db.transaction('channel', 'readonly');
        const store = transaction.objectStore('channel');

        const request = store.get("channel");

        return new Promise((resolve, reject) => {
            request.onsuccess = function (event) {
                const channel = event.target.result;
                resolve(channel);
            };

            request.onerror = function (event) {
                reject(event.target.error);
            };
        });
    } catch (error) {
        console.error('Error accessing IndexedDB:', error);
    }
}

function addOrUpdateTwitchChannelDB(data) {
    const request = indexedDB.open('twitch_channel_db', 1);

    request.onsuccess = function () {
        const db = request.result;
        const transaction = db.transaction('channel', "readwrite");
        const store = transaction.objectStore('channel');

        const getRequest = store.get('channel');

        getRequest.onsuccess = function () {
            const existingData = getRequest.result;
            if (existingData) {
                existingData.value = data;
                const updateRequest = store.put(existingData);
                updateRequest.onsuccess = function () {
                    console.log("Data updated successfully");
                };
            } else {
                const newData = { id:'channel', value: data };
                const addRequest = store.add(newData);
                addRequest.onsuccess = function () {
                    console.log("Data added successfully");
                };
            }
        };

        transaction.oncomplete = function () {
            console.log("Transaction completed");
            db.close();
            return true
        };
    };
}

export {getTwitchChannel, addOrUpdateTwitchChannelDB}