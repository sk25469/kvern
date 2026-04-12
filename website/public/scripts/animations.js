// ===== ANIMATIONS.JS - Visual Effects and Trie Animation =====

document.addEventListener('DOMContentLoaded', function() {
    initializeAnimations();
});

function initializeAnimations() {
    setupTrieAnimation();
    setupHoverEffects();
    setupCounterAnimations();
    console.log('Animations initialized');
}

// ===== TRIE ANIMATION =====
function setupTrieAnimation() {
    const trieAnimation = document.querySelector('.trie-animation');
    if (!trieAnimation) return;
    
    // Start animation after a short delay
    setTimeout(() => {
        trieAnimation.classList.add('active');
        startTokenFlow();
    }, 1000);
}

function startTokenFlow() {
    const tokenFlow = document.querySelector('.token-flow');
    const trieNodes = document.querySelectorAll('.trie-node.hit');
    
    if (!tokenFlow) return;
    
    // Animate token flow every 3 seconds
    setInterval(() => {
        animateTokenSequence();
    }, 3000);
}

function animateTokenSequence() {
    const tokens = document.querySelectorAll('.token');
    const hitNode = document.querySelector('.trie-node.hit');
    
    // Reset all tokens
    tokens.forEach((token, index) => {
        token.style.animation = 'none';
        token.offsetHeight; // Trigger reflow
        token.style.animation = `tokenFlow 2s ease-in-out ${index * 0.3}s`;
    });
    
    // Animate hit node after tokens reach it
    if (hitNode) {
        setTimeout(() => {
            hitNode.style.animation = 'none';
            hitNode.offsetHeight; // Trigger reflow
            hitNode.style.animation = 'trieHit 1s ease-in-out';
        }, 1200);
    }
}

// ===== HOVER EFFECTS =====
function setupHoverEffects() {
    // Enhanced button hover effects
    const buttons = document.querySelectorAll('.btn-primary, .btn-secondary');
    
    buttons.forEach(button => {
        button.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });
        
        button.addEventListener('mouseleave', function() {
            if (!this.classList.contains('copied')) {
                this.style.transform = 'translateY(0)';
            }
        });
    });
    
    // Glass card hover effects
    const cards = document.querySelectorAll('.glass-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-4px)';
            this.style.borderColor = 'var(--accent-violet)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.borderColor = 'var(--border-gray)';
        });
    });
}

// ===== COUNTER ANIMATIONS =====
function setupCounterAnimations() {
    const counters = document.querySelectorAll('.metric-value');
    
    const counterObserver = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
            }
        });
    }, { threshold: 0.5 });
    
    counters.forEach(counter => counterObserver.observe(counter));
}

function animateCounter(element) {
    const finalValue = parseFloat(element.getAttribute('data-value')) || 
                      parseFloat(element.textContent.replace(/[^0-9.]/g, ''));
    const duration = 2000; // 2 seconds
    const steps = 60;
    const increment = finalValue / steps;
    const stepDuration = duration / steps;
    
    let currentValue = 0;
    
    const timer = setInterval(() => {
        currentValue += increment;
        
        if (currentValue >= finalValue) {
            currentValue = finalValue;
            clearInterval(timer);
        }
        
        // Format the number based on its type
        let displayValue;
        if (element.textContent.includes('$')) {
            displayValue = `$${Math.round(currentValue).toLocaleString()}`;
        } else if (element.textContent.includes('%')) {
            displayValue = `${Math.round(currentValue * 10) / 10}%`;
        } else {
            displayValue = Math.round(currentValue).toLocaleString();
        }
        
        element.textContent = displayValue;
    }, stepDuration);
}

// ===== PARTICLE EFFECTS =====
function createParticleEffect(container, options = {}) {
    const defaults = {\n        particleCount: 20,
        colors: ['var(--accent-green)', 'var(--accent-violet)'],
        size: { min: 2, max: 6 },
        speed: { min: 1, max: 3 },
        lifetime: 3000
    };
    
    const config = { ...defaults, ...options };
    
    for (let i = 0; i < config.particleCount; i++) {
        setTimeout(() => {
            createParticle(container, config);
        }, i * 100);
    }
}

function createParticle(container, config) {
    const particle = document.createElement('div');
    particle.className = 'particle';
    
    // Random properties
    const size = Math.random() * (config.size.max - config.size.min) + config.size.min;
    const color = config.colors[Math.floor(Math.random() * config.colors.length)];
    const speed = Math.random() * (config.speed.max - config.speed.min) + config.speed.min;
    
    // Initial position
    const startX = Math.random() * container.offsetWidth;
    const startY = container.offsetHeight;
    
    // Styling
    Object.assign(particle.style, {
        position: 'absolute',
        left: startX + 'px',
        top: startY + 'px',
        width: size + 'px',
        height: size + 'px',
        backgroundColor: color,
        borderRadius: '50%',
        pointerEvents: 'none',
        zIndex: '-1',
        boxShadow: `0 0 ${size * 2}px ${color}`,
        transition: `all ${config.lifetime}ms ease-out`
    });
    
    container.appendChild(particle);
    
    // Animate
    requestAnimationFrame(() => {
        particle.style.transform = `translateY(-${container.offsetHeight + 50}px) translateX(${(Math.random() - 0.5) * 100}px)`;
        particle.style.opacity = '0';
    });
    
    // Remove after animation
    setTimeout(() => {
        if (particle.parentNode) {
            particle.parentNode.removeChild(particle);
        }
    }, config.lifetime);
}

// ===== INTERSECTION OBSERVER FOR ADVANCED ANIMATIONS =====
function setupAdvancedScrollAnimations() {
    const animationObserver = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const animationType = entry.target.dataset.animation;\n                \n                switch(animationType) {
                    case 'slide-up':
                        entry.target.classList.add('animate-fade-in-up');
                        break;
                    case 'slide-left':
                        entry.target.classList.add('animate-slide-in-left');
                        break;
                    case 'slide-right':
                        entry.target.classList.add('animate-slide-in-right');
                        break;
                    case 'scale':
                        entry.target.style.transform = 'scale(1)';
                        entry.target.style.opacity = '1';
                        break;
                    default:
                        entry.target.classList.add('animate-fade-in-up');
                }
            }
        });
    }, { 
        threshold: 0.1,
        rootMargin: '0px 0px -10% 0px'
    });
    
    // Observe all elements with data-animation attribute
    const animatedElements = document.querySelectorAll('[data-animation]');
    animatedElements.forEach(el => animationObserver.observe(el));
}

// ===== PERFORMANCE OPTIMIZATIONS =====
function optimizeAnimations() {
    // Use will-change property for animated elements
    const animatedElements = document.querySelectorAll('.trie-animation, .token, .trie-node');
    animatedElements.forEach(el => {
        el.style.willChange = 'transform, opacity';
    });
    
    // Cleanup will-change after animations complete
    setTimeout(() => {
        animatedElements.forEach(el => {
            el.style.willChange = 'auto';
        });
    }, 5000);
}

// ===== INITIALIZE ADVANCED FEATURES =====
setTimeout(() => {
    setupAdvancedScrollAnimations();
    optimizeAnimations();
}, 1000);

// ===== EXPORT FOR MODULE USE =====
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        setupTrieAnimation,
        animateCounter,
        createParticleEffect
    };
}