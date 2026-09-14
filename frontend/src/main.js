import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import App from './App.vue';

import '@/styles/base.css';
import '@/styles/sidebar.css';

import LoginView from '@/views/LoginView.vue';
import ChatView from '@/views/ChatView.vue';
import DashboardView from '@/views/DashboardView.vue';
import ParticipantsView from '@/views/ParticipantsView.vue';
import ConfigView from '@/views/ConfigView.vue';
import MaintenanceView from '@/views/MaintenanceView.vue';

const router = createRouter({
    history: createWebHistory(),
    routes: [
        // { path: '/', redirect: '/noservice' },
        // {
        //     path: '/noservice',
        //     component: MaintenanceView,
        // },
        // {
        //     path: '/:pathMatch(.*)*',
        //     redirect: '/noservice',
        // },

        { path: '/', redirect: '/login' },
        { path: '/login', component: LoginView },
        {
            path: '/chat',
            component: ChatView,
            meta: { requiresAuth: true },
        },
        {
            path: '/dashboard',
            component: DashboardView,
            meta: { requiresAuth: true, role: 'developer' },
        },
        {
            path: '/participants',
            component: ParticipantsView,
            meta: { requiresAuth: true, role: 'developer' },
        },
        {
            path: '/config',
            component: ConfigView,
            meta: { requiresAuth: true, role: 'developer' },
        },
    ],
});

router.beforeEach((to, _from, next) => {
    const token = localStorage.getItem('token');

    if (to.meta.requiresAuth && !token) {
        return next('/login');
    }

    if (token && to.meta.role) {
        let role = 'user';
        try {
            const payload = JSON.parse(
                atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))
            );
            role = payload.role ?? 'user';
        } catch {}

        if (to.meta.role === 'developer' && role !== 'developer') {
            return next('/chat');
        }
        if (to.meta.role === 'user' && role === 'developer') {
            return next('/dashboard');
        }
    }

    next();
});

createApp(App).use(router).mount('#app');
