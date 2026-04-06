class WebSocketClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.listeners = new Map();
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      // 心跳保活（与后端 manager 的 ping 兼容）
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };

    this.ws.onclose = () => {
      this.reconnect();
    };

    this.ws.onerror = (error) => {
      // eslint-disable-next-line no-console
      console.error("WebSocket错误:", error);
    };
  }

  startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);
  }

  reconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.connect();
      this.reconnectTimer = null;
    }, 5000);
  }

  handleMessage(data) {
    const { type, payload } = data;
    const listeners = this.listeners.get(type) || [];
    listeners.forEach((callback) => callback(payload));
  }

  on(type, callback) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type).push(callback);
  }

  /** 移除与 on 成对注册的处理函数，避免热更新或重复挂载导致同一告警多次弹窗 */
  off(type, callback) {
    const listeners = this.listeners.get(type);
    if (!listeners) return;
    const i = listeners.indexOf(callback);
    if (i !== -1) listeners.splice(i, 1);
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  close() {
    clearInterval(this.heartbeatTimer);
    clearTimeout(this.reconnectTimer);
    this.ws?.close();
  }
}

export default WebSocketClient;

