function openFrequencyDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('kick_frequency_db', 1);

    request.onerror = function (event) {
      reject(event.target.error);
    };

    request.onsuccess = function (event) {
      const db = event.target.result;
      resolve(db);
    };

    request.onupgradeneeded = function (event) {
      const db = event.target.result;

      if (!db.objectStoreNames.contains('frequency')) {
        db.createObjectStore('frequency', { keyPath: "id" });
      }
    };
  });
}

async function getFrequency() {
  try {
    const db = await openFrequencyDB();
    const transaction = db.transaction('frequency', 'readonly');
    const store = transaction.objectStore('frequency');

    const request = store.get("frequency");

    return new Promise((resolve, reject) => {
      request.onsuccess = function (event) {
        const frequency = event.target.result;
        resolve(frequency);
      };

      request.onerror = function (event) {
        reject(event.target.error);
      };
    });
  } catch (error) {
    console.error('Error accessing IndexedDB:', error);
  }
}

function addOrUpdateFrequencyDB(data) {
    const request = indexedDB.open('kick_frequency_db', 1);

    request.onsuccess = function () {
        const db = request.result;
        const transaction = db.transaction('frequency', "readwrite");
        const store = transaction.objectStore('frequency');

        const getRequest = store.get('frequency');

        getRequest.onsuccess = function () {
            const existingData = getRequest.result;
            if (existingData) {
                existingData.value = data;
                const updateRequest = store.put(existingData);
                updateRequest.onsuccess = function () {
                    console.log("Data updated successfully");
                };
            } else {
                const newData = { id:'frequency', value: data };
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

export {getFrequency, addOrUpdateFrequencyDB}