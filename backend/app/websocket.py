"""WebSocket handlers for real-time search"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
from .models import SearchRequest, SearchComplete, SearchError
from .services.ripgrep import RipgrepService
import time


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.search_tasks: Dict[WebSocket, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.discard(websocket)
        # Cancel any ongoing search task
        if websocket in self.search_tasks:
            task = self.search_tasks[websocket]
            if not task.done():
                task.cancel()
            del self.search_tasks[websocket]

    async def send_message(self, websocket: WebSocket, message: dict):
        """Send a message to a specific connection"""
        try:
            await websocket.send_json(message)
        except Exception:
            # Connection might be closed
            self.disconnect(websocket)

    async def handle_search(self, websocket: WebSocket, request: SearchRequest):
        """Handle a search request via WebSocket"""
        start_time = time.time()
        total_matches = 0
        files_scanned = 0

        try:
            # Execute search and stream results
            async for update in RipgrepService.execute_search(request):
                # Send update to client
                await self.send_message(websocket, update.model_dump())

                # Track stats
                if update.type == "progress":
                    files_scanned = update.files_scanned
                elif update.type == "result":
                    total_matches += 1

            # Send completion message
            duration = time.time() - start_time
            completion = SearchComplete(
                total_matches=total_matches,
                files_scanned=files_scanned,
                duration_seconds=duration,
            )
            await self.send_message(websocket, completion.model_dump())

        except asyncio.CancelledError:
            # Search was cancelled
            error = SearchError(message="Search cancelled by user")
            await self.send_message(websocket, error.model_dump())
            raise

        except Exception as e:
            # Send error to client
            error = SearchError(message=f"Search failed: {str(e)}")
            await self.send_message(websocket, error.model_dump())


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for search operations"""
    await manager.connect(websocket)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            action = data.get("action")

            if action == "search":
                # Parse search request
                try:
                    request = SearchRequest(**data.get("data", {}))

                    # Start search in background task
                    task = asyncio.create_task(manager.handle_search(websocket, request))
                    manager.search_tasks[websocket] = task

                    # Wait for task to complete
                    await task

                except ValueError as e:
                    # Invalid request
                    error = SearchError(message=f"Invalid request: {str(e)}")
                    await manager.send_message(websocket, error.model_dump())

            elif action == "cancel":
                # Cancel ongoing search
                if websocket in manager.search_tasks:
                    task = manager.search_tasks[websocket]
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

            elif action == "ping":
                # Heartbeat
                await manager.send_message(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
