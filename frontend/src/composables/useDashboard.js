import { ref, reactive } from 'vue';
import api from '@/api/axios.js';

export function useDashboard() {
    const stats = ref(null);
    const chats = ref([]);
    const users = ref([]);
    const config = ref({
        threshold_high: 0.6,
        threshold_mid: 0.4,
        num_samples: 5,
        temperature: 0.8,
        method: 'nli',
        llm_provider: 'ollama',
        llm_model: 'llama3',
        llm_api_key: '',
        llm_base_url: 'http://localhost:11434',
    });

    const llmStatus = ref(null);

    const loading = reactive({
        stats: false,
        chats: false,
        users: false,
        config: false,
        llmStatus: false,
    });

    const filters = reactive({
        userId: null,
        dateFrom: null,
        dateTo: null,
        llmModel: null,
        llmProvider: null,
    });

    const availableModels = ref([]);
    const availableProviders = ref([]);

    const fetchStats = async () => {
        loading.stats = true;
        try {
            const params = {};
            if (filters.userId) params.user_id = filters.userId;
            if (filters.dateFrom) params.date_from = filters.dateFrom;
            if (filters.dateTo) params.date_to = filters.dateTo;
            if (filters.llmModel) params.llm_model = filters.llmModel;
            if (filters.llmProvider) params.llm_provider = filters.llmProvider;
            const res = await api.get('/api/dashboard/stats', { params });
            stats.value = res.data;
        } catch (e) {
            console.error('[useDashboard] Failed to fetch stats:', e);
        } finally {
            loading.stats = false;
        }
    };

    const fetchChats = async () => {
        loading.chats = true;
        try {
            const params = { limit: 200 };
            if (filters.userId) params.user_id = filters.userId;
            if (filters.dateFrom) params.date_from = filters.dateFrom;
            if (filters.dateTo) params.date_to = filters.dateTo;
            if (filters.llmModel) params.llm_model = filters.llmModel;
            if (filters.llmProvider) params.llm_provider = filters.llmProvider;
            const res = await api.get('/api/dashboard/chats', { params });
            chats.value = res.data;
        } catch (e) {
            console.error('[useDashboard] Failed to fetch chats:', e);
        } finally {
            loading.chats = false;
        }
    };

    const fetchAvailableModels = async () => {
        try {
            const [modelsRes, providersRes] = await Promise.all([
                api.get('/api/dashboard/models'),
                api.get('/api/dashboard/providers'),
            ]);
            availableModels.value = modelsRes.data;
            availableProviders.value = providersRes.data;
        } catch (e) {
            console.error(
                '[useDashboard] Failed to fetch available models:',
                e
            );
        }
    };

    const fetchUsers = async () => {
        loading.users = true;
        try {
            const res = await api.get('/api/dashboard/users');
            users.value = res.data;
        } catch (e) {
            console.error('[useDashboard] Failed to fetch users:', e);
        } finally {
            loading.users = false;
        }
    };

    const fetchUserChats = async (userId) => {
        try {
            const res = await api.get(`/api/dashboard/users/${userId}/chats`);
            return res.data;
        } catch (e) {
            console.error(
                `[useDashboard] Failed to fetch chats for user ${userId}:`,
                e
            );
            return [];
        }
    };

    const fetchChatDetail = async (chatId) => {
        try {
            const res = await api.get(`/api/dashboard/chats/${chatId}`);
            return res.data;
        } catch (e) {
            console.error(
                `[useDashboard] Failed to fetch chat detail ${chatId}:`,
                e
            );
            return null;
        }
    };

    const fetchConfig = async () => {
        loading.config = true;
        try {
            const res = await api.get('/api/dashboard/config');
            config.value = res.data;
        } catch (e) {
            console.error('[useDashboard] Failed to fetch config:', e);
        } finally {
            loading.config = false;
        }
    };

    const saveConfig = async (newConfig) => {
        loading.config = true;
        try {
            const res = await api.put('/api/dashboard/config', newConfig);
            config.value = res.data;
            return true;
        } catch (e) {
            console.error('[useDashboard] Failed to save config:', e);
            return false;
        } finally {
            loading.config = false;
        }
    };

    const fetchLlmStatus = async () => {
        loading.llmStatus = true;
        llmStatus.value = null;
        try {
            const res = await api.get('/api/llm/status');
            llmStatus.value = res.data;
            return res.data;
        } catch (e) {
            const msg =
                e.response?.data?.detail ?? e.message ?? 'Unable to connect';
            llmStatus.value = { error: msg, available: false };
            return null;
        } finally {
            loading.llmStatus = false;
        }
    };

    const scoreLabel = (score) => {
        if (score === null || score === undefined) return 'pending';
        if (score >= config.value.threshold_high) return 'halusinasi';
        if (score >= config.value.threshold_mid) return 'borderline';
        return 'faktual';
    };

    const scoreBadgeClass = (score) =>
        ({
            halusinasi: 'badge-danger',
            borderline: 'badge-warning',
            faktual: 'badge-success',
            pending: 'badge-muted',
        }[scoreLabel(score)] ?? 'badge-muted');

    const formatScore = (score) =>
        score !== null && score !== undefined ? score.toFixed(2) : '-';

    return {
        stats,
        chats,
        users,
        config,
        filters,
        llmStatus,
        availableModels,
        availableProviders,
        loading,
        fetchStats,
        fetchChats,
        fetchUsers,
        fetchUserChats,
        fetchChatDetail,
        fetchConfig,
        saveConfig,
        fetchLlmStatus,
        fetchAvailableModels,
        scoreLabel,
        scoreBadgeClass,
        formatScore,
    };
}
