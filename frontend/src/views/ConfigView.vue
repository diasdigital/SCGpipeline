<template>
    <div class="app-layout">
        <AppSidebar title="Developer" />

        <main class="page-main">
            <div class="page-container">
                <div class="page-header-row">
                    <div>
                        <h1 class="page-title">Detection Configuration</h1>
                        <p class="page-sub">
                            Configure the LLM provider, classification
                            thresholds, and sampling parameters. All changes
                            take effect immediately without restarting the
                            server.
                        </p>
                    </div>
                </div>

                <div
                    v-if="!localConfig"
                    class="loading-state">
                    <i
                        class="ti ti-loader spin"
                        aria-hidden="true"></i>
                    Loading configuration...
                </div>

                <template v-else>
                    <div class="section-card">
                        <div class="section-card-header">
                            <i
                                class="ti ti-cpu"
                                aria-hidden="true"></i>
                            <div>
                                <p class="section-card-title">
                                    LLM Model Configuration
                                </p>
                                <p class="section-card-desc">
                                    Select the provider and model used to
                                    generate chat responses and stochastic
                                    samples. Changes apply to subsequent
                                    conversations.
                                </p>
                            </div>
                        </div>

                        <div class="llm-field">
                            <label class="llm-label">Provider</label>
                            <div class="provider-tabs">
                                <button
                                    v-for="p in providers"
                                    :key="p.value"
                                    class="provider-tab"
                                    :class="{
                                        active:
                                            localConfig.llm_provider ===
                                            p.value,
                                    }"
                                    @click="onProviderChange(p.value)"
                                    type="button">
                                    <i
                                        :class="['ti', p.icon]"
                                        aria-hidden="true"></i>
                                    {{ p.label }}
                                </button>
                            </div>
                        </div>

                        <div
                            v-if="localConfig.llm_provider === 'none'"
                            class="none-banner">
                            <i
                                class="ti ti-info-circle"
                                aria-hidden="true"></i>
                            <p>
                                <strong>No Model</strong> mode is active.
                                FastAPI continues to run and chats send
                                placeholder messages — no LLM response or
                                hallucination evaluation.
                            </p>
                        </div>

                        <template v-if="localConfig.llm_provider !== 'none'">
                            <div class="llm-field">
                                <label class="llm-label">Model Name</label>
                                <div class="llm-input-wrap">
                                    <input
                                        type="text"
                                        class="llm-input"
                                        v-model="localConfig.llm_model"
                                        :placeholder="modelPlaceholder" />
                                </div>
                                <p class="llm-hint">{{ modelHint }}</p>
                            </div>

                            <div
                                v-if="providerNeedsKey"
                                class="llm-field">
                                <label class="llm-label">API Key</label>
                                <div class="llm-input-wrap api-key-wrap">
                                    <input
                                        :type="showApiKey ? 'text' : 'password'"
                                        class="llm-input"
                                        v-model="localConfig.llm_api_key"
                                        placeholder="Fill to change, leave blank to keep current" />
                                    <button
                                        class="eye-btn"
                                        type="button"
                                        @click="showApiKey = !showApiKey"
                                        :title="showApiKey ? 'Hide' : 'Show'">
                                        <i
                                            :class="[
                                                'ti',
                                                showApiKey
                                                    ? 'ti-eye-off'
                                                    : 'ti-eye',
                                            ]"
                                            aria-hidden="true"></i>
                                    </button>
                                </div>
                                <p class="llm-hint llm-hint--warn">
                                    <i
                                        class="ti ti-lock-small"
                                        aria-hidden="true"></i>
                                    The server always returns this field empty
                                    for security. Enter a new value only if you
                                    wish to replace it.
                                </p>
                            </div>

                            <div
                                v-if="localConfig.llm_provider === 'ollama'"
                                class="llm-field">
                                <label class="llm-label">Ollama Base URL</label>
                                <div class="llm-input-wrap">
                                    <input
                                        type="text"
                                        class="llm-input"
                                        v-model="localConfig.llm_base_url"
                                        placeholder="http://localhost:11434" />
                                </div>
                                <p class="llm-hint">
                                    Ollama server address. Change if Ollama runs
                                    on a different host or port.
                                </p>
                            </div>
                        </template>

                        <div class="llm-test-row">
                            <button
                                class="btn btn-ghost btn-sm"
                                type="button"
                                @click="testConnection"
                                :disabled="loading.llmStatus">
                                <i
                                    v-if="loading.llmStatus"
                                    class="ti ti-loader spin"
                                    aria-hidden="true"></i>
                                <i
                                    v-else
                                    class="ti ti-plug"
                                    aria-hidden="true"></i>
                                Test Connection
                            </button>

                            <div
                                v-if="llmStatus"
                                class="status-strip"
                                :class="
                                    llmStatus.error
                                        ? 'status-strip--err'
                                        : 'status-strip--ok'
                                ">
                                <span
                                    class="status-dot"
                                    :class="
                                        llmStatus.error
                                            ? 'status-dot--err'
                                            : 'status-dot--ok'
                                    "></span>
                                <span v-if="llmStatus.error">
                                    Failed: {{ llmStatus.error }}
                                </span>
                                <span v-else>
                                    Active &mdash;
                                    <strong>{{ llmStatus.provider }}</strong> /
                                    <strong>{{ llmStatus.model }}</strong>
                                    <template v-if="llmStatus.base_url">
                                        @ {{ llmStatus.base_url }}
                                    </template>
                                    <template v-if="llmStatus.has_api_key">
                                        &nbsp;&middot; API key
                                        <span class="key-ok">✓</span>
                                    </template>
                                </span>
                            </div>
                        </div>
                    </div>

                    <div class="config-grid">
                        <div class="config-card">
                            <div class="config-card-header">
                                <i
                                    class="ti ti-adjustments-horizontal"
                                    aria-hidden="true"></i>
                                <div>
                                    <p class="config-card-title">
                                        Classification Thresholds
                                    </p>
                                    <p class="config-card-desc">
                                        Determines score boundaries for each
                                        hallucination category. Changes only
                                        affect label and color displays — scores
                                        already stored in the database remain
                                        unchanged.
                                    </p>
                                </div>
                            </div>

                            <div class="threshold-list">
                                <div class="threshold-row">
                                    <div class="threshold-label-group">
                                        <span
                                            class="threshold-dot threshold-dot--danger"></span>
                                        <div>
                                            <p class="threshold-name">
                                                Hallucination
                                            </p>
                                            <p class="threshold-desc">
                                                Scores ≥ this value are
                                                categorized as hallucination
                                                (red)
                                            </p>
                                        </div>
                                    </div>
                                    <div class="threshold-input-group">
                                        <input
                                            type="range"
                                            class="threshold-slider"
                                            v-model.number="
                                                localConfig.threshold_high
                                            "
                                            min="0"
                                            max="1"
                                            step="0.05"
                                            @input="clampThresholds('high')" />
                                        <input
                                            type="number"
                                            class="threshold-number"
                                            v-model.number="
                                                localConfig.threshold_high
                                            "
                                            min="0"
                                            max="1"
                                            step="0.05"
                                            @change="clampThresholds('high')" />
                                    </div>
                                </div>

                                <div class="threshold-row">
                                    <div class="threshold-label-group">
                                        <span
                                            class="threshold-dot threshold-dot--warning"></span>
                                        <div>
                                            <p class="threshold-name">
                                                Borderline
                                            </p>
                                            <p class="threshold-desc">
                                                Scores between this value and
                                                the hallucination threshold
                                                (yellow)
                                            </p>
                                        </div>
                                    </div>
                                    <div class="threshold-input-group">
                                        <input
                                            type="range"
                                            class="threshold-slider"
                                            v-model.number="
                                                localConfig.threshold_mid
                                            "
                                            min="0"
                                            max="1"
                                            step="0.05"
                                            @input="clampThresholds('mid')" />
                                        <input
                                            type="number"
                                            class="threshold-number"
                                            v-model.number="
                                                localConfig.threshold_mid
                                            "
                                            min="0"
                                            max="1"
                                            step="0.05"
                                            @change="clampThresholds('mid')" />
                                    </div>
                                </div>

                                <div
                                    class="threshold-row threshold-row--disabled">
                                    <div class="threshold-label-group">
                                        <span
                                            class="threshold-dot threshold-dot--success"></span>
                                        <div>
                                            <p class="threshold-name">
                                                Factual
                                            </p>
                                            <p class="threshold-desc">
                                                Scores &lt;
                                                {{ localConfig.threshold_mid }}
                                                are categorized as factual
                                                (green)
                                            </p>
                                        </div>
                                    </div>
                                    <div class="threshold-input-group">
                                        <div class="threshold-auto">
                                            Automatic
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div
                                v-if="stats"
                                class="threshold-preview">
                                <p class="preview-label">
                                    Preview with current thresholds
                                </p>
                                <div class="preview-bar-wrap">
                                    <div
                                        class="preview-segment preview-segment--success"
                                        :style="{
                                            flex: countByLabel('faktual'),
                                        }"
                                        :title="`Factual: ${countByLabel(
                                            'faktual'
                                        )} chats`">
                                        <span
                                            v-if="countByLabel('faktual') > 0"
                                            >{{ countByLabel('faktual') }}</span
                                        >
                                    </div>
                                    <div
                                        class="preview-segment preview-segment--warning"
                                        :style="{
                                            flex: countByLabel('borderline'),
                                        }"
                                        :title="`Borderline: ${countByLabel(
                                            'borderline'
                                        )} chats`">
                                        <span
                                            v-if="
                                                countByLabel('borderline') > 0
                                            "
                                            >{{
                                                countByLabel('borderline')
                                            }}</span
                                        >
                                    </div>
                                    <div
                                        class="preview-segment preview-segment--danger"
                                        :style="{
                                            flex: countByLabel('halusinasi'),
                                        }"
                                        :title="`Hallucination: ${countByLabel(
                                            'halusinasi'
                                        )} chats`">
                                        <span
                                            v-if="
                                                countByLabel('halusinasi') > 0
                                            "
                                            >{{
                                                countByLabel('halusinasi')
                                            }}</span
                                        >
                                    </div>
                                </div>
                                <div class="preview-legend">
                                    <span class="legend-item"
                                        ><span
                                            class="legend-dot legend-dot--success"></span
                                        >Factual ({{
                                            countByLabel('faktual')
                                        }})</span
                                    >
                                    <span class="legend-item"
                                        ><span
                                            class="legend-dot legend-dot--warning"></span
                                        >Borderline ({{
                                            countByLabel('borderline')
                                        }})</span
                                    >
                                    <span class="legend-item"
                                        ><span
                                            class="legend-dot legend-dot--danger"></span
                                        >Hallucination ({{
                                            countByLabel('halusinasi')
                                        }})</span
                                    >
                                </div>
                            </div>
                        </div>

                        <div class="config-card">
                            <div class="config-card-header">
                                <i
                                    class="ti ti-settings-2"
                                    aria-hidden="true"></i>
                                <div>
                                    <p class="config-card-title">
                                        Sampling Parameters
                                    </p>
                                    <p class="config-card-desc">
                                        Configures Celery task behavior when
                                        generating stochastic samples. Changes
                                        apply to subsequent conversations — not
                                        retroactive.
                                    </p>
                                </div>
                            </div>

                            <div class="param-list">
                                <div class="param-row">
                                    <div class="param-label-group">
                                        <p class="param-name">
                                            Number of Samples (N)
                                        </p>
                                        <p class="param-desc">
                                            More samples → higher accuracy, but
                                            longer processing time. Recommended:
                                            3–7.
                                        </p>
                                    </div>
                                    <div class="param-input-group">
                                        <input
                                            type="number"
                                            class="param-input"
                                            v-model.number="
                                                localConfig.num_samples
                                            "
                                            min="1"
                                            max="20"
                                            step="1" />
                                        <span class="param-unit">samples</span>
                                    </div>
                                </div>

                                <div class="param-row">
                                    <div class="param-label-group">
                                        <p class="param-name">
                                            Sampling Temperature
                                        </p>
                                        <p class="param-desc">
                                            Higher values → more varied output.
                                            <template v-if="isGemini3">
                                                <span class="hint-warn"
                                                    >Gemini 3.x: automatically
                                                    increased to 1.0 if you set
                                                    0.7 (Google
                                                    recommendation).</span
                                                >
                                            </template>
                                            Default: 0.8.
                                        </p>
                                    </div>
                                    <div class="param-input-group">
                                        <input
                                            type="range"
                                            class="threshold-slider"
                                            v-model.number="
                                                localConfig.temperature
                                            "
                                            min="0"
                                            max="2"
                                            step="0.1" />
                                        <input
                                            type="number"
                                            class="param-input"
                                            v-model.number="
                                                localConfig.temperature
                                            "
                                            min="0"
                                            max="2"
                                            step="0.1" />
                                    </div>
                                </div>

                                <div class="param-row">
                                    <div class="param-label-group">
                                        <p class="param-name">
                                            Evaluation Method
                                        </p>
                                        <p class="param-desc">
                                            NLI (DeBERTa) is more accurate,
                                            BERTScore is computationally
                                            lighter.
                                        </p>
                                    </div>
                                    <div class="param-input-group">
                                        <select
                                            class="param-select"
                                            v-model="localConfig.method">
                                            <option value="nli">
                                                SelfCheckNLI (DeBERTa)
                                            </option>
                                            <option value="bertscore">
                                                BERTScore
                                            </option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="estimate-card">
                        <i
                            class="ti ti-clock"
                            aria-hidden="true"></i>
                        <div>
                            <p class="estimate-title">
                                Background Processing Time Estimation
                            </p>
                            <p class="estimate-desc">{{ estimatedTimeText }}</p>
                        </div>
                    </div>

                    <div class="action-row">
                        <button
                            class="btn btn-ghost"
                            @click="resetToDefault"
                            type="button">
                            <i
                                class="ti ti-rotate"
                                aria-hidden="true"></i>
                            Reset to Default
                        </button>
                        <div
                            style="
                                display: flex;
                                gap: 10px;
                                align-items: center;
                            ">
                            <Transition name="fade">
                                <span
                                    v-if="saveMessage"
                                    :class="['save-message', saveMessage.type]">
                                    {{ saveMessage.text }}
                                </span>
                            </Transition>
                            <button
                                class="btn btn-primary"
                                @click="handleSave"
                                :disabled="loading.config"
                                type="button">
                                <i
                                    v-if="loading.config"
                                    class="ti ti-loader spin"
                                    aria-hidden="true"></i>
                                Save Configuration
                            </button>
                        </div>
                    </div>
                </template>
            </div>
        </main>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import AppSidebar from '@/components/AppSidebar.vue';
import { useDashboard } from '@/composables/useDashboard.js';

const {
    stats,
    chats,
    config,
    loading,
    llmStatus,
    fetchStats,
    fetchChats,
    fetchConfig,
    saveConfig,
    fetchLlmStatus,
} = useDashboard();

const localConfig = ref(null);
const saveMessage = ref(null);
const showApiKey = ref(false);

const providers = [
    { value: 'ollama', label: 'Ollama', icon: 'ti-server' },
    { value: 'openai', label: 'OpenAI', icon: 'ti-brand-openai' },
    { value: 'fireworks', label: 'Fireworks', icon: 'ti-bolt' },
    { value: 'gemini', label: 'Gemini', icon: 'ti-sparkles' },
    { value: 'none', label: 'No Model', icon: 'ti-ban' },
];

const modelMeta = {
    ollama: {
        placeholder: 'llama3, mistral, phi3, ...',
    },
    openai: {
        placeholder: 'gpt-4o, gpt-4o-mini, gpt-3.5-turbo, ...',
    },
    firework: {
        placeholder: 'accounts/fireworks/models/gpt-oss-20b, ...',
    },
    gemini: {
        placeholder:
            'gemini-3.1-flash-lite, gemini-2.0-flash, gemini-1.5-pro, ...',
    },
    none: { placeholder: '', hint: '' },
};

const providerNeedsKey = computed(() =>
    ['openai', 'fireworks', 'gemini'].includes(localConfig.value?.llm_provider)
);

const isGemini3 = computed(() => {
    if (!localConfig.value) return false;
    const m = localConfig.value.llm_model?.toLowerCase() ?? '';
    return (
        localConfig.value.llm_provider === 'gemini' &&
        (m.startsWith('gemini-3') || m.startsWith('gemini-3.'))
    );
});

const modelPlaceholder = computed(
    () => modelMeta[localConfig.value?.llm_provider]?.placeholder ?? ''
);

const modelHint = computed(
    () => modelMeta[localConfig.value?.llm_provider]?.hint ?? ''
);

const estimatedTimeText = computed(() => {
    if (!localConfig.value) return '–';
    const n = localConfig.value.num_samples;
    const provider = localConfig.value.llm_provider;

    if (provider === 'none')
        return 'Provider is set to "No Model" — no hallucination evaluation.';

    const isCloud = ['openai', 'fireworks', 'gemini'].includes(provider);
    const secPerSample = isCloud ? 3 : 45;
    const totalSec = n * secPerSample;
    const timeStr =
        totalSec < 60
            ? `~${totalSec} seconds`
            : `~${Math.round(totalSec / 60)} minutes`;

    return isCloud
        ? `With N = ${n} samples via ${provider} (cloud), estimated ~${timeStr} per conversation.`
        : `With N = ${n} samples via Ollama (local), estimated ~${timeStr} per conversation. Use a GPU to speed it up.`;
});

onMounted(async () => {
    await Promise.all([fetchConfig(), fetchStats(), fetchChats()]);
    localConfig.value = { ...config.value };
});

const onProviderChange = (provider) => {
    localConfig.value.llm_provider = provider;
    localConfig.value.llm_api_key = '';
    showApiKey.value = false;

    const defaults = {
        ollama: 'llama3',
        openai: 'gpt-4o-mini',
        fireworks: 'accounts/fireworks/models/gpt-oss-20b',
        gemini: 'gemini-3.1-flash-lite',
        none: '',
    };
    localConfig.value.llm_model = defaults[provider] ?? '';
    localConfig.value.llm_base_url =
        provider === 'ollama' ? 'http://localhost:11434' : '';
};

const clampThresholds = (changed) => {
    if (changed === 'high') {
        if (localConfig.value.threshold_high <= localConfig.value.threshold_mid)
            localConfig.value.threshold_mid = Math.max(
                0,
                localConfig.value.threshold_high - 0.05
            );
    } else {
        if (localConfig.value.threshold_mid >= localConfig.value.threshold_high)
            localConfig.value.threshold_high = Math.min(
                1,
                localConfig.value.threshold_mid + 0.05
            );
    }
    localConfig.value.threshold_high =
        Math.round(localConfig.value.threshold_high * 100) / 100;
    localConfig.value.threshold_mid =
        Math.round(localConfig.value.threshold_mid * 100) / 100;
};

const resetToDefault = () => {
    localConfig.value = {
        threshold_high: 0.6,
        threshold_mid: 0.4,
        num_samples: 5,
        temperature: 0.8,
        method: 'nli',
        llm_provider: 'ollama',
        llm_model: 'llama3',
        llm_api_key: '',
        llm_base_url: 'http://localhost:11434',
    };
    showApiKey.value = false;
};

const handleSave = async () => {
    const ok = await saveConfig(localConfig.value);
    saveMessage.value = ok
        ? { type: 'success', text: '✓ Configuration successfully saved' }
        : { type: 'error', text: '✗ Failed to save, please try again' };
    setTimeout(() => {
        saveMessage.value = null;
    }, 3000);
};

const testConnection = async () => {
    await fetchLlmStatus();
};

const countByLabel = (label) => {
    if (!chats.value?.length) return 0;
    return chats.value.filter((c) => {
        if (c.hallucination_score === null) return false;
        const s = c.hallucination_score;
        if (label === 'halusinasi')
            return s >= localConfig.value.threshold_high;
        if (label === 'borderline')
            return (
                s >= localConfig.value.threshold_mid &&
                s < localConfig.value.threshold_high
            );
        return s < localConfig.value.threshold_mid;
    }).length;
};
</script>

<style src="@/styles/configView.css"></style>
