from typing import List, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.patch_note import PatchNote


class PatchNoteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_published(self, limit: int, offset: int) -> Tuple[List[PatchNote], int]:
        total = await self.session.scalar(select(func.count()).select_from(PatchNote)) or 0
        statement = select(PatchNote).order_by(PatchNote.published_at.desc(), PatchNote.id.desc()).offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all()), total
