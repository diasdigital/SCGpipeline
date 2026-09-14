<template>
    <div
        v-if="showRenameModal"
        class="modal-overlay"
        @click.self="closeModals">
        <div class="modal-card">
            <h3>Rename Chat</h3>
            <input
                v-model="tempRoomName"
                type="text"
                class="modal-input"
                placeholder="Enter new name..."
                @keyup.enter="confirmRename"
                ref="renameInput" />
            <div class="modal-actions">
                <button
                    @click="closeModals"
                    class="btn btn-ghost">
                    Cancel
                </button>
                <button
                    @click="confirmRename"
                    class="btn btn-primary">
                    Save
                </button>
            </div>
        </div>
    </div>

    <div
        v-if="showDeleteModal"
        class="modal-overlay"
        @click.self="closeModals">
        <div class="modal-card">
            <h3>Delete Conversation?</h3>
            <p>
                Are you sure you want to permanently delete
                <strong>"{{ targetRoom?.room_name }}"</strong>?
            </p>
            <div class="modal-actions">
                <button
                    @click="closeModals"
                    class="btn btn-ghost">
                    Cancel
                </button>
                <button
                    @click="confirmDelete"
                    class="btn btn-danger">
                    Yes, Delete
                </button>
            </div>
        </div>
    </div>

    <div class="app-layout">
        <AppSidebar title="Personal Assistant">
            <button
                @click="createNewRoom"
                class="new-chat-btn">
                <span>+</span> New Chat
            </button>

            <div class="room-list">
                <div
                    v-for="room in rooms"
                    :key="room.id"
                    :class="['nav-item', { active: activeRoomId === room.id }]"
                    @click="selectRoom(room.id)">
                    <div class="room-info">
                        <span class="icon">💬</span>
                        <span class="room-name">{{ room.room_name }}</span>
                    </div>
                    <div
                        class="kebab-menu"
                        @click.stop>
                        <button
                            class="kebab-btn"
                            @click="toggleDropdown(room.id)">
                            ⋮
                        </button>
                        <div
                            v-if="activeDropdown === room.id"
                            class="dropdown-content">
                            <button
                                @click="openRenameModal(room)"
                                class="dropdown-item">
                                ✏️ Rename
                            </button>
                            <button
                                @click="openDeleteModal(room)"
                                class="dropdown-item danger">
                                🗑️ Delete
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </AppSidebar>

        <main class="chat-main">
            <div
                v-if="messages.length === 0"
                class="empty-state">
                <div class="ai-avatar-large">🤖</div>
                <h1>How can I help you today?</h1>
                <p>Ask me anything, or try an example below.</p>
                <div class="suggestion-pills">
                    <button @click="setInput('Draft an email')">
                        Draft an email
                    </button>
                    <button @click="setInput('Explain quantum computing')">
                        Explain quantum computing
                    </button>
                    <button @click="setInput('Plan a weekend trip')">
                        Plan a weekend trip
                    </button>
                </div>
            </div>

            <div
                v-else
                class="chat-history"
                ref="messageBox">
                <div
                    v-for="(msg, index) in messages"
                    :key="index"
                    :class="['message-row', msg.role]">
                    <div
                        v-if="msg.role === 'assistant'"
                        class="msg-avatar ai">
                        🤖
                    </div>
                    <div class="message-bubble">
                        <div
                            class="markdown-body"
                            v-html="renderMarkdown(msg.content)"></div>

                        <div
                            v-if="msg.role === 'assistant' && msg.id"
                            class="feedback-actions">
                            <button
                                class="btn-feedback"
                                :class="{
                                    'active-up': msg.user_feedback === 1,
                                }"
                                @click="submitFeedback(msg, 1)"
                                :disabled="isStreaming"
                                title="Good answer">
                                👍
                            </button>
                            <button
                                class="btn-feedback"
                                :class="{
                                    'active-down': msg.user_feedback === -1,
                                }"
                                @click="submitFeedback(msg, -1)"
                                :disabled="isStreaming"
                                title="Bad answer">
                                👎
                            </button>
                        </div>
                    </div>
                    <div
                        v-if="msg.role === 'user'"
                        class="msg-avatar user">
                        {{ currentUsername.charAt(0).toUpperCase() }}
                    </div>
                </div>

                <div
                    v-if="isStreaming && currentStreamText === ''"
                    class="message-row assistant">
                    <div class="msg-avatar ai">🤖</div>
                    <div class="message-bubble loading-bubble">
                        <span class="dot"></span>
                        <span class="dot"></span>
                        <span class="dot"></span>
                    </div>
                </div>
            </div>

            <div class="input-area">
                <form
                    @submit.prevent="sendMessage"
                    class="input-container">
                    <input
                        v-model="inputMessage"
                        type="text"
                        placeholder="Message AI Chat..."
                        :disabled="isStreaming" />
                    <button
                        type="submit"
                        class="send-btn"
                        :disabled="isStreaming || !inputMessage.trim()">
                        ↑
                    </button>
                </form>
                <p class="disclaimer">
                    AI Chat can make mistakes. Consider verifying important
                    information.
                </p>
            </div>
        </main>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import api from '@/api/axios.js';
import { marked } from 'marked';

import AppSidebar from '@/components/AppSidebar.vue';
import { useAuth } from '@/composables/useAuth.js';

const { currentUsername, getToken } = useAuth();

const rooms = ref([]);
const activeRoomId = ref(null);
const messages = ref([]);
const inputMessage = ref('');

const isStreaming = ref(false);
const currentStreamText = ref('');

const messageBox = ref(null);
const activeDropdown = ref(null);
const showRenameModal = ref(false);
const showDeleteModal = ref(false);
const targetRoom = ref(null);
const tempRoomName = ref('');
const renameInput = ref(null);

onMounted(() => {
    fetchRooms();
    document.addEventListener('click', closeDropdown);
});
onUnmounted(() => {
    document.removeEventListener('click', closeDropdown);
});

const renderMarkdown = (rawText) => (rawText ? marked.parse(rawText) : '');
const scrollToBottom = async () => {
    await nextTick();
    if (messageBox.value)
        messageBox.value.scrollTop = messageBox.value.scrollHeight;
};
const setInput = (text) => {
    inputMessage.value = text;
};

const toggleDropdown = (roomId) => {
    activeDropdown.value = activeDropdown.value === roomId ? null : roomId;
};
const closeDropdown = () => {
    activeDropdown.value = null;
};
const openRenameModal = async (room) => {
    targetRoom.value = room;
    tempRoomName.value = room.room_name;
    activeDropdown.value = null;
    showRenameModal.value = true;
    await nextTick();
    renameInput.value?.focus();
};
const openDeleteModal = (room) => {
    targetRoom.value = room;
    activeDropdown.value = null;
    showDeleteModal.value = true;
};
const closeModals = () => {
    showRenameModal.value = false;
    showDeleteModal.value = false;
    targetRoom.value = null;
};

const confirmRename = async () => {
    const newName = tempRoomName.value.trim();
    if (!newName || newName === targetRoom.value.room_name) {
        closeModals();
        return;
    }
    try {
        await api.patch(
            `/api/rooms/${targetRoom.value.id}`,
            { room_name: newName },
            { headers: { Authorization: `Bearer ${getToken()}` } }
        );
        const room = rooms.value.find((r) => r.id === targetRoom.value.id);
        if (room) room.room_name = newName;
    } catch (e) {
        console.error('[ChatView] Failed to rename room:', e);
    } finally {
        closeModals();
    }
};

const confirmDelete = async () => {
    try {
        await api.delete(`/api/rooms/${targetRoom.value.id}`, {
            headers: { Authorization: `Bearer ${getToken()}` },
        });
        const deletedId = targetRoom.value.id;
        rooms.value = rooms.value.filter((r) => r.id !== deletedId);
        if (activeRoomId.value === deletedId) {
            if (rooms.value.length > 0) {
                selectRoom(rooms.value[0].id);
            } else {
                activeRoomId.value = null;
                messages.value = [];
            }
        }
    } catch (e) {
        console.error('[ChatView] Failed to delete room:', e);
    } finally {
        closeModals();
    }
};

const fetchRooms = async () => {
    try {
        const res = await api.get('/api/rooms', {
            headers: { Authorization: `Bearer ${getToken()}` },
        });
        rooms.value = res.data;
        if (rooms.value.length > 0) selectRoom(rooms.value[0].id);
    } catch (e) {
        console.error('[ChatView] Failed to fetch rooms:', e);
    }
};

const selectRoom = async (roomId) => {
    activeRoomId.value = roomId;
    try {
        const res = await api.get(`/api/rooms/${roomId}/chats`);

        messages.value = res.data.flatMap((chat) => [
            { role: 'user', content: chat.prompt_text },
            {
                id: chat.id,
                role: 'assistant',
                content: chat.llm_response,
                user_feedback: chat.user_feedback,
            },
        ]);
        scrollToBottom();
    } catch (e) {
        console.error('[ChatView] Failed to fetch chats:', e);
    }
};

const createNewRoom = async () => {
    try {
        const res = await api.post(
            '/api/rooms',
            { room_name: 'New Conversation' },
            { headers: { Authorization: `Bearer ${getToken()}` } }
        );
        rooms.value.unshift(res.data);
        activeRoomId.value = res.data.id;
        messages.value = [];
    } catch (e) {
        console.error('[ChatView] Failed to create room:', e);
    }
};

const sendMessage = async () => {
    if (!inputMessage.value.trim() || isStreaming.value) return;
    if (!activeRoomId.value) await createNewRoom();

    const userPrompt = inputMessage.value;
    messages.value.push({ role: 'user', content: userPrompt });
    inputMessage.value = '';
    isStreaming.value = true;
    currentStreamText.value = '';
    scrollToBottom();

    try {
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${getToken()}`,
            },
            body: JSON.stringify({
                room_id: activeRoomId.value,
                prompt_text: userPrompt,
            }),
        });
        if (!response.ok) throw new Error(`HTTP error: ${response.status}`);

        const chatId = response.headers.get('X-Chat-ID');
        console.log(`[ChatView] Streaming started for chat_id: ${chatId}`);

        messages.value.push({
            id: parseInt(chatId),
            role: 'assistant',
            content: '',
            user_feedback: null,
        });
        const assistantIndex = messages.value.length - 1;

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            currentStreamText.value += chunk;
            messages.value[assistantIndex].content = currentStreamText.value;
            scrollToBottom();
        }
    } catch (e) {
        console.error('[ChatView] Streaming error:', e);
        messages.value.push({
            role: 'assistant',
            content: 'Sorry, an error occurred. Please try again in a moment.',
        });
    } finally {
        isStreaming.value = false;
        scrollToBottom();
    }
};

const submitFeedback = async (msg, value) => {
    if (msg.user_feedback === value) return;

    const prevFeedback = msg.user_feedback;
    msg.user_feedback = value;

    try {
        await api.patch(`/api/chat/${msg.id}/feedback`, {
            user_feedback: value,
        });
    } catch (e) {
        console.error('[ChatView] Failed to submit feedback:', e);
        msg.user_feedback = prevFeedback;
    }
};
</script>

<style src="@/styles/chatView.css"></style>
