"""
Middleware for request interception and request_id assignment.

This module provides FastAPI middleware for request tracking and observability.
"""

import time
import uuid
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from typing import Callable


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track requests and add observability headers.
    
    Features:
    - Assigns unique request_id to each request
    - Measures request processing time
    - Adds observability headers to responses
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add tracking information."""
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Record start time
        start_time = time.perf_counter()
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.perf_counter() - start_time
        
        # Add observability headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-KVern-Version"] = "0.1.0"
        
        return response


class CORSMiddleware(BaseHTTPMiddleware):
    """
    Simple CORS middleware for development.
    
    Note: In production, use fastapi.middleware.cors.CORSMiddleware instead.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add CORS headers to responses."""
        
        response = await call_next(request)
        
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Request logging middleware for debugging.
    
    Logs basic request information including method, path, and response status.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request information."""
        
        start_time = time.perf_counter()
        
        # Extract request info
        method = request.method
        url = str(request.url)
        client_ip = request.client.host if request.client else "unknown"
        
        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            
            # Log successful request
            print(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"{client_ip} - {method} {url} - "
                f"{response.status_code} - {process_time:.3f}s"
            )
            
            return response
            
        except Exception as e:
            process_time = time.perf_counter() - start_time
            
            # Log failed request
            print(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"{client_ip} - {method} {url} - "
                f"ERROR: {str(e)} - {process_time:.3f}s"
            )
            
            raise