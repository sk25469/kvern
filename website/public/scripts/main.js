// ===== MAIN.JS - Core Functionality =====

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Main.js loaded and DOM ready');
    initializeApp();
});

function initializeApp() {
    console.log('🔧 Initializing app...');
    setupClipboard();
    setupScrollReveal();
    setupNavigation();
    console.log('✅ KVern website initialized');
}

// ===== CLIPBOARD FUNCTIONALITY =====
function setupClipboard() {
    const cloneBtn = document.getElementById('clone-btn');
    
    if (cloneBtn) {
        cloneBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            
            const gitCommand = 'git clone https://github.com/user/kvern.git';
            
            try {
                // Modern browsers with clipboard API
                if (navigator.clipboard && window.isSecureContext) {
                    await navigator.clipboard.writeText(gitCommand);
                    showCopySuccess(cloneBtn);
                    console.log('Copied using Clipboard API');
                } else {
                    // Fallback for older browsers or non-HTTPS
                    fallbackCopy(gitCommand);
                    showCopySuccess(cloneBtn);
                    console.log('Copied using fallback method');
                }
            } catch (error) {
                console.error('Copy failed:', error);
                // Show error message
                showCopyError(cloneBtn);
            }
        });
    }
}

function showCopySuccess(button) {
    const originalHTML = button.innerHTML;
    button.innerHTML = '<span class="mono-text">✓ Copied to clipboard!</span>';
    button.classList.add('copied');
    button.style.background = 'linear-gradient(135deg, #22C55E, #16a34a)';
    
    setTimeout(() => {
        button.innerHTML = originalHTML;
        button.classList.remove('copied');
        button.style.background = '';
    }, 2500);
}

function showCopyError(button) {
    const originalHTML = button.innerHTML;
    button.innerHTML = '<span class="mono-text">✗ Copy failed</span>';
    button.style.background = 'linear-gradient(135deg, #ef4444, #dc2626)';
    
    setTimeout(() => {
        button.innerHTML = originalHTML;
        button.style.background = '';
    }, 2000);
}

function fallbackCopy(text) {
    // Create a temporary textarea element
    const textArea = document.createElement('textarea');
    textArea.value = text;
    
    // Style it to be invisible
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    textArea.style.opacity = '0';
    
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (!successful) {
            throw new Error('execCommand copy failed');
        }
    } finally {
        document.body.removeChild(textArea);
    }
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