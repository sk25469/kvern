// ===== MAIN.JS - Core Functionality =====

document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    setupClipboard();
    setupScrollReveal();
    setupNavigation();
    console.log('KVern website initialized');
}

// ===== CLIPBOARD FUNCTIONALITY =====
function setupClipboard() {
    const cloneBtn = document.getElementById('clone-btn');
    
    if (cloneBtn) {
        cloneBtn.addEventListener('click', function() {
            const gitCommand = 'git clone https://github.com/[user]/kvern.git';
            
            // Try to copy to clipboard
            if (navigator.clipboard) {
                navigator.clipboard.writeText(gitCommand).then(function() {
                    showCopySuccess(cloneBtn);
                }).catch(function(err) {
                    console.error('Failed to copy: ', err);
                    fallbackCopy(gitCommand);
                });
            } else {
                fallbackCopy(gitCommand);
            }
        });
    }
}

function showCopySuccess(button) {
    const originalText = button.innerHTML;
    button.innerHTML = '<span class=\"mono-text\">✓ Copied to clipboard!</span>';
    button.classList.add('copied');
    
    setTimeout(() => {
        button.innerHTML = originalText;\n        button.classList.remove('copied');
    }, 2000);
}

function fallbackCopy(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        console.log('Fallback copy successful');
    } catch (err) {
        console.error('Fallback copy failed: ', err);
    }
    
    document.body.removeChild(textArea);
}

// ===== SCROLL REVEAL ANIMATIONS =====
function setupScrollReveal() {
    // Create intersection observer for scroll animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const scrollObserver = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
            }
        });
    }, observerOptions);
    
    // Observe elements with scroll-reveal class
    const revealElements = document.querySelectorAll('.scroll-reveal');
    revealElements.forEach(el => scrollObserver.observe(el));
}

// ===== NAVIGATION =====
function setupNavigation() {
    const header = document.querySelector('.nav-header');
    if (!header) return;
    
    let lastScrollTop = 0;
    
    window.addEventListener('scroll', function() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        if (scrollTop > 100) {
            header.classList.add('visible');
        } else {
            header.classList.remove('visible');
        }
        
        lastScrollTop = scrollTop;
    });
}

// ===== UTILITY FUNCTIONS =====
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}

// ===== SMOOTH SCROLLING FOR INTERNAL LINKS =====
document.addEventListener('click', function(e) {
    const target = e.target.closest('a[href^=\"#\"]');
    if (!target) return;
    
    e.preventDefault();
    const targetId = target.getAttribute('href');
    const targetElement = document.querySelector(targetId);
    
    if (targetElement) {
        targetElement.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
});

// ===== PERFORMANCE MONITORING =====
if ('IntersectionObserver' in window) {
    // Enhanced scroll performance
    const scrollHandler = throttle(function() {
        // Handle scroll-based animations here if needed
    }, 16); // ~60fps
    
    window.addEventListener('scroll', scrollHandler, { passive: true });
}

// ===== ERROR HANDLING =====
window.addEventListener('error', function(e) {
    console.error('JavaScript error:', e.error);
    // Could send to analytics in production
});

// ===== EXPORT FOR MODULE USE =====
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        setupClipboard,
        setupScrollReveal,
        setupNavigation
    };
}