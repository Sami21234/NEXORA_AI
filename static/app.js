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

function renderMessage(text, sender) {
    const row = document.createElement("div");
    row.className = `message-row ${sender}`;

    const avatar = document.createElement("div");
    avatar.className = `avatar avatar-${sender}`;
    avatar.textContent = sender === "bot" ? "N" : "Y";

    const bubble = document.createElement("div");
    bubble.className = "message";

    if (sender === "bot") {
        const rawHtml = marked.parse(text);
        bubble.innerHTML = DOMPurify.sanitize(rawHtml);
    } else {
        bubble.textContent = text;
    }

    row.appendChild(avatar);
    row.appendChild(bubble);
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
            history.forEach((m) => renderMessage(m.text, m.role));
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
        renderMessage(res.ok ? data.reply : (data.error || "Something went wrong."), "bot");
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