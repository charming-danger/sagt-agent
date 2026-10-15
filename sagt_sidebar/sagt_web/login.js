// 登录页面 JavaScript
class LoginManager {
    constructor() {
        this.apiBaseUrl = '/api';
        this.init();
    }

    init() {
        const loginForm = document.getElementById('loginForm');

        // 从主页面因登录失效跳转过来时，给出提示
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('expired') === '1') {
            this.showError('登录已失效，请重新登录');
        }

        // 绑定登录表单提交事件（无论是否已有 token 都先绑定，保证校验失败时表单可用）
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleLogin();
        });

        // 回车键登录
        document.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                loginForm.dispatchEvent(new Event('submit'));
            }
        });

        // 检查是否已经登录：需要向后端校验 token，
        // 避免服务重启后残留的旧 token 导致在登录页和主页面之间来回跳转
        const token = localStorage.getItem('sagt_token');
        if (token) {
            this.validateToken(token);
        }
    }

    // 向后端校验 token 是否仍然有效
    async validateToken(token) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/get_interrupt`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                // token 有效，进入主页面
                this.redirectToMain();
                return;
            }

            if (response.status === 401) {
                // token 已失效（服务重启或过期），清除本地登录状态，留在登录页
                localStorage.removeItem('sagt_token');
                localStorage.removeItem('sagt_username');
                this.showError('登录已失效，请重新登录');
            }
        } catch (error) {
            // 网络异常等情况：不跳转，留在登录页由用户自行处理
            console.error('校验登录状态失败:', error);
        }
    }

    async handleLogin() {
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value.trim();
        const loginBtn = document.getElementById('loginBtn');
        const btnText = loginBtn.querySelector('.btn-text');
        const loadingSpinner = loginBtn.querySelector('.loading-spinner');
        const errorMessage = document.getElementById('errorMessage');

        // 验证输入
        if (!username || !password) {
            this.showError('请输入用户名和密码');
            return;
        }

        // 显示加载状态
        loginBtn.disabled = true;
        btnText.style.display = 'none';
        loadingSpinner.style.display = 'inline';
        this.hideError();

        try {
            const response = await fetch(`${this.apiBaseUrl}/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: username,
                    password: password
                })
            });

            const data = await response.json();

            if (data.success) {
                // 保存令牌
                localStorage.setItem('sagt_token', data.token);
                localStorage.setItem('sagt_username', username);
                
                // 跳转到主页面
                this.redirectToMain();
            } else {
                this.showError(data.message || '登录失败');
            }
        } catch (error) {
            console.error('登录错误:', error);
            this.showError('网络连接失败，请检查服务器是否启动');
        } finally {
            // 恢复按钮状态
            loginBtn.disabled = false;
            btnText.style.display = 'inline';
            loadingSpinner.style.display = 'none';
        }
    }

    showError(message) {
        const errorMessage = document.getElementById('errorMessage');
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
    }

    hideError() {
        const errorMessage = document.getElementById('errorMessage');
        errorMessage.style.display = 'none';
    }

    redirectToMain() {
        window.location.href = 'index.html';
    }
}

// 初始化登录管理器
document.addEventListener('DOMContentLoaded', () => {
    new LoginManager();
});
