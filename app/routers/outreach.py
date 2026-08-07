from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    BulkMessageRequest,
    BulkMessageResponse,
    BulkMessageItem,
    ConversationRequest,
    ConversationResponse,
    MessageRequest,
    OutreachMessage,
    SendCampaignRequest,
    SendCampaignResponse,
)
from app.services.campaign_send import run_send_campaign
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
        project_id=request.lead.recommended_project_id or request.project_id,
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
            project_id=lead.recommended_project_id or request.project_id,
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
        project_id=request.lead.recommended_project_id or request.project_id,
        project_description=request.project_description,
        messages=request.messages,
    )


@router.post("/send-campaign", response_model=SendCampaignResponse)
async def send_whatsapp_campaign(request: SendCampaignRequest) -> SendCampaignResponse:
    """Envía plantilla Twilio a leads ready (CSV) o CRM. dry_run=true por defecto."""
    if request.source not in ("csv", "crm"):
        raise HTTPException(status_code=400, detail="source debe ser 'csv' o 'crm'")
    try:
        return await run_send_campaign(
            source=request.source,
            csv_path=request.csv_path,
            dry_run=request.dry_run,
            limit=request.limit,
            only_status=request.only_status,
            mark_contacted=request.mark_contacted,
            update_crm_on_dry_run=request.update_crm_on_dry_run,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error Twilio/campaña: {exc}") from exc
