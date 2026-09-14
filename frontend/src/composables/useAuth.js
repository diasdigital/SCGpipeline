import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';

export function useAuth() {
    const router = useRouter();

    function decodeTokenPayload() {
        const token = localStorage.getItem('token');
        if (!token) return {};
        try {
            const base64Url = token.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const jsonPayload = decodeURIComponent(
                atob(base64)
                    .split('')
                    .map(
                        (c) =>
                            '%' +
                            ('00' + c.charCodeAt(0).toString(16)).slice(-2)
                    )
                    .join('')
            );
            return JSON.parse(jsonPayload);
        } catch {
            return {};
        }
    }

    const payload = decodeTokenPayload();

    const currentUsername = ref(payload.sub ?? 'User');
    const currentRole = ref(payload.role ?? 'user');

    const isDeveloper = computed(() => currentRole.value === 'developer');

    const getToken = () => localStorage.getItem('token');

    const handleLogout = () => {
        localStorage.removeItem('token');
        router.push('/login');
    };

    return {
        currentUsername,
        currentRole,
        isDeveloper,
        getToken,
        handleLogout,
    };
}
