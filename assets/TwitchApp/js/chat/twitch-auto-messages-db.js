function openAutoMessagesDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('twitch_auto_messages_db', 1);

    request.onerror = function (event) {
      reject(event.target.error);
    };

    request.onsuccess = function (event) {
      const db = event.target.result;
      resolve(db);
    };

    request.onupgradeneeded = function (event) {
      const db = event.target.result;

      if (!db.objectStoreNames.contains('messages')) {
        db.createObjectStore('messages', { autoIncrement: true });
      }
    };
  });
}

async function getAutoMessages() {
  try {
    const db = await openAutoMessagesDB();
    const transaction = db.transaction('messages', 'readonly');
    const store = transaction.objectStore('messages');

    const request = store.getAll();

    return new Promise((resolve, reject) => {
      request.onsuccess = function (event) {
        const messages = event.target.result;
        resolve(messages);
      };

      request.onerror = function (event) {
        reject(event.target.error);
      };
    });
  } catch (error) {
    console.error('Error accessing IndexedDB:', error);
  }
}

async function addAutoMessages(messages) {
  try {
    const db = await openAutoMessagesDB();
    const transaction = db.transaction('messages', 'readwrite');
    const store = transaction.objectStore('messages');

    messages.forEach((message) => {
      store.add(message);
    });

    return new Promise((resolve, reject) => {
      transaction.oncomplete = function () {
        resolve('Messages added');
      };

      transaction.onerror = function (event) {
        reject(event.target.error);
      };
    });
  } catch (error) {
    console.error('Error accessing IndexedDB:', error);
  }
}

async function clearAllAutoMessages() {
  try {
    const db = await openAutoMessagesDB();
    const transaction = db.transaction('messages', 'readwrite');
    const store = transaction.objectStore('messages');

    const request = store.clear();

    return new Promise((resolve, reject) => {
      request.onsuccess = function () {
        resolve('All messages cleared');
      };

      request.onerror = function (event) {
        reject(event.target.error);
      };
    });
  } catch (error) {
    console.error('Error accessing IndexedDB:', error);
  }
}

export {getAutoMessages, addAutoMessages, clearAllAutoMessages}