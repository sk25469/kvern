"""
HTTP client for backend forwarding.

This module handles communication with the actual LLM backend (vLLM, Ollama, etc.)
including request forwarding, response streaming, and error handling.
"""

import httpx
import asyncio
from typing import Dict, Any, AsyncIterator
from fastapi import HTTPException
import json


class BackendClient:
    """
    Async HTTP client for forwarding requests to LLM backends.
    
    Features:
    - Request forwarding with proper headers
    - Streaming response support
    - Error handling and retries
    - Connection pooling
    """
    
    def __init__(self, base_url: str, timeout: float = 120.0):
        """
        Initialize backend client.
        
        Args:
            base_url: Backend endpoint URL (e.g., http://localhost:11434)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self.client = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_connections=20)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()
    
    async def forward_chat_completion(
        self,
        body: Dict[str, Any],
        headers: Dict[str, str] = None
    ) -> httpx.Response:
        """
        Forward chat completion request to backend.
        
        Args:
            body: Request body (messages, model, etc.)
            headers: Additional headers to forward
            
        Returns:
            Backend response
            
        Raises:
            HTTPException: On backend errors
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use as context manager.")
            
        # Prepare headers
        forward_headers = {"Content-Type": "application/json"}
        if headers:
            # Forward relevant headers, exclude hop-by-hop headers
            for key, value in headers.items():
                if key.lower() not in ["host", "connection", "content-length"]:
                    forward_headers[key] = value
        
        try:
            response = await self.client.post(
                "/v1/chat/completions",
                json=body,
                headers=forward_headers
            )
            
            # Check for backend errors
            if response.status_code >= 400:
                try:
                    error_detail = response.json().get("error", "Unknown backend error")
                except:
                    error_detail = response.text[:200] if response.text else "Empty response"
                    
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Backend error: {error_detail}"
                )
            
            return response
            
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Backend timeout"
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=502,
                detail=f"Cannot connect to backend at {self.base_url}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502, 
                detail=f"Backend request error: {str(e)}"
            )
    
    async def forward_streaming(
        self,
        body: Dict[str, Any],
        headers: Dict[str, str] = None
    ) -> AsyncIterator[bytes]:
        """
        Forward streaming chat completion request.
        
        Args:
            body: Request body with stream=True
            headers: Additional headers to forward
            
        Yields:
            Streaming chunks from backend
            
        Raises:
            HTTPException: On backend errors
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use as context manager.")
            
        # Ensure streaming is enabled
        body = dict(body)
        body["stream"] = True
        
        # Prepare headers
        forward_headers = {"Content-Type": "application/json"}
        if headers:
            for key, value in headers.items():
                if key.lower() not in ["host", "connection", "content-length"]:
                    forward_headers[key] = value
        
        try:
            async with self.client.stream(
                "POST",
                "/v1/chat/completions",
                json=body,
                headers=forward_headers
            ) as response:
                
                # Check for immediate errors
                if response.status_code >= 400:
                    error_data = await response.aread()
                    try:
                        error_detail = json.loads(error_data).get("error", "Unknown error")
                    except:
                        error_detail = error_data.decode()[:200] if error_data else "Empty response"
                        
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Backend streaming error: {error_detail}"
                    )
                
                # Stream response chunks
                async for chunk in response.aiter_bytes():
                    yield chunk
                    
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Backend streaming timeout"
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=502,
                detail=f"Cannot connect to backend at {self.base_url}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Backend streaming error: {str(e)}"
            )
    
    async def health_check(self) -> bool:
        """
        Check if backend is healthy.
        
        Returns:
            True if backend is responsive, False otherwise
        """
        if not self.client:
            return False
            
        try:
            response = await self.client.get("/health", timeout=5.0)
            return response.status_code == 200
        except:
            return False


# Singleton backend client factory
_backend_clients: Dict[str, BackendClient] = {}

def get_backend_client(base_url: str, timeout: float = 120.0) -> BackendClient:
    """
    Get or create backend client for the given URL.
    
    Args:
        base_url: Backend endpoint URL
        timeout: Request timeout in seconds
        
    Returns:
        BackendClient instance
    """
    key = f"{base_url}:{timeout}"
    if key not in _backend_clients:
        _backend_clients[key] = BackendClient(base_url, timeout)
    return _backend_clients[key]


async def cleanup_backend_clients():
    """Cleanup all backend client connections."""
    for client in _backend_clients.values():
        if client.client:
            await client.client.aclose()
    _backend_clients.clear()