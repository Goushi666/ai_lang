/**
 * Agent SSE 流式调试：默认关闭，避免刷屏。
 * 开启方式（任选其一）：
 * - 地址栏加参数：?agentStreamDebug=1
 * - 控制台执行：localStorage.setItem('agentStreamDebug','1') 后刷新
 * 关闭：localStorage.removeItem('agentStreamDebug')
 */

export function isAgentStreamDebug() {
  if (typeof window === "undefined") return false;
  try {
    if (window.sessionStorage?.getItem("agentStreamDebug") === "1") return true;
    if (window.localStorage?.getItem("agentStreamDebug") === "1") return true;
  } catch {
    /* private mode */
  }
  try {
    return new URLSearchParams(window.location.search).get("agentStreamDebug") === "1";
  } catch {
    return false;
  }
}

let _didHint;

export function agentStreamDbg(label, payload) {
  if (!isAgentStreamDebug()) return;
  if (!_didHint) {
    _didHint = true;
    console.info(
      "[agent-stream] 调试已开启。若控制台出现 all.js、HTMLBodyElement 等报错，多为浏览器扩展注入脚本，可用无痕窗口或禁用扩展对比。",
    );
  }
  if (payload !== undefined) {
    console.debug(`[agent-stream] ${label}`, payload);
  } else {
    console.debug(`[agent-stream] ${label}`);
  }
}
