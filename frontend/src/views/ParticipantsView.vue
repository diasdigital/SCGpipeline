<template>
    <div class="app-layout">
        <AppSidebar title="Developer" />

        <main class="page-main">
            <div class="page-container">
                <div class="page-header-row">
                    <div>
                        <h1 class="page-title">Participant Progress</h1>
                        <p class="page-sub">
                            Conversation history for each participant
                        </p>
                    </div>
                    <button
                        class="btn btn-ghost"
                        @click="loadAll"
                        :disabled="isLoading">
                        <i
                            class="ti ti-refresh"
                            :class="{ spin: isLoading }"
                            aria-hidden="true"></i>
                        Refresh
                    </button>
                </div>

                <div
                    v-if="isLoading && users.length === 0"
                    class="loading-state">
                    <i
                        class="ti ti-loader spin"
                        aria-hidden="true"></i>
                    Loading participant data...
                </div>

                <div
                    v-else
                    class="table-card">
                    <div class="table-header">
                        <p class="table-title">All participants</p>
                        <span class="table-count"
                            >{{ users.length }} registered accounts</span
                        >
                    </div>

                    <div
                        v-if="users.length === 0"
                        class="table-empty">
                        No participants registered yet.
                    </div>

                    <div v-else>
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Username</th>
                                    <th class="col-num">Total chats</th>
                                    <th class="col-num">Avg score</th>
                                    <th class="col-action">Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                <template
                                    v-for="user in users"
                                    :key="user.id">
                                    <tr
                                        :class="[
                                            'table-row',
                                            {
                                                'table-row--expanded':
                                                    expandedUserId === user.id,
                                            },
                                        ]"
                                        @click="toggleUser(user.id)">
                                        <td>
                                            <div class="user-cell">
                                                <div class="user-avatar">
                                                    {{
                                                        user.username
                                                            .charAt(0)
                                                            .toUpperCase()
                                                    }}
                                                </div>
                                                <span class="user-name">{{
                                                    user.username
                                                }}</span>
                                            </div>
                                        </td>
                                        <td class="col-num">
                                            {{ user.total_chats }}
                                        </td>
                                        <td class="col-num">
                                            <span
                                                v-if="user.avg_score !== null"
                                                :class="[
                                                    'score-chip',
                                                    scoreBadgeClass(
                                                        user.avg_score
                                                    ),
                                                ]">
                                                {{
                                                    formatScore(user.avg_score)
                                                }}
                                            </span>
                                            <span
                                                v-else
                                                class="text-muted"
                                                >–</span
                                            >
                                        </td>
                                        <td class="col-action">
                                            <button
                                                class="btn btn-ghost"
                                                style="
                                                    font-size: 12px;
                                                    padding: 4px 10px;
                                                "
                                                @click.stop="
                                                    toggleUser(user.id)
                                                ">
                                                {{
                                                    expandedUserId === user.id
                                                        ? 'Close'
                                                        : 'Detail'
                                                }}
                                            </button>
                                        </td>
                                    </tr>

                                    <tr
                                        v-if="expandedUserId === user.id"
                                        class="expand-row">
                                        <td colspan="4">
                                            <div class="expand-content">
                                                <div
                                                    v-if="loadingDetail"
                                                    class="expand-loading">
                                                    <i
                                                        class="ti ti-loader spin"
                                                        aria-hidden="true"></i>
                                                    Loading history...
                                                </div>

                                                <div v-else>
                                                    <div
                                                        v-if="
                                                            userChats[user.id]
                                                                ?.length
                                                        "
                                                        class="user-chat-list">
                                                        <p
                                                            class="expand-section-label">
                                                            Conversation history
                                                            ({{
                                                                userChats[
                                                                    user.id
                                                                ].length
                                                            }}
                                                            chats)
                                                        </p>
                                                        <div
                                                            v-for="chat in userChats[
                                                                user.id
                                                            ]"
                                                            :key="chat.id"
                                                            class="chat-row">
                                                            <div
                                                                class="chat-row-left">
                                                                <span
                                                                    class="chat-room-tag"
                                                                    >{{
                                                                        chat.room_name
                                                                    }}</span
                                                                >
                                                                <span
                                                                    class="chat-prompt"
                                                                    >{{
                                                                        chat.prompt_text
                                                                    }}</span
                                                                >
                                                            </div>
                                                            <div
                                                                class="chat-row-right">
                                                                <span
                                                                    v-if="
                                                                        chat.hallucination_score !==
                                                                        null
                                                                    "
                                                                    :class="[
                                                                        'score-chip',
                                                                        scoreBadgeClass(
                                                                            chat.hallucination_score
                                                                        ),
                                                                    ]">
                                                                    {{
                                                                        formatScore(
                                                                            chat.hallucination_score
                                                                        )
                                                                    }}
                                                                </span>
                                                                <span
                                                                    v-else
                                                                    class="badge badge-muted"
                                                                    >pending</span
                                                                >
                                                                <span
                                                                    v-if="
                                                                        chat.user_feedback ===
                                                                        1
                                                                    "
                                                                    class="feedback-icon"
                                                                    >👍</span
                                                                >
                                                                <span
                                                                    v-else-if="
                                                                        chat.user_feedback ===
                                                                        -1
                                                                    "
                                                                    class="feedback-icon"
                                                                    >👎</span
                                                                >
                                                                <span
                                                                    class="chat-time"
                                                                    >{{
                                                                        formatTime(
                                                                            chat.created_at
                                                                        )
                                                                    }}</span
                                                                >
                                                            </div>
                                                        </div>
                                                    </div>

                                                    <div
                                                        v-else
                                                        class="expand-empty">
                                                        This participant has no
                                                        conversation history
                                                        yet.
                                                    </div>
                                                </div>
                                            </div>
                                        </td>
                                    </tr>
                                </template>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </main>
    </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import AppSidebar from '@/components/AppSidebar.vue';
import { useDashboard } from '@/composables/useDashboard.js';

const { users, fetchUsers, fetchUserChats, scoreBadgeClass, formatScore } =
    useDashboard();

const isLoading = ref(false);
const expandedUserId = ref(null);
const loadingDetail = ref(false);

const userChats = reactive({});

onMounted(() => loadAll());

const loadAll = async () => {
    isLoading.value = true;
    await fetchUsers();
    isLoading.value = false;
};

const toggleUser = async (userId) => {
    if (expandedUserId.value === userId) {
        expandedUserId.value = null;
        return;
    }
    expandedUserId.value = userId;

    if (!userChats[userId]) {
        loadingDetail.value = true;
        userChats[userId] = await fetchUserChats(userId);
        loadingDetail.value = false;
    }
};

const formatTime = (iso) => {
    if (!iso) return '–';
    return new Date(iso).toLocaleString('id-ID', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
};
</script>

<style scoped>
.page-main {
    flex: 1;
    overflow-y: auto;
    padding: 32px 40px;
    background: var(--color-bg);
}
.page-container {
    max-width: 1000px;
    margin: 0 auto;
}

.page-header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
}
.page-title {
    font-size: 22px;
    font-weight: 500;
    color: var(--color-text-primary);
    margin: 0 0 4px;
}
.page-sub {
    font-size: 14px;
    color: var(--color-text-muted);
    margin: 0;
}

.loading-state {
    text-align: center;
    padding: 48px;
    font-size: 14px;
    color: var(--color-text-muted);
}

.table-card {
    background: var(--color-surface);
    border: 0.5px solid var(--color-border);
    border-radius: var(--radius-lg);
    overflow: hidden;
}
.table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 20px;
    border-bottom: 0.5px solid var(--color-border);
}
.table-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--color-text-primary);
    margin: 0;
}
.table-count {
    font-size: 12px;
    color: var(--color-text-muted);
}
.table-empty {
    padding: 32px;
    text-align: center;
    font-size: 13px;
    color: var(--color-text-muted);
}

.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}
.data-table th {
    padding: 10px 16px;
    text-align: left;
    font-size: 11px;
    font-weight: 500;
    color: var(--color-text-muted);
    background: var(--color-bg);
    border-bottom: 0.5px solid var(--color-border);
    white-space: nowrap;
}
.data-table td {
    padding: 12px 16px;
    border-bottom: 0.5px solid var(--color-border);
    vertical-align: middle;
}

.table-row {
    cursor: pointer;
    transition: background 0.1s;
}
.table-row:hover {
    background: var(--color-bg);
}
.table-row--expanded {
    background: #eef2ff;
}

.col-num {
    width: 90px;
    text-align: center;
}
.col-action {
    width: 80px;
    text-align: right;
}

.user-cell {
    display: flex;
    align-items: center;
    gap: 10px;
}
.user-avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    flex-shrink: 0;
    background: var(--color-primary-light);
    color: var(--color-primary-text);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 500;
}
.user-name {
    font-weight: 500;
    color: var(--color-text-primary);
}

.score-chip {
    font-size: 12px;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 99px;
}
.badge-danger {
    background: #fee2e2;
    color: #b91c1c;
}
.badge-warning {
    background: #fef3c7;
    color: #92400e;
}
.badge-success {
    background: #dcfce7;
    color: #166534;
}
.badge-muted {
    background: var(--color-bg);
    color: var(--color-text-muted);
    border: 0.5px solid var(--color-border);
}

.expand-row td {
    padding: 0;
}
.expand-content {
    padding: 20px;
    background: #f5f7ff;
    border-bottom: 0.5px solid var(--color-border);
}
.expand-loading {
    font-size: 13px;
    color: var(--color-text-muted);
    padding: 8px 0;
}
.expand-empty {
    font-size: 13px;
    color: var(--color-text-muted);
    padding: 8px 0;
}
.expand-section-label {
    font-size: 11px;
    font-weight: 500;
    color: var(--color-text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin: 16px 0 8px;
}

.user-chat-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.chat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    background: var(--color-surface);
    border: 0.5px solid var(--color-border);
    border-radius: var(--radius-md);
    font-size: 13px;
}
.chat-row-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
}
.chat-row-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}
.chat-room-tag {
    font-size: 11px;
    color: var(--color-primary-text);
    background: var(--color-primary-light);
    padding: 2px 7px;
    border-radius: 99px;
    white-space: nowrap;
    flex-shrink: 0;
}
.chat-prompt {
    color: var(--color-text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.feedback-icon {
    font-size: 14px;
}
.chat-time {
    font-size: 11px;
    color: var(--color-text-muted);
    white-space: nowrap;
}
.text-muted {
    color: var(--color-text-muted);
}

.spin {
    animation: spin 1s linear infinite;
    display: inline-block;
}
@keyframes spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}
</style>
