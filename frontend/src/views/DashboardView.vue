<template>
    <div class="app-layout">
        <AppSidebar title="Developer" />
        <main class="dash-main">
            <div class="dash-container">
                <div class="dash-header">
                    <div>
                        <h1 class="dash-title">Hallucination Dashboard</h1>
                        <p class="dash-sub">
                            Monitor SelfCheckNLI detection results on
                            participant conversations
                        </p>
                    </div>
                    <button
                        class="btn btn-ghost"
                        @click="refreshAll"
                        :disabled="isLoading">
                        <i
                            class="ti ti-refresh"
                            :class="{ spin: isLoading }"
                            aria-hidden="true"></i>
                        Refresh
                    </button>
                </div>

                <div class="filter-bar">
                    <div class="filter-group">
                        <label class="filter-label">User</label>
                        <select
                            class="filter-select"
                            v-model="selectedUserId"
                            @change="applyFilters">
                            <option :value="null">All participants</option>
                            <option
                                v-for="u in users"
                                :key="u.id"
                                :value="u.id">
                                {{ u.username }}
                            </option>
                        </select>
                    </div>

                    <div class="filter-group">
                        <label class="filter-label">Model</label>
                        <select
                            class="filter-select"
                            v-model="selectedModel"
                            @change="applyFilters">
                            <option :value="null">All models</option>
                            <option
                                v-for="m in availableModels"
                                :key="m"
                                :value="m">
                                {{ m }}
                            </option>
                        </select>
                    </div>

                    <div class="filter-group">
                        <label class="filter-label">Provider</label>
                        <select
                            class="filter-select"
                            v-model="selectedProvider"
                            @change="applyFilters">
                            <option :value="null">All providers</option>
                            <option
                                v-for="p in availableProviders"
                                :key="p"
                                :value="p">
                                {{ p }}
                            </option>
                        </select>
                    </div>

                    <div class="filter-group">
                        <label class="filter-label">From</label>
                        <input
                            type="datetime-local"
                            class="filter-input"
                            v-model="dateFrom"
                            @change="applyFilters" />
                    </div>

                    <div class="filter-group">
                        <label class="filter-label">To</label>
                        <input
                            type="datetime-local"
                            class="filter-input"
                            v-model="dateTo"
                            @change="applyFilters" />
                    </div>

                    <button
                        v-if="
                            selectedUserId ||
                            selectedModel ||
                            selectedProvider ||
                            dateFrom ||
                            dateTo
                        "
                        class="btn btn-ghost"
                        style="margin-top: 18px"
                        @click="resetFilters">
                        <i
                            class="ti ti-x"
                            aria-hidden="true"></i>
                        Reset
                    </button>
                </div>

                <div class="stat-grid">
                    <div class="stat-card">
                        <p class="stat-value">
                            {{ stats?.total_chats ?? '–' }}
                        </p>
                        <p class="stat-label">Total conversations</p>
                    </div>
                    <div class="stat-card">
                        <p class="stat-value">
                            {{ stats?.evaluated_chats ?? '–' }}
                        </p>
                        <p class="stat-label">Evaluated</p>
                    </div>
                    <div class="stat-card stat-card--danger">
                        <p class="stat-value">
                            {{ stats?.above_threshold ?? '–' }}
                        </p>
                        <p class="stat-label">Above threshold</p>
                    </div>
                    <div class="stat-card">
                        <p class="stat-value">
                            {{ stats ? formatScore(stats.avg_score) : '–' }}
                        </p>
                        <p class="stat-label">Average score</p>
                    </div>
                </div>

                <div class="chart-grid">
                    <div class="chart-card">
                        <p class="chart-title">
                            Hallucination score distribution
                        </p>
                        <div
                            v-if="stats?.score_distribution"
                            class="bar-chart">
                            <div
                                v-for="(
                                    count, bucket
                                ) in stats.score_distribution"
                                :key="bucket"
                                class="bar-group">
                                <div class="bar-wrap">
                                    <div
                                        class="bar-fill"
                                        :style="{
                                            height:
                                                barHeight(
                                                    count,
                                                    stats.score_distribution
                                                ) + '%',
                                        }"
                                        :class="barColorClass(bucket)"
                                        :title="`${bucket}: ${count} chats`"></div>
                                </div>
                                <span class="bar-label">{{ bucket }}</span>
                            </div>
                        </div>
                        <div
                            v-else
                            class="chart-empty">
                            No data available
                        </div>
                    </div>
                </div>

                <div class="table-card">
                    <div class="table-header">
                        <p class="table-title">Conversation history</p>
                        <span class="table-count"
                            >{{ chats.length }} chats</span
                        >
                    </div>

                    <div
                        v-if="loading.chats"
                        class="table-loading">
                        <i
                            class="ti ti-loader spin"
                            aria-hidden="true"></i>
                        Loading...
                    </div>

                    <div
                        v-else-if="chats.length === 0"
                        class="table-empty">
                        No conversation data available.
                    </div>

                    <div
                        v-else
                        class="table-wrap">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>User</th>
                                    <th>Prompt</th>
                                    <th class="col-model">Model</th>
                                    <th class="col-score">Score</th>
                                    <th class="col-status">Status</th>
                                    <th class="col-feedback">Feedback</th>
                                    <th class="col-time">Time</th>
                                </tr>
                            </thead>
                            <tbody>
                                <template
                                    v-for="chat in chats"
                                    :key="chat.id">
                                    <tr
                                        :class="[
                                            'table-row',
                                            {
                                                'table-row--expanded':
                                                    expandedChatId === chat.id,
                                            },
                                        ]"
                                        @click="toggleExpand(chat.id)">
                                        <td>{{ chat.username }}</td>
                                        <td class="td-prompt">
                                            {{ chat.prompt_text }}
                                        </td>
                                        <td class="col-model">
                                            <span
                                                v-if="chat.llm_model"
                                                class="model-chip">
                                                <span
                                                    class="model-chip__provider"
                                                    >{{
                                                        chat.llm_provider
                                                    }}</span
                                                >
                                                {{ chat.llm_model }}
                                            </span>
                                            <span
                                                v-else
                                                class="text-muted"
                                                >–</span
                                            >
                                        </td>
                                        <td class="col-score">
                                            <span
                                                v-if="
                                                    chat.hallucination_score !==
                                                    null
                                                "
                                                :class="[
                                                    'badge',
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
                                        </td>
                                        <td class="col-status">
                                            <span
                                                :class="[
                                                    'badge',
                                                    scoreBadgeClass(
                                                        chat.hallucination_score
                                                    ),
                                                ]">
                                                {{
                                                    scoreLabel(
                                                        chat.hallucination_score
                                                    )
                                                }}
                                            </span>
                                        </td>
                                        <td class="col-feedback">
                                            <span
                                                v-if="chat.user_feedback === 1"
                                                title="Factual"
                                                >👍</span
                                            >
                                            <span
                                                v-else-if="
                                                    chat.user_feedback === -1
                                                "
                                                title="Hallucination"
                                                >👎</span
                                            >
                                            <span
                                                v-else
                                                class="text-muted"
                                                >–</span
                                            >
                                        </td>
                                        <td class="col-time">
                                            {{ formatTime(chat.created_at) }}
                                        </td>
                                    </tr>

                                    <tr
                                        v-if="expandedChatId === chat.id"
                                        class="expand-row">
                                        <td colspan="7">
                                            <div class="expand-content">
                                                <div
                                                    v-if="loadingDetail"
                                                    class="expand-loading">
                                                    <i
                                                        class="ti ti-loader spin"
                                                        aria-hidden="true"></i>
                                                    Loading details...
                                                </div>
                                                <div v-else-if="chatDetail">
                                                    <div class="expand-grid">
                                                        <div>
                                                            <p
                                                                class="expand-label">
                                                                Prompt
                                                            </p>
                                                            <p
                                                                class="expand-text">
                                                                {{
                                                                    chatDetail.prompt_text
                                                                }}
                                                            </p>
                                                        </div>
                                                        <div>
                                                            <p
                                                                class="expand-label">
                                                                LLM Response
                                                            </p>
                                                            <p
                                                                class="expand-text">
                                                                {{
                                                                    chatDetail.llm_response
                                                                }}
                                                            </p>
                                                        </div>
                                                    </div>
                                                    <div class="expand-meta">
                                                        <span
                                                            >Room:
                                                            <strong>{{
                                                                chatDetail.room_name
                                                            }}</strong></span
                                                        >
                                                        <span
                                                            v-if="
                                                                chatDetail.llm_model
                                                            ">
                                                            Model:
                                                            <strong
                                                                >{{
                                                                    chatDetail.llm_provider
                                                                }}/{{
                                                                    chatDetail.llm_model
                                                                }}</strong
                                                            >
                                                        </span>
                                                        <span
                                                            >Method:
                                                            <strong>{{
                                                                chatDetail.evaluation_method
                                                            }}</strong></span
                                                        >
                                                        <span
                                                            v-if="
                                                                chatDetail.temperature_sample !=
                                                                null
                                                            ">
                                                            Temperature:
                                                            <strong>{{
                                                                chatDetail.temperature_sample
                                                            }}</strong>
                                                        </span>
                                                        <span
                                                            v-if="
                                                                chatDetail.num_samples !=
                                                                null
                                                            ">
                                                            Samples:
                                                            <strong
                                                                >{{
                                                                    chatDetail.num_samples
                                                                }}x</strong
                                                            >
                                                        </span>
                                                        <span
                                                            >Score:
                                                            <strong>{{
                                                                formatScore(
                                                                    chatDetail.hallucination_score
                                                                )
                                                            }}</strong></span
                                                        >
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
import { ref, onMounted } from 'vue';
import AppSidebar from '@/components/AppSidebar.vue';
import { useDashboard } from '@/composables/useDashboard.js';

const {
    stats,
    chats,
    users,
    filters,
    loading,
    availableModels,
    availableProviders,
    fetchStats,
    fetchChats,
    fetchUsers,
    fetchChatDetail,
    fetchAvailableModels,
    scoreLabel,
    scoreBadgeClass,
    formatScore,
} = useDashboard();

const selectedUserId = ref(null);
const selectedModel = ref(null);
const selectedProvider = ref(null);
const dateFrom = ref('');
const dateTo = ref('');

const expandedChatId = ref(null);
const chatDetail = ref(null);
const loadingDetail = ref(false);

const isLoading = ref(false);

onMounted(async () => {
    await refreshAll();
});

const refreshAll = async () => {
    isLoading.value = true;
    await Promise.all([
        fetchStats(),
        fetchChats(),
        fetchUsers(),
        fetchAvailableModels(),
    ]);
    isLoading.value = false;
};

const applyFilters = async () => {
    filters.userId = selectedUserId.value;
    filters.llmModel = selectedModel.value;
    filters.llmProvider = selectedProvider.value;
    filters.dateFrom = dateFrom.value || null;
    filters.dateTo = dateTo.value || null;
    isLoading.value = true;
    await Promise.all([fetchStats(), fetchChats()]);
    isLoading.value = false;
};

const resetFilters = async () => {
    selectedUserId.value = null;
    selectedModel.value = null;
    selectedProvider.value = null;
    dateFrom.value = '';
    dateTo.value = '';
    filters.userId = null;
    filters.llmModel = null;
    filters.llmProvider = null;
    filters.dateFrom = null;
    filters.dateTo = null;
    await refreshAll();
};

const toggleExpand = async (chatId) => {
    if (expandedChatId.value === chatId) {
        expandedChatId.value = null;
        chatDetail.value = null;
        return;
    }
    expandedChatId.value = chatId;
    chatDetail.value = null;
    loadingDetail.value = true;
    chatDetail.value = await fetchChatDetail(chatId);
    loadingDetail.value = false;
};

const formatTime = (isoString) => {
    if (!isoString) return '–';
    const d = new Date(isoString);
    return d.toLocaleString('id-ID', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
};

const barHeight = (count, distribution) => {
    const max = Math.max(...Object.values(distribution), 1);
    return Math.max((count / max) * 100, count > 0 ? 4 : 0);
};

const barColorClass = (bucket) => {
    if (bucket === '0.6-0.8' || bucket === '0.8-1.0') return 'bar-danger';
    if (bucket === '0.4-0.6') return 'bar-warning';
    return 'bar-success';
};
</script>

<style scoped>
.dash-main {
    flex: 1;
    overflow-y: auto;
    padding: 32px 40px;
    background: var(--color-bg);
}
.dash-container {
    max-width: 1100px;
    margin: 0 auto;
}

.dash-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
}
.dash-title {
    font-size: 22px;
    font-weight: 500;
    color: var(--color-text-primary);
    margin: 0 0 4px;
}
.dash-sub {
    font-size: 14px;
    color: var(--color-text-muted);
    margin: 0;
}

.filter-bar {
    display: flex;
    gap: 16px;
    align-items: flex-end;
    flex-wrap: wrap;
    padding: 14px 16px;
    background: var(--color-surface);
    border: 0.5px solid var(--color-border);
    border-radius: var(--radius-lg);
    margin-bottom: 24px;
}
.filter-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.filter-label {
    font-size: 11px;
    color: var(--color-text-muted);
    font-weight: 500;
}
.filter-select,
.filter-input {
    font-size: 13px;
    padding: 7px 10px;
    border: 0.5px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg);
    color: var(--color-text-primary);
    outline: none;
    transition: border-color 0.15s;
}
.filter-select:focus,
.filter-input:focus {
    border-color: var(--color-primary);
}

.stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 24px;
}
.stat-card {
    background: var(--color-surface);
    border: 0.5px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 16px 20px;
}
.stat-card--danger {
    border-color: #fca5a5;
    background: #fff5f5;
}
.stat-value {
    font-size: 28px;
    font-weight: 500;
    color: var(--color-text-primary);
    margin: 0 0 4px;
}
.stat-card--danger .stat-value {
    color: var(--color-danger);
}
.stat-label {
    font-size: 12px;
    color: var(--color-text-muted);
    margin: 0;
}

.chart-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 24px;
}
.chart-card {
    background: var(--color-surface);
    border: 0.5px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 16px 20px;
}
.chart-title {
    font-size: 13px;
    font-weight: 500;
    color: var(--color-text-primary);
    margin: 0 0 14px;
}
.chart-empty {
    font-size: 13px;
    color: var(--color-text-muted);
    text-align: center;
    padding: 20px 0;
}

.bar-chart {
    display: flex;
    align-items: flex-end;
    gap: 8px;
    height: 100px;
    padding-bottom: 24px;
    position: relative;
}
.bar-group {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    height: 100%;
}
.bar-wrap {
    flex: 1;
    width: 100%;
    display: flex;
    align-items: flex-end;
}
.bar-fill {
    width: 100%;
    border-radius: 4px 4px 0 0;
    transition: height 0.4s ease;
    min-height: 2px;
    cursor: pointer;
}
.bar-success {
    background: var(--color-success);
}
.bar-warning {
    background: var(--color-warning);
}
.bar-danger {
    background: var(--color-danger);
}
.bar-label {
    font-size: 10px;
    color: var(--color-text-muted);
    margin-top: 4px;
    text-align: center;
    white-space: nowrap;
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
.table-loading,
.table-empty {
    padding: 32px;
    text-align: center;
    font-size: 13px;
    color: var(--color-text-muted);
}
.table-wrap {
    overflow-x: auto;
}

.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}
.data-table th {
    padding: 10px 14px;
    text-align: left;
    font-size: 11px;
    font-weight: 500;
    color: var(--color-text-muted);
    background: var(--color-bg);
    border-bottom: 0.5px solid var(--color-border);
    white-space: nowrap;
}
.data-table td {
    padding: 11px 14px;
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
    background: var(--color-primary-light) !important;
}

.td-prompt {
    max-width: 280px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--color-text-primary);
}

.col-score {
    width: 80px;
    text-align: center;
}
.col-status {
    width: 110px;
    text-align: center;
}
.col-feedback {
    width: 70px;
    text-align: center;
}
.col-time {
    width: 120px;
    color: var(--color-text-muted);
    white-space: nowrap;
}

.expand-row td {
    padding: 0;
}
.expand-content {
    padding: 16px 20px;
    background: var(--color-bg);
    border-bottom: 0.5px solid var(--color-border);
}
.expand-loading {
    font-size: 13px;
    color: var(--color-text-muted);
    padding: 8px 0;
}
.expand-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 12px;
}

.expand-label {
    font-size: 11px;
    color: var(--color-text-muted);
    font-weight: 500;
    margin: 0 0 4px;
}
.expand-text {
    font-size: 13px;
    color: var(--color-text-primary);
    line-height: 1.6;
    margin: 0;
    white-space: pre-wrap;
    max-height: 200px;
    overflow-y: auto;
    background: var(--color-surface);
    padding: 10px 12px;
    border-radius: var(--radius-md);
    border: 0.5px solid var(--color-border);
}
.expand-meta {
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    font-size: 12px;
    color: var(--color-text-muted);
}
.expand-meta strong {
    color: var(--color-text-primary);
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

.col-model {
    width: 160px;
    white-space: nowrap;
}

.model-chip {
    display: inline-flex;
    flex-direction: column;
    font-size: 11px;
    line-height: 1.3;
    color: var(--color-text-primary);
}
.model-chip__provider {
    font-size: 10px;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
</style>
