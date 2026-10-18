const chatMessages = document.getElementById("chatMessages");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const typingIndicator = document.getElementById("typingIndicator");
const conversationList = document.getElementById("conversationList");
const newChatBtn = document.getElementById("newChatBtn");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");

const CONVERSATIONS_KEY = "nexora_conversations";
const ACTIVE_KEY = "nexora_active_conversation";

function loadConversations() {
    return JSON.parse(localStorage.getItem(CONVERSATIONS_KEY) || "[]");
}
function saveConversations(list) {
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(list));
}
function getActiveId() {
    return localStorage.getItem(ACTIVE_KEY);
}
function setActiveId(id) {
    localStorage.setItem(ACTIVE_KEY, id);
}

let conversations = loadConversations();
let activeId = getActiveId();

if (!activeId || !conversations.find((c) => c.id === activeId)) {
    const newConv = { id: crypto.randomUUID(), title: "New chat", updatedAt: Date.now() };
    conversations.unshift(newConv);
    activeId = newConv.id;
    saveConversations(conversations);
    setActiveId(activeId);
}

function renderSidebar() {
    conversationList.innerHTML = "";
    conversations
        .sort((a, b) => b.updatedAt - a.updatedAt)
        .forEach((conv) => {
            const item = document.createElement("div");
            item.className = "conversation-item" + (conv.id === activeId ? " active" : "");
            item.textContent = conv.title;
            item.addEventListener("click", () => switchConversation(conv.id));
            conversationList.appendChild(item);
        });
}

const THUMB_UP_SVG = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M7 11V21H4V11H7ZM7 11L11 3C12.1046 3 13 3.89543 13 5V9H18.5C19.6046 9 20.4368 10.0057 20.2 11.0831L18.8 17.0831C18.6132 17.9294 17.8619 18.5 17 18.5H7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const THUMB_DOWN_SVG = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M17 13V3H20V13H17ZM17 13L13 21C11.8954 21 11 20.1046 11 19V15H5.5C4.39543 15 3.56318 13.9943 3.8 12.9169L5.2 6.91689C5.38682 6.07064 6.1381 5.5 7 5.5H17" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

function buildFeedbackRow(messageId) {
    const row = document.createElement("div");
    row.className = "feedback-row";

    const up = document.createElement("button");
    up.className = "feedback-btn";
    up.innerHTML = THUMB_UP_SVG;
    up.setAttribute("aria-label", "Good response");

    const down = document.createElement("button");
    down.className = "feedback-btn";
    down.innerHTML = THUMB_DOWN_SVG;
    down.setAttribute("aria-label", "Bad response");

    up.addEventListener("click", () => sendFeedback(messageId, "up", up, down));
    down.addEventListener("click", () => sendFeedback(messageId, "down", up, down));

    row.appendChild(up);
    row.appendChild(down);
    return row;
}

async function sendFeedback(messageId, value, upBtn, downBtn) {
    const target = value === "up" ? upBtn : downBtn;
    upBtn.classList.remove("active-up", "active-down");
    downBtn.classList.remove("active-up", "active-down");
    target.classList.add(value === "up" ? "active-up" : "active-down");
    upBtn.disabled = true;
    downBtn.disabled = true;

    try {
        const res = await fetch("/feedback", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message_id: messageId, feedback: value }),
        });
        if (!res.ok) throw new Error("feedback request failed");
    } catch (err) {
        // Revert on failure so the UI never claims a vote was saved when it wasn't.
        target.classList.remove("active-up", "active-down");
        upBtn.disabled = false;
        downBtn.disabled = false;
    }
}

function renderMessage(text, sender, messageId = null) {
    const row = document.createElement("div");
    row.className = `message-row ${sender}`;

    const avatar = document.createElement("div");
    avatar.className = `avatar avatar-${sender}`;
    avatar.textContent = sender === "bot" ? "N" : "Y";

    const wrap = document.createElement("div");
    wrap.className = "message-wrap";

    const bubble = document.createElement("div");
    bubble.className = "message";

    if (sender === "bot") {
        const rawHtml = marked.parse(text);
        bubble.innerHTML = DOMPurify.sanitize(rawHtml);
    } else {
        bubble.textContent = text;
    }

    wrap.appendChild(bubble);
    if (sender === "bot" && messageId) {
        wrap.appendChild(buildFeedbackRow(messageId));
    }

    row.appendChild(avatar);
    row.appendChild(wrap);
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function switchConversation(id) {
    activeId = id;
    setActiveId(id);
    renderSidebar();
    chatMessages.innerHTML = "";

    try {
        const res = await fetch(`/history/${id}`);
        const history = await res.json();
        if (history.length === 0) {
            renderMessage("Hi! I'm Nexora. Ask me anything.", "bot");
        } else {
            history.forEach((m) => renderMessage(m.text, m.role, m.role === "bot" ? m.id : null));
        }
    } catch (err) {
        renderMessage("Could not load this conversation.", "bot");
    }
}

function startNewChat() {
    const newConv = { id: crypto.randomUUID(), title: "New chat", updatedAt: Date.now() };
    conversations.unshift(newConv);
    saveConversations(conversations);
    switchConversation(newConv.id);
}

function autoResize() {
    messageInput.style.height = "auto";
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + "px";
}
messageInput.addEventListener("input", autoResize);

async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text) return;

    renderMessage(text, "user");
    messageInput.value = "";
    autoResize();
    sendBtn.disabled = true;
    typingIndicator.classList.remove("hidden");
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Auto-title the conversation from the first message, ChatGPT-style.
    const activeConv = conversations.find((c) => c.id === activeId);
    if (activeConv && activeConv.title === "New chat") {
        activeConv.title = text.length > 40 ? text.slice(0, 40) + "..." : text;
        activeConv.updatedAt = Date.now();
        saveConversations(conversations);
        renderSidebar();
    }

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: activeId, message: text }),
        });
        const data = await res.json();
        if (res.ok) {
            renderMessage(data.reply, "bot", data.message_id);
        } else {
            renderMessage(data.error || "Something went wrong.", "bot");
        }
    } catch (err) {
        renderMessage("Could not reach the server. Is it running?", "bot");
    } finally {
        typingIndicator.classList.add("hidden");
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

sendBtn.addEventListener("click", sendMessage);
messageInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
newChatBtn.addEventListener("click", startNewChat);
sidebarToggle.addEventListener("click", () => sidebar.classList.toggle("collapsed"));

// Initial load
renderSidebar();
switchConversation(activeId);