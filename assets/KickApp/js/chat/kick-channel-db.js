function openKickChannelDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('kick_channel_db', 1);

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

async function getKickChannel() {
    try {
        const db = await openKickChannelDB();
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

function addOrUpdateKickChannelDB(data) {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('kick_channel_db', 1);

        request.onerror = function (event) {
            reject(event.target.error);
        };

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
                        resolve();
                    };
                    updateRequest.onerror = function (event) {
                        reject(event.target.error);
                    };
                } else {
                    const newData = { id:'channel', value: data };
                    const addRequest = store.add(newData);
                    addRequest.onsuccess = function () {
                        console.log("Data added successfully");
                        resolve();
                    };
                    addRequest.onerror = function (event) {
                        reject(event.target.error);
                    };
                }
            };

            getRequest.onerror = function (event) {
                reject(event.target.error);
            };

            transaction.oncomplete = function () {
                console.log("Transaction completed");
                db.close();
            };
        };
    });
}

export {getKickChannel, addOrUpdateKickChannelDB}