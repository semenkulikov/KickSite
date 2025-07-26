// Web Worker для обработки сообщений в фоне
self.onmessage = function(e) {
  const { type, data } = e.data;
  
  switch (type) {
    case 'PROCESS_BATCH':
      const { accounts, messages, batchSize, startIndex } = data;
      const batch = [];
      const currentTime = Date.now();
      
      for (let i = 0; i < batchSize; i++) {
        const accountIndex = (startIndex + i) % accounts.length;
        const messageIndex = Math.floor((startIndex + i) / accounts.length) % messages.length;
        
        batch.push({
          account: accounts[accountIndex],
          message: messages[messageIndex],
          messageId: currentTime + i
        });
      }
      
      self.postMessage({
        type: 'BATCH_READY',
        batch: batch,
        nextIndex: (startIndex + batchSize) % (accounts.length * messages.length)
      });
      break;
      
    default:
      console.warn('Unknown message type:', type);
  }
}; 