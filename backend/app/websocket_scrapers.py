"""WebSocket endpoint for real-time scraper execution logs"""
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import logging
from typing import Dict, Set
import json

from .services.scraper_db import scraper_db
from .services.scraper_executor import scraper_executor

logger = logging.getLogger(__name__)


class ScraperConnectionManager:
    """Manage WebSocket connections for scraper logs"""

    def __init__(self):
        # execution_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, execution_id: str):
        """Connect to scraper execution logs"""
        await websocket.accept()

        if execution_id not in self.active_connections:
            self.active_connections[execution_id] = set()

        self.active_connections[execution_id].add(websocket)
        logger.info(f"Client connected to execution {execution_id}")

    def disconnect(self, websocket: WebSocket, execution_id: str):
        """Disconnect from scraper execution logs"""
        if execution_id in self.active_connections:
            self.active_connections[execution_id].discard(websocket)

            # Clean up if no more connections
            if not self.active_connections[execution_id]:
                del self.active_connections[execution_id]

        logger.info(f"Client disconnected from execution {execution_id}")

    async def broadcast(self, execution_id: str, message: dict):
        """Broadcast message to all clients watching this execution"""
        if execution_id not in self.active_connections:
            return

        disconnected = set()

        for websocket in self.active_connections[execution_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to websocket: {e}")
                disconnected.add(websocket)

        # Clean up disconnected
        for websocket in disconnected:
            self.disconnect(websocket, execution_id)


# Singleton
scraper_manager = ScraperConnectionManager()


async def websocket_scraper_logs(websocket: WebSocket, execution_id: str):
    """
    WebSocket endpoint for streaming scraper execution logs

    Client receives JSON messages:
    {
        "type": "status",
        "status": "running" | "completed" | "failed",
        "started_at": 1234567890,
        "finished_at": 1234567890
    }
    {
        "type": "stdout",
        "data": "..."
    }
    {
        "type": "stderr",
        "data": "..."
    }
    {
        "type": "finding",
        "finding": {...}
    }
    {
        "type": "complete",
        "execution": {...}
    }
    """
    await scraper_manager.connect(websocket, execution_id)

    try:
        # Send initial execution status
        execution = scraper_db.get_execution(execution_id)
        if not execution:
            await websocket.send_json({
                "type": "error",
                "message": "Execution not found"
            })
            await websocket.close()
            return

        await websocket.send_json({
            "type": "status",
            "status": execution['status'],
            "started_at": execution['started_at'],
            "finished_at": execution.get('finished_at')
        })

        # If execution already finished, send final data and close
        if execution['status'] in ['completed', 'failed']:
            # Send stdout/stderr
            if execution.get('stdout'):
                await websocket.send_json({
                    "type": "stdout",
                    "data": execution['stdout']
                })

            if execution.get('stderr'):
                await websocket.send_json({
                    "type": "stderr",
                    "data": execution['stderr']
                })

            # Send findings
            findings = scraper_db.list_findings(
                scraper_id=execution['scraper_id'],
                execution_id=execution_id,
                limit=1000
            )

            for finding in findings:
                await websocket.send_json({
                    "type": "finding",
                    "finding": finding
                })

            # Send complete message
            await websocket.send_json({
                "type": "complete",
                "execution": execution
            })

            await websocket.close()
            return

        # Poll for updates while execution is running
        while True:
            await asyncio.sleep(1)  # Poll every second

            execution = scraper_db.get_execution(execution_id)
            if not execution:
                break

            # Send status update
            await websocket.send_json({
                "type": "status",
                "status": execution['status'],
                "started_at": execution['started_at'],
                "finished_at": execution.get('finished_at')
            })

            # Check if finished
            if execution['status'] in ['completed', 'failed']:
                # Send final output
                if execution.get('stdout'):
                    await websocket.send_json({
                        "type": "stdout",
                        "data": execution['stdout']
                    })

                if execution.get('stderr'):
                    await websocket.send_json({
                        "type": "stderr",
                        "data": execution['stderr']
                    })

                # Send findings
                findings = scraper_db.list_findings(
                    scraper_id=execution['scraper_id'],
                    execution_id=execution_id,
                    limit=1000
                )

                for finding in findings:
                    await websocket.send_json({
                        "type": "finding",
                        "finding": finding
                    })

                # Send complete message
                await websocket.send_json({
                    "type": "complete",
                    "execution": execution
                })

                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for execution {execution_id}")
    except Exception as e:
        logger.error(f"WebSocket error for execution {execution_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        scraper_manager.disconnect(websocket, execution_id)
