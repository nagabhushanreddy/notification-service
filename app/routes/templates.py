from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from uuid import UUID
import uuid
from app.models import (
    TemplateCreateRequest,
    TemplateResponse,
    TemplateStatusEnum,
)
from app.services import TemplateService

router = APIRouter(prefix="/api/v1", tags=["templates"])
template_service = TemplateService()


@router.post("/templates", status_code=201)
async def create_template(request: Request, payload: TemplateCreateRequest):
    """Create a new template"""
    try:
        tenant_id = getattr(request.state, "tenant_id", None)
        user_id = getattr(request.state, "user_id", None)
        correlation_id = getattr(request.state, "correlation_id", None)

        if not tenant_id:
            return JSONResponse(
                content={
                    "success": False,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Missing tenant_id in token",
                        "details": None,
                    },
                    "data": None,
                    "metadata": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "correlation_id": correlation_id,
                    },
                },
                status_code=401,
            )

        # created_by may not be a valid UUID in tests; coerce safely
        created_by_uuid = None
        try:
            if isinstance(user_id, UUID):
                created_by_uuid = user_id
            elif user_id is not None:
                created_by_uuid = UUID(str(user_id))
        except Exception:
            created_by_uuid = None

        template = await template_service.create_template(
            tenant_id=tenant_id,
            name=payload.template_name,
            notification_type=payload.notification_type,
            channels_content=payload.channels_content,
            required_variables=payload.required_variables,
            created_by=created_by_uuid,
        )

        response = TemplateResponse(
            id=template.id,
            tenant_id=template.tenant_id,
            template_name=template.name,
            notification_type=template.notification_type,
            channels_content=template.channels_content,
            required_variables=template.required_variables,
            version=template.version,
            status=template.status,
            created_at=template.created_at,
            updated_at=template.updated_at,
            created_by=template.created_by,
        )

        return {
            "success": True,
            "error": None,
            "data": response.model_dump(),
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "correlation_id": correlation_id,
            },
        }

    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": str(e),
                    "details": None,
                },
                "data": None,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": getattr(request.state, "correlation_id", None),
                },
            },
            status_code=500,
        )


@router.get("/templates")
async def list_templates(request: Request):
    """List all templates for tenant"""
    try:
        tenant_id = getattr(request.state, "tenant_id", None)
        correlation_id = getattr(request.state, "correlation_id", None)

        if not tenant_id:
            return JSONResponse(
                content={
                    "success": False,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Missing tenant_id in token",
                        "details": None,
                    },
                    "data": None,
                    "metadata": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "correlation_id": correlation_id,
                    },
                },
                status_code=401,
            )

        templates = await template_service.list_templates(tenant_id)

        template_responses = [
            {
                "id": t.id,
                "template_name": t.name,
                "notification_type": t.notification_type.value,
                "version": t.version,
                "status": t.status.value,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            }
            for t in templates
        ]

        return {
            "success": True,
            "error": None,
            "data": template_responses,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "correlation_id": correlation_id,
            },
        }

    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": str(e),
                    "details": None,
                },
                "data": None,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": getattr(request.state, "correlation_id", None),
                },
            },
            status_code=500,
        )


@router.patch("/templates/{template_id}")
async def update_template(request: Request, template_id: UUID, status: str = "active"):
    """Update template status"""
    try:
        correlation_id = getattr(request.state, "correlation_id", None)

        template = await template_service.get_template(template_id)
        if not template:
            return JSONResponse(
                content={
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Template not found: {template_id}",
                        "details": None,
                    },
                    "data": None,
                    "metadata": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "correlation_id": correlation_id,
                    },
                },
                status_code=404,
            )

        if status == "active":
            await template_service.activate_template(template_id)

        return {
            "success": True,
            "error": None,
            "data": {
                "id": template.id,
                "status": template.status.value,
                "updated_at": template.updated_at,
            },
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "correlation_id": correlation_id,
            },
        }

    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": str(e),
                    "details": None,
                },
                "data": None,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": getattr(request.state, "correlation_id", None),
                },
            },
            status_code=500,
        )
