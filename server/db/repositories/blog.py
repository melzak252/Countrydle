from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from db.models.blog import DailyBlogPost
from db.models.country import Country
from db.models.countrydle import CountrydleDay, CountrydleState

class BlogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, post_id: int) -> Optional[DailyBlogPost]:
        stmt = (
            select(DailyBlogPost)
            .options(joinedload(DailyBlogPost.country))
            .where(DailyBlogPost.id == post_id)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_by_slug(self, slug: str) -> Optional[DailyBlogPost]:
        stmt = (
            select(DailyBlogPost)
            .options(joinedload(DailyBlogPost.country))
            .where(DailyBlogPost.slug == slug)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_by_date(self, post_date: date) -> Optional[DailyBlogPost]:
        stmt = (
            select(DailyBlogPost)
            .options(joinedload(DailyBlogPost.country))
            .where(DailyBlogPost.date == post_date)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_latest(self) -> Optional[DailyBlogPost]:
        stmt = (
            select(DailyBlogPost)
            .options(joinedload(DailyBlogPost.country))
            .order_by(desc(DailyBlogPost.date))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_posts(
        self, limit: int = 20, offset: int = 0, search: Optional[str] = None
    ) -> Tuple[List[DailyBlogPost], int]:
        base_query = select(DailyBlogPost).join(DailyBlogPost.country)

        if search and search.strip():
            term = f"%{search.strip()}%"
            base_query = base_query.where(
                or_(
                    DailyBlogPost.title.ilike(term),
                    DailyBlogPost.subtitle.ilike(term),
                    DailyBlogPost.summary.ilike(term),
                    Country.name.ilike(term),
                )
            )

        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar() or 0

        query = (
            base_query.options(joinedload(DailyBlogPost.country))
            .order_by(desc(DailyBlogPost.date))
            .offset(offset)
            .limit(limit)
        )
        res = await self.session.execute(query)
        posts = list(res.scalars().all())

        return posts, total

    async def create(self, post: DailyBlogPost) -> DailyBlogPost:
        self.session.add(post)
        await self.session.commit()
        await self.session.refresh(post)
        return post

    async def get_day_player_stats(self, post_date: date) -> Dict[str, Any]:
        stmt = (
            select(
                func.count(CountrydleState.id).label("total_players"),
                func.count(case((CountrydleState.won == True, 1))).label("winners_count"),
                func.coalesce(func.sum(CountrydleState.questions_asked), 0).label("total_questions"),
                func.coalesce(func.sum(CountrydleState.guesses_made), 0).label("total_guesses"),
                func.avg(case((CountrydleState.won == True, CountrydleState.questions_asked))).label("avg_questions_won"),
                func.avg(case((CountrydleState.won == True, CountrydleState.guesses_made))).label("avg_guesses_won"),
            )
            .join(CountrydleDay, CountrydleDay.id == CountrydleState.day_id)
            .where(CountrydleDay.date == post_date)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row or row.total_players == 0:
            return {
                "total_players": 0,
                "winners_count": 0,
                "win_rate_pct": 0,
                "total_questions": 0,
                "total_guesses": 0,
                "avg_questions_won": 0,
                "avg_guesses_won": 0,
            }

        win_rate = round((row.winners_count / row.total_players) * 100, 1) if row.total_players > 0 else 0
        return {
            "total_players": row.total_players,
            "winners_count": row.winners_count,
            "win_rate_pct": win_rate,
            "total_questions": int(row.total_questions),
            "total_guesses": int(row.total_guesses),
            "avg_questions_won": round(float(row.avg_questions_won or 0), 1),
            "avg_guesses_won": round(float(row.avg_guesses_won or 0), 1),
        }
