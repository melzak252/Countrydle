from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from db.models.blog import DailyBlogPost
from db.models.country import Country
from db.repositories.participation import _aggregate, _participants, _stats

class BlogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _post_query(self, public_only: bool = True):
        query = select(DailyBlogPost).options(
            joinedload(DailyBlogPost.country), joinedload(DailyBlogPost.reviewer)
        )
        if public_only:
            query = query.where(DailyBlogPost.date < datetime.now(timezone.utc).date())
        return query

    async def get_by_id(self, post_id: int, *, for_update: bool = False) -> Optional[DailyBlogPost]:
        query = self._post_query(public_only=False).where(DailyBlogPost.id == post_id)
        if for_update:
            query = query.with_for_update(of=DailyBlogPost)
        result = await self.session.execute(query.execution_options(populate_existing=True))
        return result.scalars().first()

    async def get_by_slug(self, slug: str, *, public_only: bool = True) -> Optional[DailyBlogPost]:
        result = await self.session.execute(
            self._post_query(public_only).where(DailyBlogPost.slug == slug)
        )
        return result.scalars().first()

    async def get_by_date(self, post_date: date, *, public_only: bool = True) -> Optional[DailyBlogPost]:
        result = await self.session.execute(
            self._post_query(public_only).where(DailyBlogPost.date == post_date)
        )
        return result.scalars().first()

    async def get_latest(self) -> Optional[DailyBlogPost]:
        result = await self.session.execute(
            self._post_query().order_by(desc(DailyBlogPost.date)).limit(1)
        )
        return result.scalars().first()

    async def list_posts(
        self, limit: int = 20, offset: int = 0, search: Optional[str] = None,
        *, public_only: bool = True,
    ) -> Tuple[List[DailyBlogPost], int]:
        base_query = select(DailyBlogPost).join(DailyBlogPost.country)
        if public_only:
            base_query = base_query.where(DailyBlogPost.date < datetime.now(timezone.utc).date())
        if search and search.strip():
            term = f"%{search.strip()}%"
            base_query = base_query.where(or_(
                DailyBlogPost.title.ilike(term), DailyBlogPost.subtitle.ilike(term),
                DailyBlogPost.summary.ilike(term), Country.name.ilike(term),
            ))
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        result = await self.session.execute(
            base_query.options(
                joinedload(DailyBlogPost.country), joinedload(DailyBlogPost.reviewer)
            ).order_by(desc(DailyBlogPost.date)).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), count_result.scalar() or 0

    async def create(self, post: DailyBlogPost) -> DailyBlogPost:
        self.session.add(post)
        await self.session.commit()
        return await self.get_by_id(post.id)

    async def update(self, post: DailyBlogPost, fields: Dict[str, Any]) -> DailyBlogPost:
        for name, value in fields.items():
            setattr(post, name, value)
        post.reviewed_by_id = None
        post.reviewed_at = None
        post.updated_at = max(
            datetime.now(timezone.utc), post.updated_at + timedelta(microseconds=1),
        )
        await self.session.commit()
        return await self.get_by_id(post.id)

    async def replace_generated(
        self, post_id: int, payload: Dict[str, Any], expected_updated_at: datetime,
    ) -> bool:
        """Replace only the captured version, never confer a human review."""
        generated_fields = {
            "title", "subtitle", "summary", "fast_facts", "fun_facts",
            "deduction_masterclass", "content_markdown", "source_links",
            "editorial_note", "ai_assisted",
        }
        if payload.keys() - generated_fields:
            raise ValueError("Generated replacements may only change editable content and AI attribution")
        statement = (
            update(DailyBlogPost)
            .where(
                DailyBlogPost.id == post_id,
                DailyBlogPost.updated_at == expected_updated_at,
            )
            .values(
                **payload,
                reviewed_by_id=None,
                reviewed_at=None,
                updated_at=func.greatest(
                    datetime.now(timezone.utc),
                    DailyBlogPost.updated_at + timedelta(microseconds=1),
                ),
            )
            .execution_options(synchronize_session=False)
        )
        try:
            result = await self.session.execute(statement)
            replaced = result.rowcount == 1
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        # Bulk SQL bypasses ORM history, including stale already-NULL reviews.
        # Both successful and failed CAS operations must forget loaded versions.
        self.session.expire_all()
        return replaced

    async def set_review(self, post: DailyBlogPost, reviewer_id: Optional[int]) -> DailyBlogPost:
        timestamp = datetime.now(timezone.utc)
        post.reviewed_by_id = reviewer_id
        post.reviewed_at = timestamp if reviewer_id is not None else None
        post.updated_at = max(timestamp, post.updated_at + timedelta(microseconds=1))
        await self.session.commit()
        return await self.get_by_id(post.id)

    async def get_player_stats_for_dates(self, dates: List[date]) -> Dict[date, Dict[str, Any]]:
        if not dates:
            return {}
        participants = _participants(min(dates), max(dates), "countrydle")
        result = await self.session.execute(
            _aggregate(participants).add_columns(participants.c.date)
            .where(participants.c.date.in_(dates)).group_by(participants.c.date)
        )
        stats_by_date = {}
        for row in result:
            stats = _stats(row)
            stats.pop("total_games")
            stats_by_date[row.date] = stats
        empty_stats = {
            "total_players": 0, "winners_count": 0, "win_rate_pct": 0.0,
            "total_questions": 0, "total_guesses": 0,
            "avg_questions_won": 0.0, "avg_guesses_won": 0.0,
        }
        return {post_date: stats_by_date.get(post_date, empty_stats.copy()) for post_date in dates}

    async def get_day_player_stats(self, post_date: date) -> Dict[str, Any]:
        return (await self.get_player_stats_for_dates([post_date]))[post_date]
