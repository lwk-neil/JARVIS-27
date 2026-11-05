const tokenField = document.getElementById("token");
const status = document.getElementById("status");

chrome.storage.local.get(["token", "tabId"], (saved) => {
  if (saved.token) tokenField.value = saved.token;
  if (saved.tabId !== undefined) refreshStatus();
});

async function refreshStatus() {
  const reply = await chrome.runtime.sendMessage({ type: "status" });
  if (reply?.error) {
    status.textContent = `Syke bridge: ${reply.error}`;
  } else if (!reply?.connected) {
    status.textContent = "Syke bridge: no tab is currently connected.";
  } else {
    const page = reply.title || reply.url || "active website";
    status.textContent =
      `Connected to ${page}. ${reply.queued} queued, ${reply.running} running.`;
  }
}

document.getElementById("connect").addEventListener("click", async () => {
  const token = tokenField.value.trim();
  if (token.length < 32) {
    status.textContent = "Enter the pairing token from Syke's local token file.";
    return;
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !Number.isInteger(tab.id) || !tab.url || !/^https?:/.test(tab.url)) {
    status.textContent = "This page cannot be paired. Open a regular website and try again.";
    return;
  }

  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => true
    });
    await chrome.storage.local.set({ token, tabId: tab.id });
    const reply = await chrome.runtime.sendMessage({ type: "connect", tabId: tab.id });
    if (reply?.error) {
      status.textContent = reply.error;
    } else {
      await refreshStatus();
    }
  } catch (error) {
    status.textContent = `Could not connect this tab: ${error.message}`;
  }
});

document.getElementById("disconnect").addEventListener("click", async () => {
  const { tabId } = await chrome.storage.local.get("tabId");
  if (!Number.isInteger(tabId)) {
    status.textContent = "No tab is currently paired.";
    return;
  }
  const reply = await chrome.runtime.sendMessage({ type: "disconnect", tabId });
  status.textContent = reply?.error || "This tab is disconnected from Syke.";
});

document.getElementById("refresh").addEventListener("click", refreshStatus);
