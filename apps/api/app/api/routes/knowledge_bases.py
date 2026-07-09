from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.api.routes.agents import get_request_context
from app.db.session import get_session
from app.schemas.knowledge_bases import (
    DocumentCreate,
    DocumentResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseDetailResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    RetrievalRequest,
    RetrievalResponse,
)
from app.services import knowledge_bases
from app.services.context import RequestContext

router = APIRouter(tags=["knowledge-bases"])


@router.get("/knowledge-bases", response_model=KnowledgeBaseListResponse)
def list_knowledge_bases(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> KnowledgeBaseListResponse:
    return KnowledgeBaseListResponse(
        items=knowledge_bases.list_knowledge_bases(session, workspace_id=context.workspace.id)
    )


@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    request: Request,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> KnowledgeBaseResponse:
    return knowledge_bases.create_knowledge_base(
        session,
        workspace_id=context.workspace.id,
        created_by=context.user.id,
        payload=payload,
        settings=request.app.state.settings,
    )


@router.get("/knowledge-bases/{knowledge_base_id}", response_model=KnowledgeBaseDetailResponse)
def get_knowledge_base(
    knowledge_base_id: UUID,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> KnowledgeBaseDetailResponse:
    try:
        return knowledge_bases.get_knowledge_base_detail(
            session,
            workspace_id=context.workspace.id,
            knowledge_base_id=knowledge_base_id,
        )
    except knowledge_bases.KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_document(
    knowledge_base_id: UUID,
    payload: DocumentCreate,
    request: Request,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> DocumentResponse:
    try:
        return knowledge_bases.add_document_content(
            session,
            workspace_id=context.workspace.id,
            knowledge_base_id=knowledge_base_id,
            payload=payload,
            object_store=request.app.state.object_store,
            embedding_client=request.app.state.embedding_client,
        )
    except knowledge_bases.KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except knowledge_bases.DocumentProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    knowledge_base_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    metadata: str = Form(default="{}"),
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> DocumentResponse:
    import json

    try:
        parsed_metadata = json.loads(metadata)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="metadata must be valid JSON") from exc
    if not isinstance(parsed_metadata, dict):
        raise HTTPException(status_code=422, detail="metadata must be a JSON object")

    data = await file.read()
    try:
        return knowledge_bases.add_document_bytes(
            session,
            workspace_id=context.workspace.id,
            knowledge_base_id=knowledge_base_id,
            filename=file.filename or "document.txt",
            content_type=file.content_type or "application/octet-stream",
            data=data,
            metadata=parsed_metadata,
            source_type="file",
            object_store=request.app.state.object_store,
            embedding_client=request.app.state.embedding_client,
        )
    except knowledge_bases.KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except knowledge_bases.DocumentProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/knowledge-bases/{knowledge_base_id}/retrieve", response_model=RetrievalResponse)
def retrieve(
    knowledge_base_id: UUID,
    payload: RetrievalRequest,
    request: Request,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> RetrievalResponse:
    try:
        return knowledge_bases.retrieve_from_knowledge_base(
            session,
            workspace_id=context.workspace.id,
            knowledge_base_id=knowledge_base_id,
            payload=payload,
            embedding_client=request.app.state.embedding_client,
        )
    except knowledge_bases.KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
