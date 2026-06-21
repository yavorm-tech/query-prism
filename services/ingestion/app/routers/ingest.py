import os
import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, Query
from pydantic import BaseModel
from app.config import get_settings
from app.db.connection import get_pool
from app.services.auth import get_current_user, can_access_team
from app.services.users import get_team
from app.services.topics import get_topic
from app.services.rate_limit import limiter
from app.services.cache import invalidate_team_cache
from app.services.billing_client import check_storage_limit, decrement_storage
from app.services.graph.writer import delete_document_graph
from app.services.audit import log_event

settings = get_settings()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingestion"])

ALLOWED_EXTENSIONS = {
    "pdf", "docx", "doc", "txt", "md",
    "png", "jpg", "jpeg", "tiff",
    "mp4", "mov", "avi", "mkv", "mp3", "wav",
    "csv", "tsv",
}


class IngestResponse(BaseModel):
    document_id: str
    job_id: str
    filename: str
    status: str
    team_id: str
    topic_id: str | None = None


class StatusResponse(BaseModel):
    document_id: str
    status: str
    team_id: str
    topic_id: str | None = None
    error_message: str | None = None


class DocumentItem(BaseModel):
    document_id: str
    original_name: str
    source_type: str
    file_size: int | None
    status: str
    team_id: str
    team_name: str | None = None
    topic_id: str | None = None
    topic_name: str | None = None
    uploaded_by_username: str | None = None
    visibility: str
    error_message: str | None = None
    created_at: str


@router.post("", response_model=IngestResponse)
@limiter.limit("20/minute")
async def ingest_file(
    request: Request,
    file: UploadFile = File(...),
    team_id: str | None = Query(None),
    topic_id: str | None = Query(None),
    visibility: str = Query("team"),
    current_user: dict = Depends(get_current_user),
):
    user_team_ids = current_user.get("team_ids", [])
    if not user_team_ids:
        raise HTTPException(400, "You are not a member of any team.")

    if topic_id:
        topic = await get_topic(topic_id)
        if not topic:
            raise HTTPException(404, "Topic not found")
        if not can_access_team(current_user, str(topic["team_id"])):
            raise HTTPException(403, "You do not have access to this topic's team")
        team_id = str(topic["team_id"])

    if team_id is None:
        if len(user_team_ids) == 1:
            team_id = user_team_ids[0]
        else:
            team_id = current_user.get("default_team_id")
            if not team_id:
                raise HTTPException(400, f"You belong to {len(user_team_ids)} teams. Please specify team_id.")

    if not can_access_team(current_user, team_id):
        raise HTTPException(403, "You are not a member of this team")

    team = await get_team(team_id, current_user["company_id"])
    if not team:
        raise HTTPException(404, "Team not found")

    ext = Path(file.filename or "").suffix.lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: .{ext}")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(413, f"File too large: {size_mb:.1f} MB (max {settings.max_upload_size_mb} MB)")

    await check_storage_limit(current_user["company_id"], len(content))

    if visibility not in ("team", "company"):
        raise HTTPException(400, "visibility must be 'team' or 'company'")

    document_id = str(uuid.uuid4())
    os.makedirs(settings.upload_dir, exist_ok=True)
    file_path = os.path.join(settings.upload_dir, f"{document_id}.{ext}")

    with open(file_path, "wb") as f:
        f.write(content)

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO documents
                (id, company_id, team_id, topic_id, uploaded_by, filename, original_name,
                 source_type, file_size, visibility, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'pending')
            """,
            document_id, current_user["company_id"], team_id, topic_id,
            current_user["sub"], os.path.basename(file_path), file.filename,
            _source_type(ext), len(content), visibility,
        )

    from app.worker import ingest_document
    task = ingest_document.apply_async(
        args=[document_id, file_path, _source_type(ext)],
        queue="ingestion",
    )

    await invalidate_team_cache(team_id)
    await log_event(
        company_id=current_user["company_id"],
        event_type="document.uploaded",
        actor_id=current_user["sub"],
        actor_username=current_user["username"],
        team_id=team_id,
        resource_type="document",
        resource_id=document_id,
        resource_name=file.filename,
        metadata={"size_bytes": len(content), "source_type": _source_type(ext),
                  "topic_id": topic_id, "visibility": visibility},
    )
    logger.info(f"[{current_user['username']}] Queued {task.id} for '{file.filename}' → team {team['name']}")

    return IngestResponse(
        document_id=document_id, job_id=task.id,
        filename=file.filename or "", status="pending",
        team_id=team_id, topic_id=topic_id,
    )


@router.get("", response_model=list[DocumentItem])
async def list_documents(
    current_user: dict = Depends(get_current_user),
    team_id: str | None = Query(None),
    topic_id: str | None = Query(None),
):
    pool = await get_pool()
    company_id = current_user["company_id"]
    role = current_user.get("role", "member")
    team_ids = current_user.get("team_ids", [])

    async with pool.acquire() as conn:
        if topic_id:
            rows = await conn.fetch(
                """
                SELECT d.id, d.original_name, d.source_type, d.file_size,
                       d.status, d.team_id, d.topic_id, d.visibility,
                       d.error_message, d.created_at,
                       t.name AS team_name, tp.name AS topic_name,
                       u.username AS uploaded_by_username
                FROM documents d
                LEFT JOIN teams t ON t.id = d.team_id
                LEFT JOIN topics tp ON tp.id = d.topic_id
                LEFT JOIN users u ON u.id = d.uploaded_by
                WHERE d.topic_id = $1 ORDER BY d.created_at DESC
                """,
                topic_id,
            )
        elif role in ("admin", "owner"):
            base = "WHERE d.company_id = $1"
            params = [company_id]
            if team_id:
                base += " AND d.team_id = $2"
                params.append(team_id)
            rows = await conn.fetch(
                f"""
                SELECT d.id, d.original_name, d.source_type, d.file_size,
                       d.status, d.team_id, d.topic_id, d.visibility,
                       d.error_message, d.created_at,
                       t.name AS team_name, tp.name AS topic_name,
                       u.username AS uploaded_by_username
                FROM documents d
                LEFT JOIN teams t ON t.id = d.team_id
                LEFT JOIN topics tp ON tp.id = d.topic_id
                LEFT JOIN users u ON u.id = d.uploaded_by
                {base} ORDER BY d.created_at DESC
                """,
                *params,
            )
        else:
            if not team_ids:
                return []
            rows = await conn.fetch(
                """
                SELECT d.id, d.original_name, d.source_type, d.file_size,
                       d.status, d.team_id, d.topic_id, d.visibility,
                       d.error_message, d.created_at,
                       t.name AS team_name, tp.name AS topic_name,
                       u.username AS uploaded_by_username
                FROM documents d
                LEFT JOIN teams t ON t.id = d.team_id
                LEFT JOIN topics tp ON tp.id = d.topic_id
                LEFT JOIN users u ON u.id = d.uploaded_by
                WHERE (d.team_id = ANY($1::uuid[]) OR (d.company_id = $2 AND d.visibility = 'company'))
                ORDER BY d.created_at DESC
                """,
                team_ids, company_id,
            )

    return [
        DocumentItem(
            document_id=str(r["id"]),
            original_name=r["original_name"],
            source_type=r["source_type"],
            file_size=r["file_size"],
            status=r["status"],
            team_id=str(r["team_id"]),
            topic_id=str(r["topic_id"]) if r["topic_id"] else None,
            team_name=r.get("team_name"),
            uploaded_by_username=r.get("uploaded_by_username"),
            visibility=r["visibility"],
            error_message=r.get("error_message"),
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]


@router.get("/{document_id}", response_model=StatusResponse)
async def get_status(document_id: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, team_id, topic_id, status, error_message FROM documents WHERE id = $1",
            document_id,
        )
    if not row:
        raise HTTPException(404, "Document not found")
    if not can_access_team(current_user, str(row["team_id"])):
        raise HTTPException(403, "Access denied")
    return StatusResponse(
        document_id=str(row["id"]), status=row["status"],
        team_id=str(row["team_id"]),
        topic_id=str(row["topic_id"]) if row["topic_id"] else None,
        error_message=row.get("error_message"),
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, team_id, company_id, uploaded_by, file_size FROM documents WHERE id = $1",
            document_id,
        )
    if not row:
        raise HTTPException(404, "Document not found")

    is_uploader = str(row["uploaded_by"]) == current_user["sub"]
    is_admin = current_user.get("role") in ("admin", "owner")
    if not is_uploader and not is_admin:
        raise HTTPException(403, "Only the uploader or an admin can delete this document")
    if not can_access_team(current_user, str(row["team_id"])):
        raise HTTPException(403, "Access denied")

    async with pool.acquire() as conn:
        filename = await conn.fetchval("SELECT original_name FROM documents WHERE id = $1", document_id)
        await conn.execute("DELETE FROM documents WHERE id = $1", document_id)

    if row["file_size"]:
        await decrement_storage(str(row["company_id"]), row["file_size"])

    await delete_document_graph(document_id)
    await invalidate_team_cache(str(row["team_id"]))

    await log_event(
        company_id=str(row["company_id"]),
        event_type="document.deleted",
        actor_id=current_user["sub"],
        actor_username=current_user["username"],
        team_id=str(row["team_id"]),
        resource_type="document",
        resource_id=document_id,
        resource_name=filename,
    )


def _source_type(ext: str) -> str:
    if ext in {"pdf"}:                                      return "pdf"
    if ext in {"docx", "doc"}:                              return "docx"
    if ext in {"txt", "md"}:                                return "txt"
    if ext in {"png", "jpg", "jpeg", "tiff"}:               return "image"
    if ext in {"mp4", "mov", "avi", "mkv", "mp3", "wav"}:  return "video"
    if ext in {"csv", "tsv"}:                               return "csv"
    return "web"
