#!/usr/bin/env python3
"""
KVern Proxy Server Launcher

Run this from the project root directory to start the proxy server.
"""

import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run the main app
if __name__ == "__main__":
    from src.proxy.main import app
    import uvicorn
    import yaml
    
    # Load config for host/port
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    uvicorn.run(
        "src.proxy.main:app",
        host=config["proxy"]["host"],
        port=config["proxy"]["port"],
        reload=True
    )