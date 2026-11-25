const chat = document.querySelector("#chat-messages");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#chat-input");
const send = document.querySelector("#send-button");
const conversation = [];

function append(role, text, modifier = "") {
  const row = document.createElement("div");
  row.className = `message ${role}${modifier ? ` ${modifier}` : ""}`;
  row.innerHTML = role === "user"
    ? "<div><small>You</small><p></p></div>"
    : "<span>✳</span><div><small>Taskflow AI</small><p></p></div>";
  row.querySelector("p").textContent = text;
  chat.append(row);
  chat.scrollTop = chat.scrollHeight;
  return row;
}

async function api(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
  const data = await response.json().catch(() => ({error: "Invalid server response."}));
  if (!response.ok) throw new Error(data.error || "Request failed.");
  if (typeof data.reply !== "string") throw new Error("The server returned an invalid response.");
  return data;
}

async function sendMessage(message) {
  const content = message.trim();
  if (!content || send.disabled) return;

  input.value = "";
  send.disabled = true;
  const userMessage = {role: "user", content};
  append("user", content);
  const thinking = append("assistant", "Thinking…", "loading");
  try {
    const data = await api("/api/chat", {messages: [...conversation, userMessage]});
    thinking.classList.remove("loading");
    thinking.querySelector("p").textContent = data.reply;
    conversation.push(userMessage, {role: "assistant", content: data.reply});
    for (const confirmation of data.confirmations || []) showConfirmation(confirmation);
  } catch (error) {
    thinking.classList.remove("loading");
    thinking.classList.add("error");
    thinking.querySelector("p").textContent = error.message || "The assistant request failed.";
  } finally {
    send.disabled = false;
    input.focus();
  }
}

function showConfirmation(item) {
  const card = document.createElement("div");
  card.className = "confirmation-card";
  card.innerHTML = '<div></div><div class="confirmation-actions"><button class="confirm-delete" type="button">Confirm delete</button><button class="cancel-delete" type="button">Keep task</button></div>';
  card.firstElementChild.textContent = `Delete "${item.task}"? Please confirm.`;
  card.querySelector(".cancel-delete").addEventListener("click", () => card.remove());
  card.querySelector(".confirm-delete").addEventListener("click", async () => {
    const button = card.querySelector(".confirm-delete");
    button.disabled = true;
    try {
      const response = await fetch(`/api/tasks/${item.task_id}`, {
        method: "DELETE",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({confirm: true})
      });
      const data = await response.json().catch(() => ({error: "Invalid server response."}));
      if (!response.ok) throw new Error(data.error || "Could not delete task.");
      card.remove();
      append("assistant", data.message);
    } catch (error) {
      button.disabled = false;
      append("assistant", error.message || "Could not delete task.", "error");
    }
  });
  chat.append(card);
  chat.scrollTop = chat.scrollHeight;
}

async function checkHealth() {
  const status = document.querySelector("#model-status");
  const indicator = status.querySelector("i");
  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Ollama is unavailable.");
    status.lastChild.textContent = ` Connected · ${data.model}`;
    indicator.classList.add("connected");
  } catch (error) {
    status.lastChild.textContent = ` ${error.message || "Could not check the local model."}`;
    indicator.classList.add("disconnected");
  }
}

form.addEventListener("submit", event => {
  event.preventDefault();
  sendMessage(input.value);
});
document.querySelector("#suggestions").addEventListener("click", event => {
  const button = event.target.closest("button[data-prompt]");
  if (button) sendMessage(button.dataset.prompt);
});
document.querySelector("#new-chat-button").addEventListener("click", () => {
  conversation.length = 0;
  chat.innerHTML = '<div class="message assistant"><span>✳</span><div><small>Taskflow AI</small><p>New conversation started. What would you like to do?</p></div></div>';
});
document.querySelector("#today-label").textContent = new Intl.DateTimeFormat(undefined, {
  weekday: "short", month: "short", day: "numeric"
}).format(new Date());
checkHealth();
