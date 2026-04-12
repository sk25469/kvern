# KVern Website

Professional website for the KVern LLM KV Cache Manager project.

## Quick Start

### Option 1: Direct File Access
Open `public/index.html` directly in your browser:
```bash
open public/index.html  # macOS
xdg-open public/index.html  # Linux
```

### Option 2: Local Development Server
```bash
cd public/
python3 -m http.server 8080
# Then visit: http://localhost:8080
```

## Theme & Design

**"Cyber-Infrastructure" Dark-First Theme:**
- Primary Background: Deep Charcoal (#0A0A0B)
- Accent Colors: Hyper-Green (#22C55E) & Electric Violet (#A855F7)
- Typography: Inter (headings) + JetBrains Mono (code)
- Visual Style: Glassmorphism with subtle gradients

## Current Status

✅ **Hero Section Complete**
- Professional headline with gradient accent text
- Value proposition copy
- Interactive git clone button with clipboard functionality  
- Animated trie visualization
- Responsive design (mobile + desktop)

## Next Sections (Planned)
- Problem Statement ("Computational Waste")
- How It Works (Feature cards)
- Architecture Diagram (Interactive)
- Metrics Dashboard Preview
- Technical Deep-Dive

## Development

**Files Structure:**
```
public/
├── index.html          # Main page
├── styles/
│   ├── main.css        # Base styles & layout
│   ├── components.css  # Component-specific styles
│   └── animations.css  # Animation definitions
└── scripts/
    ├── main.js         # Core functionality
    └── animations.js   # Visual effects
```

**Key Features:**
- Static HTML/CSS/JS (no build process required)
- Progressive enhancement with vanilla JavaScript
- Optimized for performance and accessibility
- Intersection Observer for scroll animations
- Clipboard API integration

## Browser Support
- Modern browsers (Chrome 80+, Firefox 75+, Safari 13+)
- Progressive degradation for older browsers
- Respects `prefers-reduced-motion` accessibility setting