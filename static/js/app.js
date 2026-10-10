const select = (selector) => document.querySelector(selector);
const panel = select("#chat-panel");
const toggle = select("#chat-toggle");
const closeButton = select("#chat-close");
const form = select("#chat-form");
const input = select("#chat-input");
const log = select("#chat-log");

function setChatOpen(open) {
  if (!panel) return;
  panel.classList.toggle("hidden", !open);
  toggle?.setAttribute("aria-expanded", String(open));
  if (open) input?.focus();
  else toggle?.focus();
}

toggle?.addEventListener("click", () => setChatOpen(panel?.classList.contains("hidden")));
closeButton?.addEventListener("click", () => setChatOpen(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && panel && !panel.classList.contains("hidden")) {
    setChatOpen(false);
  }
});

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

/* Category strip: scroll by buttons, keyboard, touch, or trackpad. */
document.addEventListener("DOMContentLoaded", () => {
  const track = document.getElementById("category-nav-track");
  const left = document.getElementById("category-scroll-left");
  const right = document.getElementById("category-scroll-right");
  if (!track || !left || !right) return;

  const updateButtons = () => {
    const max = Math.max(0, track.scrollWidth - track.clientWidth);
    const hasOverflow = max > 2;
    left.hidden = !hasOverflow;
    right.hidden = !hasOverflow;
    left.disabled = track.scrollLeft <= 2;
    right.disabled = track.scrollLeft >= max - 2;
  };

  const scrollCategories = (direction) => {
    const distance = Math.max(200, track.clientWidth * 0.7);
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    track.scrollBy({left: direction * distance, behavior: reduceMotion ? "auto" : "smooth"});
  };

  left.addEventListener("click", () => scrollCategories(-1));
  right.addEventListener("click", () => scrollCategories(1));
  track.addEventListener("scroll", updateButtons, {passive: true});
  window.addEventListener("resize", updateButtons);
  if ("ResizeObserver" in window) {
    new ResizeObserver(updateButtons).observe(track);
  }
  updateButtons();
});
