<template>
    <Teleport to="body">
        <button
            v-if="!isOpen"
            class="mobile-menu-btn"
            aria-label="Open menu"
            @click="open">
            <i
                class="ti ti-menu-2"
                aria-hidden="true"></i>
        </button>
    </Teleport>

    <Teleport to="body">
        <Transition name="sidebar-overlay">
            <div
                v-if="isOpen"
                class="sidebar-overlay"
                aria-hidden="true"
                @click="close" />
        </Transition>
    </Teleport>

    <aside
        class="sidebar"
        :class="{ 'sidebar--open': isOpen }"
        aria-label="Sidebar navigation">
        <div class="sidebar-header">
            <div
                class="logo-icon"
                aria-hidden="true">
                AI
            </div>
            <div class="logo-text">
                <h2>AI Chat</h2>
                <p>{{ title }}</p>
            </div>

            <button
                class="sidebar-close-btn"
                aria-label="Close menu"
                @click="close">
                <i
                    class="ti ti-x"
                    aria-hidden="true"></i>
            </button>
        </div>

        <nav
            v-if="hasDefaultSlot"
            class="sidebar-nav"
            aria-label="Main navigation">
            <slot />
        </nav>
        <div
            v-else
            class="sidebar-spacer"></div>

        <template v-if="isDeveloper">
            <div
                class="sidebar-bottom-nav"
                role="navigation"
                aria-label="Navigation menu">
                <span
                    v-if="hasDefaultSlot"
                    class="sidebar-bottom-label">
                    Menu
                </span>
                <div class="bottom-nav-divider"></div>

                <button
                    :class="['bottom-nav-item', { active: isActive('/chat') }]"
                    aria-label="Open AI Chat page"
                    @click="navigate('/chat')">
                    <i
                        class="ti ti-message"
                        aria-hidden="true"></i>
                    AI Chat
                </button>

                <button
                    :class="[
                        'bottom-nav-item',
                        { active: isActive('/dashboard') },
                    ]"
                    aria-label="Open Hallucination Dashboard"
                    @click="navigate('/dashboard')">
                    <i
                        class="ti ti-layout-dashboard"
                        aria-hidden="true"></i>
                    Hallucination Dashboard
                </button>

                <button
                    :class="[
                        'bottom-nav-item',
                        { active: isActive('/config') },
                    ]"
                    aria-label="Open Configuration"
                    @click="navigate('/config')">
                    <i
                        class="ti ti-settings"
                        aria-hidden="true"></i>
                    Configuration
                </button>
            </div>
        </template>

        <div class="sidebar-footer">
            <div class="user-info">
                <div
                    class="avatar"
                    aria-hidden="true">
                    {{ currentUsername.charAt(0).toUpperCase() }}
                </div>
                <span :title="currentUsername">{{ currentUsername }}</span>
            </div>
            <button
                class="logout-btn"
                title="Log out of account"
                aria-label="Logout"
                @click="handleLogout">
                <i
                    class="ti ti-logout"
                    aria-hidden="true"
                    >Logout</i
                >
            </button>
        </div>
    </aside>
</template>

<script setup>
import { computed, useSlots, onMounted, onUnmounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuth } from '@/composables/useAuth.js';
import { useSidebar } from '@/composables/useSidebar.js';

defineProps({
    title: {
        type: String,
        default: 'Personal Assistant',
    },
});

const router = useRouter();
const route = useRoute();
const slots = useSlots();

const { currentUsername, isDeveloper, handleLogout } = useAuth();
const { isOpen, open, close } = useSidebar();

const hasDefaultSlot = computed(() => !!slots.default);

const navigate = (path) => {
    router.push(path);
    close();
};

const isActive = (path) => route.path.startsWith(path);

const handleKeydown = (e) => {
    if (e.key === 'Escape' && isOpen.value) close();
};

onMounted(() => document.addEventListener('keydown', handleKeydown));
onUnmounted(() => document.removeEventListener('keydown', handleKeydown));
</script>

<style scoped>
.sidebar-spacer {
    flex: 1;
}

.sidebar-close-btn {
    margin-left: auto;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--color-text-muted);
    font-size: 18px;
    display: none;
    align-items: center;
    padding: 4px 6px;
    border-radius: var(--radius-sm);
    transition: color 0.15s, background 0.15s;
    flex-shrink: 0;
}
.sidebar-close-btn:hover {
    color: var(--color-text-primary);
    background: var(--color-border);
}
</style>
