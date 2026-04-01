// Common JS for all pages - extracted from index.html + nav enhancements

// Auth system
function isLoggedIn() {
    return localStorage.getItem('researchportal_logged_in') === 'true';
}

function setLoggedIn(status) {
    localStorage.setItem('researchportal_logged_in', status ? 'true' : 'false');
    toggleMainApp();
}

function toggleMainApp() {
    const authSection = document.getElementById('authSection');
    const mainApp = document.getElementById('mainApp');
    const loginBtn = document.getElementById('loginBtn');
    if (isLoggedIn()) {
        authSection.style.display = 'none';
        mainApp.style.display = 'block';
        loginBtn.textContent = 'Logout';
    } else {
        authSection.style.display = 'flex';
        mainApp.style.display = 'none';
        loginBtn.textContent = 'Login';
    }
}

// Auth handlers (login/signup tabs, submit)
let currentAuthMode = 'login';
function initAuthMode(mode) {
    const loginTab = document.getElementById('loginTab');
    const signupTab = document.getElementById('signupTab');
    const authSubmit = document.getElementById('authSubmit');
    const authMessage = document.getElementById('authMessage');
    currentAuthMode = mode;
    if (mode === 'signup') {
        signupTab.style.background = '#00bcd4';
        signupTab.style.color = '#000';
        loginTab.style.background = '#fff';
        loginTab.style.color = '#000';
        authSubmit.textContent = 'Sign Up';
        authMessage.textContent = '';
    } else {
        loginTab.style.background = '#00bcd4';
        loginTab.style.color = '#000';
        signupTab.style.background = '#fff';
        signupTab.style.color = '#000';
        authSubmit.textContent = 'Login';
        authMessage.textContent = '';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (!isLoggedIn()) {
        initAuthMode('login');
    }
    toggleMainApp();
    
    // Login button
    document.getElementById('loginBtn').addEventListener('click', () => {
        const authSection = document.getElementById('authSection');
        if (isLoggedIn()) {
            setLoggedIn(false);
        } else {
            authSection.style.display = 'flex';
        }
    });

    // Auth tabs
    document.getElementById('loginTab').addEventListener('click', () => initAuthMode('login'));
    document.getElementById('signupTab').addEventListener('click', () => initAuthMode('signup'));

    // Auth submit
    document.getElementById('authSubmit').addEventListener('click', () => {
        const authUsername = document.getElementById('authUsername');
        const authPassword = document.getElementById('authPassword');
        const authMessage = document.getElementById('authMessage');
        const authSubmit = document.getElementById('authSubmit');
        const username = authUsername.value.trim();
        const password = authPassword.value.trim();
        if (!username || !password) {
            authMessage.textContent = 'Username and password are required.';
            return;
        }
        const users = JSON.parse(localStorage.getItem('researchportal_users') || '{}');
        if (authSubmit.textContent === 'Sign Up') {
            if (users[username]) {
                authMessage.textContent = 'User already exists. Please login.';
                return;
            }
            users[username] = password;
            localStorage.setItem('researchportal_users', JSON.stringify(users));
            authMessage.textContent = 'Signup successful. Please login now.';
            initAuthMode('login');
            authUsername.value = '';
            authPassword.value = '';
            return;
        }
        // Login
        if (users[username] === password) {
            setLoggedIn(true);
            authMessage.textContent = '';
            authUsername.value = '';
            authPassword.value = '';
            return;
        }
        authMessage.textContent = 'Invalid credentials. Try again.';
    });

    // Page-specific init
    initPage();
});

// Navigation active highlight
function setActiveNav(currentPage) {
    const navLinks = document.querySelectorAll('nav ul li a');
    navLinks.forEach(link => link.parentElement.classList.remove('active'));
    const activeLink = Array.from(navLinks).find(link => link.getAttribute('href').includes(currentPage));
    if (activeLink) {
        activeLink.parentElement.classList.add('active');
    }
}

// Smooth page fade transition
function initPage() {
    document.body.style.opacity = '0';
    setTimeout(() => {
        document.body.style.transition = 'opacity 0.5s';
        document.body.style.opacity = '1';
    }, 50);
}

// Called by page-specific JS
let topics = {};
let keywordChart = null;
let topicTrendChart = null;

function formatSummary(text) {
    return text
        .replace(/^### (.*$)/gim, '<h4>$1</h4>')
        .replace(/^## (.*$)/gim, '<h3>$1</h3>')
        .replace(/^# (.*$)/gim, '<h2>$1</h2>')
        .replace(/^- (.*$)/gim, '<ul><li>$1</li></ul>')
        .replace(/^\d+\. (.*$)/gim, '<ol><li>$1</li></ol>')
        .replace(/\n\n/g, '<br><br>');
}

