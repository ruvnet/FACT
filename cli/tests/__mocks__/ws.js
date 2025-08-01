/**
 * Mock for WebSocket (ws) module
 */

class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = 1; // OPEN state
    setTimeout(() => {
      if (this.onopen) this.onopen();
    }, 0);
  }

  send(data) {
    // Mock send
    setTimeout(() => {
      if (this.onmessage) {
        this.onmessage({ data: JSON.stringify({ response: 'mock' }) });
      }
    }, 0);
  }

  close() {
    this.readyState = 3; // CLOSED state
    if (this.onclose) this.onclose();
  }

  on(event, handler) {
    if (event === 'open') this.onopen = handler;
    if (event === 'message') this.onmessage = handler;
    if (event === 'close') this.onclose = handler;
    if (event === 'error') this.onerror = handler;
  }
}

class MockWebSocketServer {
  constructor(options) {
    this.options = options;
    this.clients = new Set();
  }

  on(event, handler) {
    if (event === 'connection') {
      // Mock a connection
      setTimeout(() => {
        const mockClient = new MockWebSocket();
        this.clients.add(mockClient);
        handler(mockClient, { socket: { remoteAddress: '127.0.0.1' } });
      }, 0);
    }
  }

  close() {
    this.clients.clear();
  }
}

module.exports = {
  WebSocket: MockWebSocket,
  WebSocketServer: MockWebSocketServer,
  default: MockWebSocket,
};