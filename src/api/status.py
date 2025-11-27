"""Status checking endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
import json
from datetime import datetime

from src.database.session import get_db
from src.models.request import CreativityRequest, ProcessingStatus
from src.api.schemas import ProcessingStatusResponse, CreativityRequestResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/status/{request_id}", response_model=ProcessingStatusResponse)
async def get_status(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed processing status for a request.

    Args:
        request_id: Request ID
        db: Database session

    Returns:
        Detailed processing status
    """
    # Get request
    result = await db.execute(
        select(CreativityRequest).where(CreativityRequest.id == request_id)
    )
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Get processing status
    status_result = await db.execute(
        select(ProcessingStatus).where(ProcessingStatus.request_id == request_id)
    )
    status = status_result.scalar_one_or_none()

    if not status:
        # Return basic status if detailed status not yet created
        return ProcessingStatusResponse(
            request_id=request_id,
            status=request.status.value,
            progress_percentage=request.progress_percentage,
            current_stage=request.current_stage,
            preparation_status=None,
            moment_agents_status=None,
            critique_agents_status=None,
            synthesis_status=None,
            memories_activated=None,
            updated_at=request.updated_at,
        )

    return ProcessingStatusResponse(
        request_id=request_id,
        status=request.status.value,
        progress_percentage=request.progress_percentage,
        current_stage=request.current_stage,
        preparation_status=status.preparation_status,
        moment_agents_status=status.moment_agents_status,
        critique_agents_status=status.critique_agents_status,
        synthesis_status=status.synthesis_status,
        memories_activated=status.memories_activated,
        updated_at=status.updated_at,
    )


# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[UUID, list[WebSocket]] = {}

    async def connect(self, request_id: UUID, websocket: WebSocket):
        """Connect a WebSocket for a request."""
        await websocket.accept()
        if request_id not in self.active_connections:
            self.active_connections[request_id] = []
        self.active_connections[request_id].append(websocket)
        logger.info("WebSocket connected", request_id=str(request_id))

    def disconnect(self, request_id: UUID, websocket: WebSocket):
        """Disconnect a WebSocket."""
        if request_id in self.active_connections:
            self.active_connections[request_id].remove(websocket)
            if not self.active_connections[request_id]:
                del self.active_connections[request_id]
        logger.info("WebSocket disconnected", request_id=str(request_id))

    async def send_update(self, request_id: UUID, message: dict):
        """Send update to all connections for a request."""
        if request_id in self.active_connections:
            for connection in self.active_connections[request_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(
                        "Failed to send WebSocket message",
                        request_id=str(request_id),
                        error=str(e),
                    )


manager = ConnectionManager()


@router.websocket("/ws/status/{request_id}")
async def websocket_status(websocket: WebSocket, request_id: UUID):
    """WebSocket endpoint for real-time status updates.

    Args:
        websocket: WebSocket connection
        request_id: Request ID to monitor
    """
    await manager.connect(request_id, websocket)
    try:
        # Keep connection alive and wait for messages
        while True:
            # Receive any messages (could be pings, etc.)
            data = await websocket.receive_text()

            # Echo back or handle specific commands if needed
            if data == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})

    except WebSocketDisconnect:
        manager.disconnect(request_id, websocket)
    except Exception as e:
        logger.error("WebSocket error", request_id=str(request_id), error=str(e))
        manager.disconnect(request_id, websocket)


async def broadcast_status_update(request_id: UUID, status_data: dict):
    """Broadcast status update to all connected WebSocket clients.

    Args:
        request_id: Request ID
        status_data: Status data to broadcast
    """
    message = {
        "type": "status_update",
        "request_id": str(request_id),
        "data": status_data,
        "timestamp": datetime.utcnow().isoformat(),
    }
    await manager.send_update(request_id, message)
