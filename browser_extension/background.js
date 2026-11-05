const BRIDGE = "http://127.0.0.1:18765";
let polling = false;

async function bridgeFetch(path, token, options = {}) {
  return fetch(`${BRIDGE}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(options.headers || {})
    }
  });
}

async function connect(tabId) {
  const tab = await chrome.tabs.get(tabId);
  const { token } = await chrome.storage.local.get("token");
  if (!token) throw new Error("Pairing token is missing.");
  const origin = new URL(tab.url).origin;
  const response = await bridgeFetch("/register", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tab_id: tabId, url: tab.url, title: tab.title })
  });
  if (!response.ok) throw new Error(`Syke bridge returned HTTP ${response.status}.`);
  await chrome.storage.local.set({ token, tabId, pairedOrigin: origin });
  startPolling();
}

async function disconnect(tabId) {
  const { token } = await chrome.storage.local.get("token");
  if (token) {
    await bridgeFetch("/disconnect", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tab_id: tabId })
    });
  }
  await chrome.storage.local.remove("tabId");
  await chrome.storage.local.remove("pairedOrigin");
}

function runPageAction(command) {
  const { action, parameters = {} } = command;
  const normalize = (value) => String(value || "").trim().toLowerCase();
  const visibleText = (element) =>
    normalize(element.innerText || element.value || element.getAttribute("aria-label"));
  const elements = [...document.querySelectorAll(
    "input, textarea, select, button, a, [role], [contenteditable='true'], label"
  )];
  const findText = (text) => {
    const wanted = normalize(text);
    return elements.find((element) => visibleText(element) === wanted) ||
      elements.find((element) => visibleText(element).includes(wanted));
  };
  const findInput = (description) => {
    const wanted = normalize(description);
    const byLabel = [...document.querySelectorAll("label")].find((label) =>
      normalize(label.innerText).includes(wanted)
    );
    if (byLabel) {
      const field = byLabel.control || byLabel.querySelector("input,textarea,select");
      if (field) return field;
    }
    return [...document.querySelectorAll(
      "input:not([type=hidden]), textarea, select, [contenteditable='true']"
    )].find((element) =>
      normalize(element.placeholder).includes(wanted) ||
      normalize(element.getAttribute("aria-label")).includes(wanted) ||
      normalize(element.getAttribute("name")).includes(wanted)
    );
  };
  const setField = (element, value) => {
    if (element.matches("select")) {
      const option = [...element.options].find((item) =>
        normalize(item.value) === normalize(value) ||
        normalize(item.textContent) === normalize(value)
      );
      if (!option) throw new Error(`No option matches "${value}".`);
      element.value = option.value;
    } else if (element.matches("input[type=checkbox], input[type=radio]")) {
      element.checked = value === true ||
        (typeof value === "string" &&
          ["true", "yes", "1", "checked"].includes(normalize(value)));
    } else if (element.isContentEditable) {
      element.textContent = String(value);
    } else {
      const prototype = element instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(prototype, "value").set.call(element, String(value));
    }
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  };

  if (action === "get_url") return location.href;
  if (action === "get_text") return (document.body?.innerText || "").slice(0, 4000);
  if (action === "click" || action === "smart_click") {
    const target = action === "click" ? parameters.text : parameters.description;
    const element = action === "click" && parameters.selector
      ? document.querySelector(parameters.selector)
      : target ? findText(target) : null;
    if (!element) throw new Error("Could not find the requested page element.");
    element.click();
    return "Click dispatched; inspect the page to verify its result.";
  }
  if (action === "type" || action === "smart_type") {
    const element = action === "type" && parameters.selector
      ? document.querySelector(parameters.selector)
      : action === "type" && !parameters.description
        ? document.activeElement
        : findInput(parameters.description);
    if (!element) throw new Error("Could not find the requested input.");
    if (action === "type" && !parameters.clear_first) {
      setField(element, `${element.value || ""}${parameters.text || ""}`);
    } else {
      setField(element, parameters.text || "");
    }
    return "Text entered; inspect the field to verify its value.";
  }
  if (action === "fill_form") {
    const results = [];
    for (const [selector, value] of Object.entries(parameters.fields || {})) {
      try {
        const element = document.querySelector(selector);
        if (!element) throw new Error("element not found");
        setField(element, value);
        results.push(`Filled ${selector}`);
      } catch (error) {
        results.push(`Could not fill ${selector}: ${error.message}`);
      }
    }
    return results.length ? results.join("; ") : "No form fields were supplied.";
  }
  if (action === "scroll") {
    window.scrollBy(0, (parameters.direction === "up" ? -1 : 1) *
      Math.max(0, Number(parameters.amount) || 500));
    return `Scrolled ${parameters.direction || "down"}.`;
  }
  if (action === "press") {
    const key = parameters.key || "Enter";
    const target = document.activeElement || document.body;
    if (key === "Enter" && target.closest("form")) {
      target.closest("form").requestSubmit();
      return "Form submission requested; inspect the page to verify its result.";
    }
    target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
    target.dispatchEvent(new KeyboardEvent("keyup", { key, bubbles: true }));
    return `Sent ${key} to the focused element.`;
  }
  throw new Error(`Unsupported current-tab action: ${action}`);
}

async function poll() {
  if (polling) return;
  polling = true;
  try {
    while (true) {
      const { token, tabId } = await chrome.storage.local.get(["token", "tabId"]);
      if (!token || !Number.isInteger(tabId)) return;
      let response;
      try {
        response = await bridgeFetch("/next", token, {
          headers: { "X-Syke-Tab-Id": String(tabId) },
          signal: AbortSignal.timeout(25000)
        });
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        continue;
      }
      if (!response.ok) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        continue;
      }
      const command = await response.json();
      if (!command.job_id) continue;

      let result;
      try {
        const tab = await chrome.tabs.get(tabId);
        if (!tab.url || !/^https?:/.test(tab.url)) {
          throw new Error("The paired tab is no longer a regular website.");
        }
        const [execution] = await chrome.scripting.executeScript({
          target: { tabId },
          func: runPageAction,
          args: [command]
        });
        result = execution.result;
      } catch (error) {
        result = `Browser extension could not act on the paired tab: ${error.message}`;
      }

      await bridgeFetch("/result", token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: command.job_id, result })
      }).catch(() => {});
    }
  } finally {
    polling = false;
  }
}

function startPolling() {
  void poll();
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "disconnect") {
    disconnect(message.tabId)
      .then(() => sendResponse({ connected: false }))
      .catch((error) => sendResponse({ error: error.message }));
    return true;
  }
  if (message?.type !== "connect") return;
  connect(message.tabId)
    .then(() => sendResponse({ connected: true }))
    .catch((error) => sendResponse({ error: error.message }));
  return true;
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "status") return;
  void chrome.storage.local.get("token").then(async ({ token }) => {
    if (!token) throw new Error("Pair this tab with Syke first.");
    const response = await bridgeFetch("/status", token);
    if (!response.ok) throw new Error(`Syke bridge returned HTTP ${response.status}.`);
    sendResponse(await response.json());
  }).catch((error) => sendResponse({ error: error.message }));
  return true;
});

chrome.alarms.create("syke-bridge-poll", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(startPolling);

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (!changeInfo.url && !changeInfo.title) return;
  void chrome.storage.local.get(["tabId", "pairedOrigin"]).then((saved) => {
    if (saved.tabId !== tabId) return;
    let changedOrigin = true;
    try {
      changedOrigin = changeInfo.url
        ? new URL(changeInfo.url).origin !== saved.pairedOrigin
        : false;
    } catch {
      changedOrigin = true;
    }
    if (changedOrigin) return disconnect(tabId);
    return chrome.tabs.get(tabId).then((tab) =>
      chrome.storage.local.get("token").then(({ token }) =>
        token && bridgeFetch("/register", token, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tab_id: tabId,
            url: tab.url,
            title: tab.title
          })
        })
      )
    );
  }).catch((error) => console.error("Could not update Syke tab status:", error));
});

chrome.tabs.onRemoved.addListener((tabId) => {
  void chrome.storage.local.get("tabId").then((saved) => {
    if (saved.tabId === tabId) return disconnect(tabId);
  }).catch((error) => console.error("Could not disconnect closed Syke tab:", error));
});
