from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    BulkMessageRequest,
    BulkMessageResponse,
    BulkMessageItem,
    ConversationRequest,
    ConversationResponse,
    MessageRequest,
    OutreachMessage,
)
from app.services.outreach import OutreachService

router = APIRouter(prefix="/api/outreach", tags=["outreach"])


@router.post("/message", response_model=OutreachMessage)
async def generate_message(request: MessageRequest) -> OutreachMessage:
    try:
        service = OutreachService()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return await service.generate_message(
        lead=request.lead,
        project_id=request.project_id,
        project_description=request.project_description,
        channel=request.channel,
    )


@router.post("/messages/bulk", response_model=BulkMessageResponse)
async def generate_bulk_messages(request: BulkMessageRequest) -> BulkMessageResponse:
    try:
        service = OutreachService()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    items: list[BulkMessageItem] = []
    for lead in request.leads:
        message = await service.generate_message(
            lead=lead,
            project_id=request.project_id,
            project_description=request.project_description,
            channel=request.channel,
        )
        items.append(
            BulkMessageItem(
                place_id=lead.place_id,
                place_name=lead.place_name,
                message=message,
            )
        )

    return BulkMessageResponse(messages=items)


@router.post("/chat", response_model=ConversationResponse)
async def sales_chat(request: ConversationRequest) -> ConversationResponse:
    try:
        service = OutreachService()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return await service.converse(
        lead=request.lead,
        project_id=request.project_id,
        project_description=request.project_description,
        messages=request.messages,
    )
