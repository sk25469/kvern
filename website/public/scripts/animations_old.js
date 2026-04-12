// ===== ANIMATIONS.JS - Clean Version =====

document.addEventListener('DOMContentLoaded', function() {
    console.log('🎬 Animations.js loaded');
    initializeAnimations();
});

function initializeAnimations() {
    // Visual feedback that JavaScript is working
    const trieAnimation = document.querySelector('.trie-animation');
    if (trieAnimation) {
        trieAnimation.style.borderColor = '#22C55E';
        setTimeout(() => {
            trieAnimation.style.borderColor = '#334155';
        }, 2000);
    }
    
    setupTrieAnimation();
    setupHoverEffects();
    console.log('✅ Animations initialized');
}

// ===== TRIE ANIMATION =====
function setupTrieAnimation() {
    console.log('🎯 Setting up trie animation...');
    const trieAnimation = document.querySelector('.trie-animation');
    console.log('Trie animation element:', trieAnimation);
    
    if (!trieAnimation) {
        console.error('❌ Trie animation element not found!');
        return;
    }
    
    // Initialize stats
    let cacheHits = 0;
    let cacheMisses = 0;
    let totalRequests = 0;
    
    // Define different request scenarios
    const scenarios = [
        { type: 'system_hit', path: ['root', 'system', 'hit'], isHit: true, description: 'System prompt reuse' },
        { type: 'user_hit', path: ['root', 'user', 'hit'], isHit: true, description: 'Chat history reuse' }, 
        { type: 'new_request', path: ['root', 'system', 'new'], isHit: false, description: 'New content' },
        { type: 'user_new', path: ['root', 'user', 'new'], isHit: false, description: 'Novel user query' }
    ];
    
    // Start animation after a short delay
    setTimeout(() => {
        console.log('🚀 Starting realistic trie animation...');
        trieAnimation.classList.add('active');
        
        // Run scenarios with realistic timing
        runRealisticSequence(scenarios, cacheHits, cacheMisses, totalRequests);
        
    }, 1000);
    
    // Add test button functionality
    const testButton = document.getElementById('test-animation');
    if (testButton) {
        console.log('✅ Test button found, adding click handler');
        testButton.addEventListener('click', function() {
            console.log('🧪 Manual animation test triggered');
            const randomScenario = scenarios[Math.floor(Math.random() * scenarios.length)];
            runSingleScenario(randomScenario, Math.floor(Math.random() * 10), Math.floor(Math.random() * 5), Math.floor(Math.random() * 15));
        });
    } else {
        console.error('❌ Test button not found!');
    }
}

function runRealisticSequence(scenarios, hits, misses, total) {
    // Pick a random scenario (80% chance of hit, 20% chance of miss - realistic cache behavior)
    const randomValue = Math.random();
    let selectedScenario;
    
    if (randomValue < 0.8) {
        // 80% chance - pick a cache hit scenario
        selectedScenario = scenarios.filter(s => s.isHit)[Math.floor(Math.random() * 2)];
        hits++;
    } else {
        // 20% chance - pick a cache miss scenario  
        selectedScenario = scenarios.filter(s => !s.isHit)[Math.floor(Math.random() * 2)];
        misses++;
    }
    
    total++;
    
    console.log(`🎲 Selected scenario: ${selectedScenario.description} (${selectedScenario.isHit ? 'HIT' : 'MISS'})`);
    
    runSingleScenario(selectedScenario, hits, misses, total);
    
    // Schedule next animation with varying intervals (2-6 seconds)
    const nextInterval = 2000 + Math.random() * 4000;
    setTimeout(() => {
        runRealisticSequence(scenarios, hits, misses, total);
    }, nextInterval);
}

function runSingleScenario(scenario, hits, misses, total) {
    console.log('🔄 Running scenario:', scenario);
    
    // Reset all tokens and nodes
    resetAllElements();
    
    // Animate tokens following the specific path
    animateTokensAlongPath(scenario.path, scenario.isHit);
    
    // Update stats after animation completes
    setTimeout(() => {
        updateRealisticStats(hits, misses, total, scenario);
    }, 2200);
}

function resetAllElements() {
    // Reset all tokens
    const tokens = document.querySelectorAll('.token');
    tokens.forEach(token => {
        token.style.transform = 'translateX(0px)';
        token.style.opacity = '0';
        token.style.background = '#22C55E'; // Reset to green
    });
    
    // Reset all nodes
    const nodes = document.querySelectorAll('.trie-node');
    nodes.forEach(node => {
        node.style.transform = 'scale(1)';
        node.style.background = '';
        node.style.boxShadow = '';
    });
    
    // Reset hit indicator
    const hitIndicator = document.querySelector('.hit-indicator');
    if (hitIndicator) {
        hitIndicator.style.opacity = '0';
        hitIndicator.style.transform = 'scale(0)';
    }
}

function animateTokensAlongPath(path, isHit) {
    const tokens = document.querySelectorAll('.token');
    
    tokens.forEach((token, index) => {
        setTimeout(() => {
            animateTokenAlongPath(token, path, isHit, index);
        }, index * 300);
    });
}

function animateTokenAlongPath(token, path, isHit, tokenIndex) {
    console.log(`🎯 Animating token ${tokenIndex} along path:`, path);
    
    // Set token color based on outcome
    if (!isHit) {
        token.style.background = '#f59e0b'; // Orange for misses
        token.style.boxShadow = '0 0 12px rgba(245, 158, 11, 0.8)';
    }
    
    // Show token
    token.style.opacity = '1';
    token.style.transition = 'all 0.8s ease-in-out';
    
    // Move to root first
    setTimeout(() => {
        token.style.transform = 'translateX(180px) translateY(-80px)';
    }, 100);
    
    // Move to second level  
    setTimeout(() => {
        if (path[1] === 'system') {
            token.style.transform = 'translateX(120px) translateY(-20px)';
        } else {
            token.style.transform = 'translateX(280px) translateY(-20px)';
        }
    }, 400);
    
    // Move to final destination
    setTimeout(() => {
        if (path[2] === 'hit') {
            token.style.transform = 'translateX(80px) translateY(60px)';
            // Trigger hit animation
            setTimeout(() => triggerNodeHit(path[2]), 200);
        } else {
            token.style.transform = 'translateX(200px) translateY(60px)';
            // Trigger miss animation
            setTimeout(() => triggerNodeMiss(path[2]), 200);
        }
    }, 800);
    
    // Hide token
    setTimeout(() => {
        token.style.opacity = '0';
    }, 1400);
}

function triggerNodeHit(nodeType) {
    console.log('💥 Cache HIT!');
    
    const hitNode = document.querySelector('.hit-node');
    const hitIndicator = document.querySelector('.hit-indicator');
    const hitLine = document.querySelector('.hit-line');
    
    if (hitNode) {
        hitNode.style.transition = 'all 0.3s ease-out';
        hitNode.style.transform = 'scale(1.3)';
        hitNode.style.background = 'rgba(34, 197, 94, 0.9)';
        hitNode.style.boxShadow = '0 0 25px rgba(34, 197, 94, 1)';
        
        setTimeout(() => {
            hitNode.style.transform = 'scale(1)';
            hitNode.style.background = 'rgba(34, 197, 94, 0.3)';
            hitNode.style.boxShadow = '0 0 15px rgba(34, 197, 94, 0.5)';
        }, 500);
    }
    
    if (hitIndicator) {
        hitIndicator.textContent = '✓';
        hitIndicator.style.opacity = '1';
        hitIndicator.style.transform = 'scale(1)';
        hitIndicator.style.background = '#22C55E';
        
        setTimeout(() => {
            hitIndicator.style.opacity = '0';
            hitIndicator.style.transform = 'scale(0)';
        }, 1500);
    }
    
    if (hitLine) {
        hitLine.style.stroke = '#22C55E';
        hitLine.style.strokeWidth = '6';
        hitLine.style.filter = 'drop-shadow(0 0 10px rgba(34, 197, 94, 0.8))';
        
        setTimeout(() => {
            hitLine.style.strokeWidth = '3';
            hitLine.style.filter = 'drop-shadow(0 0 6px rgba(34, 197, 94, 0.6))';
        }, 800);
    }
}

function triggerNodeMiss(nodeType) {
    console.log('❌ Cache MISS');
    
    const newNode = document.querySelector('.trie-node.level-2.center');
    const hitIndicator = document.querySelector('.hit-indicator');
    
    if (newNode) {
        newNode.style.transition = 'all 0.3s ease-out';
        newNode.style.transform = 'scale(1.2)';
        newNode.style.background = 'rgba(245, 158, 11, 0.8)';
        newNode.style.boxShadow = '0 0 20px rgba(245, 158, 11, 0.9)';
        
        setTimeout(() => {
            newNode.style.transform = 'scale(1)';
            newNode.style.background = 'rgba(148, 163, 184, 0.2)';
            newNode.style.boxShadow = '';
        }, 500);
    }
    
    if (hitIndicator) {
        hitIndicator.textContent = '○';
        hitIndicator.style.opacity = '1';
        hitIndicator.style.transform = 'scale(1)';
        hitIndicator.style.background = '#f59e0b';
        
        setTimeout(() => {
            hitIndicator.style.opacity = '0';
            hitIndicator.style.transform = 'scale(0)';
        }, 1500);
    }
}

function updateStats(hits, tokens) {
    console.log('📊 Updating stats:', { hits, tokens });
    
    const hitsElement = document.getElementById('cache-hits');
    const tokensElement = document.getElementById('tokens-saved');
    
    console.log('Stats elements:', { hitsElement, tokensElement });
    
    if (hitsElement) {
        hitsElement.textContent = hits;
        hitsElement.style.transition = 'all 0.3s ease-out';
        hitsElement.style.transform = 'scale(1.2)';
        hitsElement.style.color = '#22C55E';
        
        setTimeout(() => {
            hitsElement.style.transform = 'scale(1)';
            hitsElement.style.color = '';
        }, 300);
    }
    
    if (tokensElement) {
        tokensElement.textContent = tokens.toLocaleString();
        tokensElement.style.transition = 'all 0.3s ease-out';
        tokensElement.style.transform = 'scale(1.2)';
        tokensElement.style.color = '#22C55E';
        
        setTimeout(() => {
            tokensElement.style.transform = 'scale(1)';
            tokensElement.style.color = '';
        }, 300);
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

console.log('🎬 Animations.js file loaded completely');// ===== ANIMATIONS.JS - Visual Effects and Trie Animation =====

document.addEventListener('DOMContentLoaded', function() {
    console.log('🎬 Animations.js loaded');
    initializeAnimations();
});

function initializeAnimations() {
    // Visual feedback that JavaScript is working
    const trieAnimation = document.querySelector('.trie-animation');
    if (trieAnimation) {
        trieAnimation.style.borderColor = '#22C55E';
        setTimeout(() => {
            trieAnimation.style.borderColor = '#334155';
        }, 2000);
    }
    
    setupTrieAnimation();
    setupHoverEffects();
    setupCounterAnimations();
    console.log('✅ Animations initialized');
}

// ===== TRIE ANIMATION =====
function setupTrieAnimation() {
    console.log('🎯 Setting up trie animation...');
    const trieAnimation = document.querySelector('.trie-animation');
    console.log('Trie animation element:', trieAnimation);
    
    if (!trieAnimation) {
        console.error('❌ Trie animation element not found!');
        return;
    }
    
    // Initialize stats
    let cacheHits = 0;
    let tokensSaved = 0;
    
    // Start animation after a short delay
    setTimeout(() => {
        console.log('🚀 Starting trie animation...');
        trieAnimation.classList.add('active');
        
        // Run immediately first time
        runTrieAnimationCycle(cacheHits, tokensSaved);
        cacheHits++;
        tokensSaved += 24;
        
        // Then repeat every 4 seconds
        setInterval(() => {
            runTrieAnimationCycle(cacheHits, tokensSaved);
            cacheHits++;
            tokensSaved += 24;
        }, 4000);
        
    }, 1000);
    
    // Add test button functionality
    const testButton = document.getElementById('test-animation');
    if (testButton) {
        testButton.addEventListener('click', function() {
            console.log('🧪 Manual animation test triggered');
            runTrieAnimationCycle(Math.floor(Math.random() * 10), Math.floor(Math.random() * 200));
        });
    }
}

function runTrieAnimationCycle(cacheHits, tokensSaved) {
    console.log('🔄 Running animation cycle...', { cacheHits, tokensSaved });
    
    // Reset all tokens to starting position
    const tokens = document.querySelectorAll('.token');
    console.log('Found tokens:', tokens.length);
    
    tokens.forEach((token, index) => {
        // Reset transform and opacity
        token.style.transform = 'translateX(0px)';
        token.style.opacity = '0';
        
        // Start animation after slight delay for each token
        setTimeout(() => {
            animateToken(token, index);
        }, index * 200);
    });
    
    // Trigger cache hit after tokens have moved
    setTimeout(() => {
        triggerCacheHit();
        updateStats(cacheHits + 1, tokensSaved + 24);
    }, 2000);
}

function animateToken(token, index) {
    console.log(`🎯 Animating token ${index}`);
    
    // Show token
    token.style.opacity = '1';
    token.style.transition = 'all 1.5s ease-in-out';
    
    // Move token across the screen
    setTimeout(() => {
        token.style.transform = 'translateX(220px)';
    }, 100);
    
    // Hide token at the end
    setTimeout(() => {
        token.style.opacity = '0';
    }, 1400);
}

function triggerCacheHit() {
    console.log('💥 Triggering cache hit!');
    
    const hitNode = document.querySelector('.hit-node');
    const hitIndicator = document.querySelector('.hit-indicator');
    const hitLine = document.querySelector('.hit-line');
    
    console.log('Hit elements:', { hitNode, hitIndicator, hitLine });
    
    if (hitNode) {
        // Flash the hit node
        hitNode.style.transition = 'all 0.3s ease-out';
        hitNode.style.transform = 'scale(1.2)';
        hitNode.style.background = 'rgba(34, 197, 94, 0.8)';
        hitNode.style.boxShadow = '0 0 25px rgba(34, 197, 94, 0.9)';
        
        setTimeout(() => {
            hitNode.style.transform = 'scale(1)';
            hitNode.style.background = 'rgba(34, 197, 94, 0.3)';
            hitNode.style.boxShadow = '0 0 15px rgba(34, 197, 94, 0.5)';
        }, 300);
    }
    
    if (hitIndicator) {
        // Show the checkmark
        hitIndicator.style.opacity = '1';
        hitIndicator.style.transform = 'scale(1)';
        
        setTimeout(() => {
            hitIndicator.style.opacity = '0';
            hitIndicator.style.transform = 'scale(0)';
        }, 1500);
    }
    
    if (hitLine) {
        // Pulse the line
        hitLine.style.strokeWidth = '6';
        hitLine.style.filter = 'drop-shadow(0 0 10px rgba(34, 197, 94, 0.8))';
        
        setTimeout(() => {
            hitLine.style.strokeWidth = '3';
            hitLine.style.filter = 'drop-shadow(0 0 6px rgba(34, 197, 94, 0.6))';
        }, 500);
    }
}

function updateStats(hits, tokens) {
    console.log('📊 Updating stats:', { hits, tokens });
    
    const hitsElement = document.getElementById('cache-hits');
    const tokensElement = document.getElementById('tokens-saved');
    
    console.log('Stats elements:', { hitsElement, tokensElement });
    
    if (hitsElement) {
        hitsElement.textContent = hits;
        hitsElement.style.transition = 'all 0.3s ease-out';
        hitsElement.style.transform = 'scale(1.2)';
        hitsElement.style.color = '#22C55E';
        
        setTimeout(() => {
            hitsElement.style.transform = 'scale(1)';
            hitsElement.style.color = '';
        }, 300);
    }
    
    if (tokensElement) {
        tokensElement.textContent = tokens.toLocaleString();
        tokensElement.style.transition = 'all 0.3s ease-out';
        tokensElement.style.transform = 'scale(1.2)';
        tokensElement.style.color = '#22C55E';
        
        setTimeout(() => {
            tokensElement.style.transform = 'scale(1)';
            tokensElement.style.color = '';
        }, 300);
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
    const defaults = {
        particleCount: 20,
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
                const animationType = entry.target.dataset.animation;
                
                switch(animationType) {
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