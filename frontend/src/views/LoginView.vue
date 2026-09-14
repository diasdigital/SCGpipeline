<template>
    <div class="login-container">
        <div class="login-card">
            <h1 class="title">Welcome Back</h1>
            <p class="subtitle">Sign in to your account to continue.</p>

            <form
                @submit.prevent="handleLogin"
                class="form-group">
                <div class="input-wrapper">
                    <label>USERNAME</label>
                    <div class="input-box">
                        <span class="icon">✉️</span>
                        <input
                            v-model="username"
                            type="text"
                            placeholder="Enter username..."
                            required />
                    </div>
                </div>

                <div class="input-wrapper">
                    <div class="label-row">
                        <label>PASSWORD</label>
                    </div>
                    <div class="input-box">
                        <span class="icon">🔒</span>
                        <input
                            v-model="password"
                            type="password"
                            placeholder="••••••••"
                            required />
                    </div>
                </div>

                <p
                    v-if="errorMessage"
                    class="error-text">
                    {{ errorMessage }}
                </p>

                <button
                    type="submit"
                    :disabled="isLoading">
                    {{ isLoading ? 'LOADING...' : 'SIGN IN ➔' }}
                </button>
            </form>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api from '@/api/axios';

const router = useRouter();
const username = ref('');
const password = ref('');
const errorMessage = ref('');
const isLoading = ref(false);

const handleLogin = async () => {
    isLoading.value = true;
    errorMessage.value = '';

    try {
        const formData = new URLSearchParams();
        formData.append('username', username.value);
        formData.append('password', password.value);

        const response = await api.post('/api/auth/login', formData, {
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        });

        localStorage.setItem('token', response.data.access_token);

        router.push('/chat');
    } catch (error) {
        if (error.response && error.response.status === 401) {
            errorMessage.value = 'Incorrect username or password.';
        } else if (error.response && error.response.status === 422) {
            errorMessage.value = 'Invalid data format.';
        } else {
            errorMessage.value = 'A server error occurred.';
        }
    } finally {
        isLoading.value = false;
    }
};
</script>

<style scoped>
.login-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background-color: #ffffff;
}

.login-card {
    width: 100%;
    max-width: 400px;
    padding: 40px;
}

.title {
    font-size: 24px;
    color: #1a1a1a;
    margin-bottom: 8px;
    font-weight: 600;
}

.subtitle {
    color: #666;
    font-size: 14px;
    margin-bottom: 30px;
}

.input-wrapper {
    margin-bottom: 20px;
}

label {
    display: block;
    font-size: 12px;
    font-weight: 700;
    color: #333;
    margin-bottom: 6px;
    letter-spacing: 0.5px;
}

.label-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.forgot-link {
    font-size: 12px;
    color: #5c6bc0;
    text-decoration: none;
    font-weight: 600;
}

.input-box {
    display: flex;
    align-items: center;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 10px 14px;
    background-color: #fff;
    transition: border-color 0.2s;
}

.input-box:focus-within {
    border-color: #5c6bc0;
}

.icon {
    margin-right: 10px;
    color: #9ca3af;
    font-size: 16px;
}

input {
    border: none;
    outline: none;
    flex: 1;
    font-size: 14px;
    color: #333;
}

.error-text {
    color: #d32f2f;
    font-size: 13px;
    margin-bottom: 10px;
}

button {
    width: 100%;
    padding: 12px;
    background-color: transparent;
    color: #333;
    border: none;
    font-weight: 700;
    font-size: 14px;
    cursor: pointer;
    margin-top: 10px;
    display: flex;
    justify-content: center;
    align-items: center;
    letter-spacing: 1px;
}

button:hover {
    color: #000;
}

button:disabled {
    color: #999;
    cursor: not-allowed;
}
</style>
