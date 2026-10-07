const select = (selector) => document.querySelector(selector);
const panel = select("#chat-panel");
const toggle = select("#chat-toggle");
const closeButton = select("#chat-close");
const form = select("#chat-form");
const input = select("#chat-input");
const log = select("#chat-log");

toggle?.addEventListener("click", () => {
  panel.classList.remove("hidden");
  input.focus();
});
closeButton?.addEventListener("click", () => panel.classList.add("hidden"));

function csrfToken() {
  return document.cookie
    .split("; ")
    .find((part) => part.startsWith("csrftoken="))
    ?.split("=")[1] || "";
}

function addBubble(message, type, sources = []) {
  const element = document.createElement("div");
  element.className = `bubble ${type}`;
  element.textContent = message;
  if (sources.length) {
    const sourceBox = document.createElement("small");
    sourceBox.append("Sources: ");
    sources.forEach((source, index) => {
      if (index) sourceBox.append(" · ");
      if (/^(https?:\/\/|\/)/i.test(source)) {
        const link = document.createElement("a");
        link.href = source;
        link.textContent = source;
        link.target = source.startsWith("http") ? "_blank" : "_self";
        link.rel = "noopener noreferrer";
        sourceBox.append(link);
      } else {
        sourceBox.append(source);
      }
    });
    element.appendChild(sourceBox);
  }
  log.appendChild(element);
  log.scrollTop = log.scrollHeight;
  return element;
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  addBubble(message, "user");
  input.value = "";
  input.disabled = true;
  const loading = addBubble("Thinking...", "bot loading");
  try {
    const response = await fetch("/knowledge/chat/", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
      body: JSON.stringify({message}),
    });
    const data = await response.json();
    loading.remove();
    addBubble(data.answer || data.error || "No response was returned.", "bot", data.sources || []);
  } catch (error) {
    loading.remove();
    addBubble("I could not connect. Please try again.", "bot");
  } finally {
    input.disabled = false;
    input.focus();
  }
});
