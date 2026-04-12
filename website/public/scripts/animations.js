// ===== ANIMATIONS.JS - Enhanced Realistic Version =====

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
    
    // Schedule next animation with varying intervals (3-7 seconds)
    const nextInterval = 3000 + Math.random() * 4000;
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
        token.style.transform = 'translateX(0px) translateY(0px)';
        token.style.opacity = '0';
        token.style.background = '#22C55E'; // Reset to green
        token.style.boxShadow = '0 0 12px rgba(34, 197, 94, 0.8)';
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
    token.style.transition = 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
    
    // Move to root first
    setTimeout(() => {
        token.style.transform = 'translateX(225px) translateY(-80px)';
    }, 100);
    
    // Move to second level  
    setTimeout(() => {
        if (path[1] === 'system') {
            token.style.transform = 'translateX(43px) translateY(-20px)';
        } else {
            token.style.transform = 'translateX(407px) translateY(-20px)';
        }
    }, 400);
    
    // Move to final destination
    setTimeout(() => {
        if (path[2] === 'hit') {
            token.style.transform = 'translateX(30px) translateY(60px)';
            // Trigger hit animation
            setTimeout(() => triggerNodeHit(path[2]), 200);
        } else {
            token.style.transform = 'translateX(225px) translateY(60px)';
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

function updateRealisticStats(hits, misses, total, scenario) {
    console.log('📊 Updating realistic stats:', { hits, misses, total, scenario: scenario.description });
    
    const hitsElement = document.getElementById('cache-hits');
    const tokensElement = document.getElementById('tokens-saved');
    
    // Calculate hit rate and tokens saved
    const hitRate = total > 0 ? Math.round((hits / total) * 100) : 0;
    const avgTokensSaved = hits * 24; // Assume 24 tokens saved per hit
    
    if (hitsElement) {
        // Show hit rate instead of just hits
        hitsElement.textContent = `${hitRate}%`;
        hitsElement.style.transition = 'all 0.3s ease-out';
        
        if (scenario.isHit) {
            hitsElement.style.transform = 'scale(1.3)';
            hitsElement.style.color = '#22C55E';
        } else {
            hitsElement.style.transform = 'scale(1.1)';  
            hitsElement.style.color = '#f59e0b';
        }
        
        setTimeout(() => {
            hitsElement.style.transform = 'scale(1)';
            hitsElement.style.color = '#22C55E';
        }, 400);
    }
    
    if (tokensElement) {
        tokensElement.textContent = avgTokensSaved.toLocaleString();
        tokensElement.style.transition = 'all 0.3s ease-out';
        
        if (scenario.isHit) {
            tokensElement.style.transform = 'scale(1.3)';
            tokensElement.style.color = '#22C55E';
        } else {
            // No tokens saved on miss
            tokensElement.style.transform = 'scale(0.9)';
            tokensElement.style.color = '#64748B';
        }
        
        setTimeout(() => {
            tokensElement.style.transform = 'scale(1)';
            tokensElement.style.color = '#22C55E';
        }, 400);
    }
    
    // Update scenario description
    const animationContainer = document.querySelector('.animation-container');
    let statusElement = document.getElementById('scenario-status');
    
    if (!statusElement && animationContainer) {
        statusElement = document.createElement('div');
        statusElement.id = 'scenario-status';
        statusElement.style.cssText = `
            position: absolute;
            top: 35px;
            left: 10px;
            right: 10px;
            text-align: center;
            font-size: 12px;
            color: #94A3B8;
            background: rgba(0, 0, 0, 0.5);
            padding: 4px 8px;
            border-radius: 6px;
            z-index: 5;
        `;
        animationContainer.appendChild(statusElement);
    }
    
    if (statusElement) {
        statusElement.textContent = scenario.description;
        statusElement.style.color = scenario.isHit ? '#22C55E' : '#f59e0b';
        
        setTimeout(() => {
            statusElement.style.color = '#94A3B8';
        }, 2000);
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

console.log('🎬 Animations.js file loaded completely');