from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.repositories.patch_note import PatchNoteRepository
from schemas.patch_note import PatchNoteItem, PatchNoteListResponse

router = APIRouter(prefix="/patch-notes", tags=["patch-notes"])


@router.get("", response_model=PatchNoteListResponse)
async def list_patch_notes(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
) -> PatchNoteListResponse:
    notes, total = await PatchNoteRepository(session).list_published(limit, (page - 1) * limit)
    items = [
        PatchNoteItem(
            id=note.id,
            version=note.version,
            title=note.title,
            body=note.body,
            published_at=note.published_at,
        )
        for note in notes
    ]
    return PatchNoteListResponse(items=items, total=total, page=page, limit=limit)
