// ===== MAIN.JS - Core Functionality =====

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Main.js loaded and DOM ready');
    initializeApp();
});

function initializeApp() {
    console.log('🔧 Initializing app...');
    setupNavigation();
    setupClipboard();
    setupDemo();
    setupArchitecture();
    setupScrollReveal();
    setupFeatureCards();
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
                showCopyError(cloneBtn);
            }
        });
    }
}

function showCopySuccess(button) {
    const originalHTML = button.innerHTML;
    button.innerHTML = '<span class=\"mono-text\">✓ Copied to clipboard!</span>';
    button.classList.add('copied');
    
    setTimeout(() => {
        button.innerHTML = originalHTML;
        button.classList.remove('copied');
    }, 2000);
}

function showCopyError(button) {
    const originalHTML = button.innerHTML;
    button.innerHTML = '<span class=\"mono-text\">❌ Copy failed</span>';
    
    setTimeout(() => {
        button.innerHTML = originalHTML;
    }, 2000);
}

function fallbackCopy(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        document.body.removeChild(textArea);
    } catch (error) {
        document.body.removeChild(textArea);
        throw error;
    }
}

// ===== HOW IT WORKS DEMO FUNCTIONALITY =====
function setupDemo() {
    const demoBtns = document.querySelectorAll('.demo-btn');
    const demoSteps = document.querySelectorAll('.demo-step');

    if (!demoBtns.length || !demoSteps.length) {
        console.log('Demo elements not found, skipping demo setup');
        return;
    }

    // Demo scenarios
    const demoScenarios = {
        basic: {
            steps: [
                {
                    title: "Request Analysis",
                    description: "KVern tokenizes a simple prompt: 'Explain machine learning'"
                },
                {
                    title: "Cache Lookup",
                    description: "Searches trie for common ML explanation prefixes"
                },
                {
                    title: "Smart Response",
                    description: "Returns cached introduction, processes unique parts only"
                }
            ]
        },
        complex: {
            steps: [
                {
                    title: "Request Analysis",
                    description: "Complex prompt with system context + multi-step reasoning chain"
                },
                {
                    title: "Cache Lookup",
                    description: "Finds 80% prefix match in system prompt, 45% in reasoning pattern"
                },
                {
                    title: "Smart Response",
                    description: "Reconstructs from cached segments, saving 1,247 tokens"
                }
            ]
        },
        repeated: {
            steps: [
                {
                    title: "Request Analysis",
                    description: "Detects repeated prompt pattern from previous requests"
                },
                {
                    title: "Cache Lookup",
                    description: "95% match found - only the final question differs"
                },
                {
                    title: "Smart Response",
                    description: "Near-instant response with 2,100 tokens cached"
                }
            ]
        }
    };

    function animateDemoSteps(scenario) {
        console.log('🎬 Starting demo animation for scenario with', scenario.steps.length, 'steps');
        
        // Reset all steps
        demoSteps.forEach(step => {
            step.classList.remove('active');
        });

        // Update content without restarting animation
        demoSteps.forEach((step, index) => {
            const stepContent = step.querySelector('.step-content');
            if (stepContent && scenario.steps[index]) {
                const title = stepContent.querySelector('h4');
                const description = stepContent.querySelector('p');
                
                if (title) title.textContent = scenario.steps[index].title;
                if (description) description.textContent = scenario.steps[index].description;
            }
        });

        // Animate steps sequentially
        demoSteps.forEach((step, index) => {
            setTimeout(() => {
                console.log(`🎯 Activating step ${index + 1}:`, scenario.steps[index]?.title);
                step.classList.add('active');
            }, index * 800);
        });
    }

    function updateDemoContent(scenario) {
        console.log('📝 Updating demo content for scenario with', scenario.steps.length, 'steps');
        
        // Update content without resetting animation
        demoSteps.forEach((step, index) => {
            const stepContent = step.querySelector('.step-content');
            if (stepContent && scenario.steps[index]) {
                const title = stepContent.querySelector('h4');
                const description = stepContent.querySelector('p');
                
                if (title) title.textContent = scenario.steps[index].title;
                if (description) description.textContent = scenario.steps[index].description;
            }
        });
    }

    // Button click handlers
    demoBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            console.log('🖱️ Demo button clicked:', btn.getAttribute('data-demo'));
            
            // Stop auto-rotation when user manually clicks
            clearInterval(autoRotateInterval);
            
            // Remove active from all buttons
            demoBtns.forEach(b => b.classList.remove('active'));
            // Add active to clicked button
            btn.classList.add('active');
            
            // Get scenario type
            const scenarioType = btn.getAttribute('data-demo');
            const scenario = demoScenarios[scenarioType];
            
            console.log('📋 Selected scenario:', scenarioType, scenario ? 'found' : 'NOT FOUND');
            
            if (scenario) {
                // Only update content, don't restart animation
                updateDemoContent(scenario);
            } else {
                console.error('❌ Scenario not found:', scenarioType);
            }
        });
    });

    // Function to set active demo button (for auto-rotation)
    function setActiveDemo(demoType) {
        console.log('🎯 Setting active demo to:', demoType);
        
        // Remove active from all buttons
        demoBtns.forEach(b => b.classList.remove('active'));
        
        // Find and activate the correct button
        const targetBtn = document.querySelector(`[data-demo="${demoType}"]`);
        if (targetBtn) {
            targetBtn.classList.add('active');
            console.log('✅ Button activated:', demoType);
        } else {
            console.error('❌ Button not found for demo:', demoType);
        }
        
        // Only update content, don't restart step animation
        const scenario = demoScenarios[demoType];
        if (scenario) {
            updateDemoContent(scenario);
        }
    }

    // Initialize with basic demo and start step animation
    setTimeout(() => {
        console.log('🎯 Initializing demo system...');
        setActiveDemo('basic');
        // Start the step animation once
        const basicScenario = demoScenarios['basic'];
        if (basicScenario) {
            animateDemoSteps(basicScenario);
        }
    }, 1500);

    // Auto-rotate through demos every 4 seconds (only change content, not animation)
    let currentDemoIndex = 0;
    const demoTypes = ['basic', 'complex', 'repeated'];
    
    const autoRotateInterval = setInterval(() => {
        currentDemoIndex = (currentDemoIndex + 1) % demoTypes.length;
        const nextDemo = demoTypes[currentDemoIndex];
        console.log('🔄 Auto-rotating to demo:', nextDemo);
        setActiveDemo(nextDemo);
    }, 4000);

    console.log('🎯 Demo system initialized with', demoBtns.length, 'buttons and', demoSteps.length, 'steps');
}

// ===== ARCHITECTURE DIAGRAM FUNCTIONALITY =====
function setupArchitecture() {
    const archSteps = [
        {
            title: "Step 1 — Client sends a request",
            desc: "A client sends a POST /v1/chat/completions to KVern's proxy — identical to how you'd talk to OpenAI directly. No API changes. KVern is a transparent drop-in.",
            highlights: ["hl-client", "hl-proxy"],
            activeLines: ["conn-cp"]
        },
        {
            title: "Step 2 — Proxy extracts and tokenizes the prompt",
            desc: "The proxy pulls the model name and the messages[] array. It passes these to the Tokenizer, which applies the model's chat template (Jinja2) to serialize the conversation into a flat token ID sequence.",
            highlights: ["hl-proxy", "hl-tokenizer"],
            activeLines: ["conn-pt"]
        },
        {
            title: "Step 3 — Prefix Trie lookup and insert",
            desc: "The token IDs walk the trie from the root. KVern finds the longest prefix this request shares with any prior request. A 2000-token system prompt seen 500 times before? That's a deep trie hit.",
            highlights: ["hl-trie"],
            activeLines: ["conn-tt"]
        },
        {
            title: "Step 4 — Analytics recorded (off the critical path)",
            desc: "Hit/miss, shared prefix depth, model, timestamp — all written to SQLite asynchronously. This happens concurrently with the backend forward, adding zero latency.",
            highlights: ["hl-analytics"],
            activeLines: ["conn-ta"]
        },
        {
            title: "Step 5 — Request forwarded to backend",
            desc: "The original request is forwarded unchanged to vLLM or Ollama. KVern never modifies it. If KVern crashes, the request still reaches the backend — it fails open.",
            highlights: ["hl-backend"],
            activeLines: ["conn-pb"]
        },
        {
            title: "Step 6 — Response streamed back to client",
            desc: "The backend response (streaming or complete) passes through the proxy back to the client, unmodified. Post-response, backend latency is recorded to analytics.",
            highlights: ["hl-client", "hl-proxy"],
            activeLines: ["conn-bp", "conn-pcc"]
        },
        {
            title: "Step 7 — Eviction engine runs in background",
            desc: "Periodically, the eviction engine scores every trie node using the configured policy (LRU, LFU-decay, or cost-aware). It produces an ordered eviction list for cache management.",
            highlights: ["hl-eviction", "hl-trie", "hl-analytics"],
            activeLines: ["conn-te2"]
        }
    ];

    let currentArchStep = 0;
    
    // Get elements
    const stepTitle = document.getElementById('arch-step-title');
    const stepDesc = document.getElementById('arch-step-desc');
    const prevBtn = document.getElementById('arch-prev');
    const nextBtn = document.getElementById('arch-next');
    const stepDots = document.querySelectorAll('.step-dot');

    if (!stepTitle || !stepDesc || !prevBtn || !nextBtn) {
        console.log('Architecture elements not found, skipping setup');
        return;
    }

    const allHighlights = ["hl-client", "hl-proxy", "hl-tokenizer", "hl-trie", "hl-analytics", "hl-backend", "hl-eviction"];
    const allLines = ["conn-cp", "conn-pt", "conn-tt", "conn-ta", "conn-pb", "conn-bp", "conn-pcc", "conn-te2"];

    function renderArchStep(stepIndex) {
        const step = archSteps[stepIndex];
        
        // Update content
        stepTitle.textContent = step.title;
        stepDesc.textContent = step.desc;

        // Reset all highlights
        allHighlights.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.setAttribute('opacity', '0');
            
            const node = document.getElementById(id.replace('hl-', 'node-'));
            if (node) node.classList.remove('active');
        });

        // Reset all lines
        allLines.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.remove('active');
        });

        // Activate current highlights
        step.highlights.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.setAttribute('opacity', '1');
            
            const node = document.getElementById(id.replace('hl-', 'node-'));
            if (node) node.classList.add('active');
        });

        // Activate current lines
        step.activeLines.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('active');
        });

        // Update step dots
        stepDots.forEach((dot, index) => {
            dot.classList.remove('active', 'completed');
            if (index === stepIndex) {
                dot.classList.add('active');
            } else if (index < stepIndex) {
                dot.classList.add('completed');
            }
        });

        // Update button states
        prevBtn.disabled = stepIndex === 0;
        nextBtn.textContent = stepIndex === archSteps.length - 1 ? 'Restart ↺' : 'Next →';
    }

    function changeArchStep(direction) {
        currentArchStep = (currentArchStep + direction + archSteps.length) % archSteps.length;
        renderArchStep(currentArchStep);
        console.log('🏗️ Architecture step:', currentArchStep + 1);
    }

    // Event listeners
    prevBtn.addEventListener('click', () => changeArchStep(-1));
    nextBtn.addEventListener('click', () => changeArchStep(1));

    // Step dot clicks
    stepDots.forEach((dot, index) => {
        dot.addEventListener('click', () => {
            currentArchStep = index;
            renderArchStep(currentArchStep);
        });
    });

    // Auto-advance every 6 seconds
    setInterval(() => {
        changeArchStep(1);
    }, 6000);

    // Initialize
    renderArchStep(0);
    console.log('🏗️ Architecture diagram initialized with', archSteps.length, 'steps');
}

// ===== FEATURE CARD ENHANCEMENTS =====
function setupFeatureCards() {
    const featureCards = document.querySelectorAll('.feature-card');
    
    featureCards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-12px)';
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
        });
    });
    
    console.log('🃏 Feature cards enhanced');
}

// ===== SCROLL REVEAL EFFECTS =====
function setupScrollReveal() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('reveal');
            }
        });
    }, observerOptions);

    // Observe sections
    const sections = document.querySelectorAll('section');
    sections.forEach(section => {
        section.classList.add('reveal-pending');
        observer.observe(section);
    });

    console.log('👀 Scroll reveal setup complete');
}

// ===== NAVIGATION =====
function setupNavigation() {
    // Smooth scrolling for navigation links
    const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);
            
            if (targetElement) {
                const navHeight = 70; // Navigation bar height
                const targetPosition = targetElement.offsetTop - navHeight;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
                
                console.log('🧭 Navigating to:', targetId);
            }
        });
    });
    
    // Navigation background on scroll
    const nav = document.querySelector('.main-nav');
    if (nav) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                nav.style.background = 'rgba(10, 10, 11, 0.98)';
            } else {
                nav.style.background = 'rgba(10, 10, 11, 0.95)';
            }
        });
    }
    
    // Mobile navigation toggle (for future)
    const navToggle = document.querySelector('.nav-toggle');
    const navLinksContainer = document.querySelector('.nav-links');
    
    if (navToggle && navLinksContainer) {
        navToggle.addEventListener('click', () => {
            navLinksContainer.classList.toggle('active');
        });
    }
    
    console.log('🧭 Navigation setup complete');
}

// ===== DEBUGGING & UTILITIES =====
function checkElementsLoaded() {
    const elements = {
        'Clone Button': document.getElementById('clone-btn'),
        'Demo Buttons': document.querySelectorAll('.demo-btn'),
        'Demo Steps': document.querySelectorAll('.demo-step'),
        'Feature Cards': document.querySelectorAll('.feature-card')
    };
    
    console.log('🔍 Element check:');
    Object.entries(elements).forEach(([name, element]) => {
        const exists = element && (element.length > 0 || element.nodeType);
        console.log(`  ${exists ? '✅' : '❌'} ${name}: ${exists ? 'Found' : 'Missing'}`);
    });
}

// Call debug function after DOM loads
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(checkElementsLoaded, 100);
});

console.log('📄 Main.js file loaded');