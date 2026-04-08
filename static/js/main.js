// Common JS for all pages

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
        document.body.style.transition = 'opacity 0.4s ease';
        document.body.style.opacity = '1';
    }, 50);
}

document.addEventListener('DOMContentLoaded', initPage);

function formatSummary(text) {
    return text
        .replace(/^### (.*$)/gim, '<h4>$1</h4>')
        .replace(/^## (.*$)/gim, '<h3>$1</h3>')
        .replace(/^# (.*$)/gim, '<h2>$1</h2>')
        .replace(/^- (.*$)/gim, '<ul><li>$1</li></ul>')
        .replace(/^\d+\. (.*$)/gim, '<ol><li>$1</li></ol>')
        .replace(/\n\n/g, '<br><br>');
}

