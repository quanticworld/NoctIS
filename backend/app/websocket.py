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
        self.cancel_events: Dict[WebSocket, asyncio.Event] = {}
        self.process_pids: Dict[WebSocket, int] = {}

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
        # Clean up cancel event and PID
        if websocket in self.cancel_events:
            del self.cancel_events[websocket]
        if websocket in self.process_pids:
            del self.process_pids[websocket]

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

        # Create cancel event for this search
        cancel_event = asyncio.Event()
        self.cancel_events[websocket] = cancel_event

        try:
            # Execute search and stream results
            async for update in RipgrepService.execute_search(request, cancel_event, websocket, self):
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
                # Cancel ongoing search - KILL THE PROCESS IMMEDIATELY
                print(f"[CANCEL] Received cancel request")

                # Kill the ripgrep process directly
                if websocket in manager.process_pids:
                    pid = manager.process_pids[websocket]
                    print(f"[CANCEL] Killing ripgrep process {pid}")
                    import signal
                    import os
                    try:
                        os.kill(pid, signal.SIGKILL)
                        print(f"[CANCEL] Sent SIGKILL to process {pid}")
                    except ProcessLookupError:
                        print(f"[CANCEL] Process {pid} already dead")
                    except Exception as e:
                        print(f"[CANCEL] Error killing process {pid}: {e}")

                # Signal cancel event
                if websocket in manager.cancel_events:
                    print(f"[CANCEL] Setting cancel event")
                    manager.cancel_events[websocket].set()

                # Cancel the task
                task_was_cancelled = False
                if websocket in manager.search_tasks:
                    task = manager.search_tasks[websocket]
                    print(f"[CANCEL] Task found, done={task.done()}")
                    if not task.done():
                        print(f"[CANCEL] Calling task.cancel()")
                        task.cancel()
                        task_was_cancelled = True
                        try:
                            await task
                            print(f"[CANCEL] Task awaited successfully")
                        except asyncio.CancelledError:
                            print(f"[CANCEL] CancelledError caught")
                            pass
                    else:
                        print(f"[CANCEL] Task already done, sending cancel confirmation anyway")
                        task_was_cancelled = True
                else:
                    print(f"[CANCEL] No task found for this websocket")

                # Always send a cancel confirmation to the client
                if task_was_cancelled or websocket not in manager.search_tasks:
                    from .models import SearchError
                    error = SearchError(message="Search cancelled")
                    await manager.send_message(websocket, error.model_dump())
                    print(f"[CANCEL] Sent cancel confirmation to client")

            elif action == "deduplication":
                # Run deduplication with progress updates
                try:
                    from app.services.mdm_service import mdm_service

                    params = data.get("data", {})
                    batch_size = params.get("batch_size", 250)
                    max_batches = params.get("max_batches")

                    # Progress callback to send updates via WebSocket
                    async def send_progress(progress_data):
                        await manager.send_message(websocket, progress_data)

                    # Run deduplication with progress callback
                    stats = await mdm_service.process_silver_deduplication(
                        batch_size=batch_size,
                        max_batches=max_batches,
                        progress_callback=send_progress
                    )

                    # Send completion message
                    await manager.send_message(websocket, {
                        'type': 'complete',
                        'processed': stats['processed'],
                        'new_masters': stats['new_masters'],
                        'merged': stats['merged'],
                        'errors': stats['errors'],
                        'has_more': stats['has_more']
                    })

                except Exception as e:
                    from .models import SearchError
                    error = SearchError(message=f"Deduplication failed: {str(e)}")
                    await manager.send_message(websocket, error.model_dump())

            elif action == "ping":
                # Heartbeat
                await manager.send_message(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
