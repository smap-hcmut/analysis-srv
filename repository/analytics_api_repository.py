"""Async repository implementation for Analytics API service."""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, asc, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from core.logger import logger
from interfaces.analytics_api_repository import IAnalyticsApiRepository, PostFilters, ErrorFilters
from models.database import PostAnalytics, PostComment, CrawlError
from models.schemas.base import PaginationParams


class AnalyticsApiRepository(IAnalyticsApiRepository):
    """Async repository implementation for Analytics API operations."""

    def __init__(self, db: AsyncSession):
        """Initialize with async database session."""
        self.db = db

    async def get_posts(
        self,
        filters: PostFilters,
        pagination: PaginationParams,
        sort_by: str = "analyzed_at",
        sort_order: str = "desc",
    ) -> Tuple[List[PostAnalytics], int]:
        """Get paginated posts with filtering and sorting."""
        try:
            # Build base query
            query = select(PostAnalytics).where(PostAnalytics.project_id == filters.project_id)

            # Apply filters
            if filters.brand_name:
                query = query.where(PostAnalytics.brand_name == filters.brand_name)
            if filters.keyword:
                query = query.where(PostAnalytics.keyword == filters.keyword)
            if filters.platform:
                query = query.where(PostAnalytics.platform == filters.platform)
            if filters.sentiment:
                query = query.where(PostAnalytics.overall_sentiment == filters.sentiment)
            if filters.risk_level:
                query = query.where(PostAnalytics.risk_level == filters.risk_level)
            if filters.intent:
                query = query.where(PostAnalytics.primary_intent == filters.intent)
            if filters.is_viral is not None:
                query = query.where(PostAnalytics.is_viral == filters.is_viral)
            if filters.is_kol is not None:
                query = query.where(PostAnalytics.is_kol == filters.is_kol)
            if filters.from_date:
                query = query.where(PostAnalytics.published_at >= filters.from_date)
            if filters.to_date:
                query = query.where(PostAnalytics.published_at <= filters.to_date)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_count = (await self.db.execute(count_query)).scalar()

            # Apply sorting
            sort_column = getattr(PostAnalytics, sort_by, PostAnalytics.analyzed_at)
            if sort_order.lower() == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))

            # Apply pagination
            offset = (pagination.page - 1) * pagination.page_size
            query = query.offset(offset).limit(pagination.page_size)

            # Execute query
            result = await self.db.execute(query)
            posts = result.scalars().all()

            logger.debug(
                f"Retrieved {len(posts)} posts out of {total_count} total "
                f"(page {pagination.page}, size {pagination.page_size})"
            )

            return list(posts), total_count

        except Exception as e:
            logger.error(f"Error retrieving posts: {e}")
            raise

    async def get_posts_all(
        self,
        filters: PostFilters,
        sort_by: str = "analyzed_at",
        sort_order: str = "desc",
        limit: int = 1000,
    ) -> Tuple[List[PostAnalytics], int]:
        """Get all posts without pagination (for export)."""
        try:
            # Build base query
            query = select(PostAnalytics).where(PostAnalytics.project_id == filters.project_id)

            # Apply filters
            if filters.brand_name:
                query = query.where(PostAnalytics.brand_name == filters.brand_name)
            if filters.keyword:
                query = query.where(PostAnalytics.keyword == filters.keyword)
            if filters.platform:
                query = query.where(PostAnalytics.platform == filters.platform)
            if filters.sentiment:
                query = query.where(PostAnalytics.overall_sentiment == filters.sentiment)
            if filters.risk_level:
                query = query.where(PostAnalytics.risk_level == filters.risk_level)
            if filters.intent:
                query = query.where(PostAnalytics.primary_intent == filters.intent)
            if filters.is_viral is not None:
                query = query.where(PostAnalytics.is_viral == filters.is_viral)
            if filters.is_kol is not None:
                query = query.where(PostAnalytics.is_kol == filters.is_kol)
            if filters.from_date:
                query = query.where(PostAnalytics.published_at >= filters.from_date)
            if filters.to_date:
                query = query.where(PostAnalytics.published_at <= filters.to_date)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_count = (await self.db.execute(count_query)).scalar()

            # Apply sorting
            sort_column = getattr(PostAnalytics, sort_by, PostAnalytics.analyzed_at)
            if sort_order.lower() == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))

            # Apply limit (no pagination)
            query = query.limit(limit)

            # Execute query
            result = await self.db.execute(query)
            posts = result.scalars().all()

            logger.debug(f"Retrieved {len(posts)} posts out of {total_count} total (limit {limit})")

            return list(posts), total_count

        except Exception as e:
            logger.error(f"Error retrieving all posts: {e}")
            raise

    async def get_post_by_id(self, post_id: str) -> Optional[PostAnalytics]:
        """Get post by ID with all details including comments."""
        try:
            query = (
                select(PostAnalytics)
                .options(selectinload(PostAnalytics.comments))
                .where(PostAnalytics.id == post_id)
            )

            result = await self.db.execute(query)
            post = result.scalars().first()

            if post:
                logger.debug(f"Retrieved post {post_id} with {len(post.comments)} comments")
            else:
                logger.debug(f"Post {post_id} not found")

            return post

        except Exception as e:
            logger.error(f"Error retrieving post {post_id}: {e}")
            raise

    async def get_summary_stats(
        self,
        project_id: UUID,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> dict:
        """Get aggregated summary statistics."""
        try:
            # Build base condition
            conditions = [PostAnalytics.project_id == project_id]

            if brand_name:
                conditions.append(PostAnalytics.brand_name == brand_name)
            if keyword:
                conditions.append(PostAnalytics.keyword == keyword)
            if from_date:
                conditions.append(PostAnalytics.published_at >= from_date)
            if to_date:
                conditions.append(PostAnalytics.published_at <= to_date)

            base_query = select(PostAnalytics).where(and_(*conditions))

            # Total posts and comments
            total_posts_query = select(func.count()).select_from(base_query.subquery())
            total_comments_query = select(func.sum(PostAnalytics.comment_count)).select_from(
                base_query.subquery()
            )

            total_posts = (await self.db.execute(total_posts_query)).scalar() or 0
            total_comments = (await self.db.execute(total_comments_query)).scalar() or 0

            # Sentiment distribution
            sentiment_query = (
                select(PostAnalytics.overall_sentiment, func.count())
                .where(and_(*conditions))
                .group_by(PostAnalytics.overall_sentiment)
            )
            sentiment_result = await self.db.execute(sentiment_query)
            sentiment_distribution = dict(sentiment_result.fetchall())

            # Risk distribution
            risk_query = (
                select(PostAnalytics.risk_level, func.count())
                .where(and_(*conditions))
                .group_by(PostAnalytics.risk_level)
            )
            risk_result = await self.db.execute(risk_query)
            risk_distribution = dict(risk_result.fetchall())

            # Intent distribution
            intent_query = (
                select(PostAnalytics.primary_intent, func.count())
                .where(and_(*conditions))
                .group_by(PostAnalytics.primary_intent)
            )
            intent_result = await self.db.execute(intent_query)
            intent_distribution = dict(intent_result.fetchall())

            # Platform distribution
            platform_query = (
                select(PostAnalytics.platform, func.count())
                .where(and_(*conditions))
                .group_by(PostAnalytics.platform)
            )
            platform_result = await self.db.execute(platform_query)
            platform_distribution = dict(platform_result.fetchall())

            # Engagement totals and averages
            engagement_query = select(
                func.sum(PostAnalytics.view_count).label("total_views"),
                func.sum(PostAnalytics.like_count).label("total_likes"),
                func.sum(PostAnalytics.share_count).label("total_shares"),
                func.sum(PostAnalytics.save_count).label("total_saves"),
                func.avg(PostAnalytics.overall_sentiment_score).label("avg_sentiment"),
                func.avg(PostAnalytics.impact_score).label("avg_impact"),
                func.count().filter(PostAnalytics.is_viral == True).label("viral_count"),
                func.count().filter(PostAnalytics.is_kol == True).label("kol_count"),
            ).where(and_(*conditions))

            engagement_result = await self.db.execute(engagement_query)
            engagement_data = engagement_result.fetchone()

            return {
                "total_posts": total_posts,
                "total_comments": total_comments,
                "sentiment_distribution": sentiment_distribution,
                "avg_sentiment_score": float(engagement_data.avg_sentiment or 0),
                "risk_distribution": risk_distribution,
                "intent_distribution": intent_distribution,
                "platform_distribution": platform_distribution,
                "engagement_totals": {
                    "views": engagement_data.total_views or 0,
                    "likes": engagement_data.total_likes or 0,
                    "comments": total_comments,
                    "shares": engagement_data.total_shares or 0,
                    "saves": engagement_data.total_saves or 0,
                },
                "viral_count": engagement_data.viral_count or 0,
                "kol_count": engagement_data.kol_count or 0,
                "avg_impact_score": float(engagement_data.avg_impact or 0),
            }

        except Exception as e:
            logger.error(f"Error getting summary stats: {e}")
            raise

    async def get_trends_data(
        self,
        project_id: UUID,
        granularity: str,
        from_date: datetime,
        to_date: datetime,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> List[dict]:
        """Get time-series trends data."""
        try:
            # Determine date truncation based on granularity
            if granularity == "day":
                date_trunc = "day"
            elif granularity == "week":
                date_trunc = "week"
            elif granularity == "month":
                date_trunc = "month"
            else:
                raise ValueError(f"Invalid granularity: {granularity}")

            # Build base conditions
            conditions = [
                PostAnalytics.project_id == project_id,
                PostAnalytics.published_at >= from_date,
                PostAnalytics.published_at <= to_date,
            ]

            if brand_name:
                conditions.append(PostAnalytics.brand_name == brand_name)
            if keyword:
                conditions.append(PostAnalytics.keyword == keyword)

            # Build trends query with date grouping
            trends_query = (
                select(
                    func.date_trunc(date_trunc, PostAnalytics.published_at).label("date"),
                    func.count().label("post_count"),
                    func.sum(PostAnalytics.comment_count).label("comment_count"),
                    func.avg(PostAnalytics.overall_sentiment_score).label("avg_sentiment_score"),
                    func.avg(PostAnalytics.impact_score).label("avg_impact_score"),
                    func.sum(PostAnalytics.view_count).label("total_views"),
                    func.sum(PostAnalytics.like_count).label("total_likes"),
                    func.count().filter(PostAnalytics.is_viral == True).label("viral_count"),
                    func.count()
                    .filter(PostAnalytics.primary_intent == "CRISIS")
                    .label("crisis_count"),
                    func.count()
                    .filter(PostAnalytics.overall_sentiment == "POSITIVE")
                    .label("positive_count"),
                    func.count()
                    .filter(PostAnalytics.overall_sentiment == "NEUTRAL")
                    .label("neutral_count"),
                    func.count()
                    .filter(PostAnalytics.overall_sentiment == "NEGATIVE")
                    .label("negative_count"),
                )
                .where(and_(*conditions))
                .group_by("date")
                .order_by("date")
            )

            result = await self.db.execute(trends_query)
            trends_data = []

            for row in result.fetchall():
                trends_data.append(
                    {
                        "date": row.date.strftime("%Y-%m-%d"),
                        "post_count": row.post_count,
                        "comment_count": row.comment_count or 0,
                        "avg_sentiment_score": float(row.avg_sentiment_score or 0),
                        "avg_impact_score": float(row.avg_impact_score or 0),
                        "sentiment_breakdown": {
                            "POSITIVE": row.positive_count,
                            "NEUTRAL": row.neutral_count,
                            "NEGATIVE": row.negative_count,
                        },
                        "total_views": row.total_views or 0,
                        "total_likes": row.total_likes or 0,
                        "viral_count": row.viral_count,
                        "crisis_count": row.crisis_count,
                    }
                )

            logger.debug(f"Retrieved {len(trends_data)} trend data points")
            return trends_data

        except Exception as e:
            logger.error(f"Error getting trends data: {e}")
            raise

    async def get_top_keywords(
        self,
        project_id: UUID,
        limit: int = 20,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[dict]:
        """Get top keywords with sentiment analysis."""
        try:
            # Build base conditions
            conditions = [PostAnalytics.project_id == project_id]

            if brand_name:
                conditions.append(PostAnalytics.brand_name == brand_name)
            if keyword:
                conditions.append(PostAnalytics.keyword == keyword)
            if from_date:
                conditions.append(PostAnalytics.published_at >= from_date)
            if to_date:
                conditions.append(PostAnalytics.published_at <= to_date)

            # Use PostgreSQL JSONB functions to extract and aggregate keywords
            # This is a complex query that extracts keywords from JSONB and aggregates them
            keywords_query = text(
                """
                SELECT 
                    keyword_data->>'keyword' as keyword,
                    keyword_data->>'aspect' as aspect,
                    COUNT(*) as count,
                    AVG((keyword_data->>'score')::float) as avg_sentiment_score,
                    COUNT(*) FILTER (WHERE (keyword_data->>'sentiment') = 'POSITIVE') as positive_count,
                    COUNT(*) FILTER (WHERE (keyword_data->>'sentiment') = 'NEUTRAL') as neutral_count,
                    COUNT(*) FILTER (WHERE (keyword_data->>'sentiment') = 'NEGATIVE') as negative_count
                FROM post_analytics,
                     LATERAL jsonb_array_elements(keywords) as keyword_data
                WHERE project_id = :project_id
                    AND (:brand_name IS NULL OR brand_name = :brand_name)
                    AND (:keyword IS NULL OR keyword = :keyword) 
                    AND (:from_date IS NULL OR published_at >= :from_date)
                    AND (:to_date IS NULL OR published_at <= :to_date)
                    AND keywords IS NOT NULL
                GROUP BY keyword_data->>'keyword', keyword_data->>'aspect'
                ORDER BY count DESC
                LIMIT :limit
            """
            )

            result = await self.db.execute(
                keywords_query,
                {
                    "project_id": str(project_id),
                    "brand_name": brand_name,
                    "keyword": keyword,
                    "from_date": from_date,
                    "to_date": to_date,
                    "limit": limit,
                },
            )

            keywords_data = []
            for row in result.fetchall():
                keywords_data.append(
                    {
                        "keyword": row.keyword,
                        "count": row.count,
                        "avg_sentiment_score": float(row.avg_sentiment_score or 0),
                        "aspect": row.aspect,
                        "sentiment_breakdown": {
                            "POSITIVE": row.positive_count,
                            "NEUTRAL": row.neutral_count,
                            "NEGATIVE": row.negative_count,
                        },
                    }
                )

            logger.debug(f"Retrieved {len(keywords_data)} top keywords")
            return keywords_data

        except Exception as e:
            logger.error(f"Error getting top keywords: {e}")
            raise

    async def get_alert_posts(
        self,
        project_id: UUID,
        limit: int = 10,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> dict:
        """Get posts requiring attention (critical, viral, crisis)."""
        try:
            # Build base conditions
            conditions = [PostAnalytics.project_id == project_id]

            if brand_name:
                conditions.append(PostAnalytics.brand_name == brand_name)
            if keyword:
                conditions.append(PostAnalytics.keyword == keyword)

            # Critical posts (CRITICAL risk level)
            critical_query = (
                select(PostAnalytics)
                .where(and_(PostAnalytics.risk_level == "CRITICAL", *conditions))
                .order_by(desc(PostAnalytics.impact_score))
                .limit(limit)
            )

            # Viral posts (is_viral = True)
            viral_query = (
                select(PostAnalytics)
                .where(and_(PostAnalytics.is_viral == True, *conditions))
                .order_by(desc(PostAnalytics.impact_score))
                .limit(limit)
            )

            # Crisis intent posts
            crisis_query = (
                select(PostAnalytics)
                .where(and_(PostAnalytics.primary_intent == "CRISIS", *conditions))
                .order_by(desc(PostAnalytics.impact_score))
                .limit(limit)
            )

            # Execute queries concurrently
            critical_result = await self.db.execute(critical_query)
            viral_result = await self.db.execute(viral_query)
            crisis_result = await self.db.execute(crisis_query)

            critical_posts = list(critical_result.scalars().all())
            viral_posts = list(viral_result.scalars().all())
            crisis_posts = list(crisis_result.scalars().all())

            # Get summary counts
            critical_count_query = select(func.count()).where(
                and_(PostAnalytics.risk_level == "CRITICAL", *conditions)
            )
            viral_count_query = select(func.count()).where(
                and_(PostAnalytics.is_viral == True, *conditions)
            )
            crisis_count_query = select(func.count()).where(
                and_(PostAnalytics.primary_intent == "CRISIS", *conditions)
            )

            critical_count = (await self.db.execute(critical_count_query)).scalar() or 0
            viral_count = (await self.db.execute(viral_count_query)).scalar() or 0
            crisis_count = (await self.db.execute(crisis_count_query)).scalar() or 0

            return {
                "critical_posts": critical_posts,
                "viral_posts": viral_posts,
                "crisis_intents": crisis_posts,
                "summary": {
                    "critical_count": critical_count,
                    "viral_count": viral_count,
                    "crisis_count": crisis_count,
                },
            }

        except Exception as e:
            logger.error(f"Error getting alert posts: {e}")
            raise

    async def get_crawl_errors(
        self,
        filters: ErrorFilters,
        pagination: PaginationParams,
    ) -> Tuple[List[CrawlError], int]:
        """Get paginated crawl errors with filtering."""
        try:
            # Build base query
            query = select(CrawlError).where(CrawlError.project_id == filters.project_id)

            # Apply filters
            if filters.job_id:
                query = query.where(CrawlError.job_id == filters.job_id)
            if filters.error_code:
                query = query.where(CrawlError.error_code == filters.error_code)
            if filters.from_date:
                query = query.where(CrawlError.created_at >= filters.from_date)
            if filters.to_date:
                query = query.where(CrawlError.created_at <= filters.to_date)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_count = (await self.db.execute(count_query)).scalar()

            # Apply sorting and pagination
            query = query.order_by(desc(CrawlError.created_at))
            offset = (pagination.page - 1) * pagination.page_size
            query = query.offset(offset).limit(pagination.page_size)

            # Execute query
            result = await self.db.execute(query)
            errors = result.scalars().all()

            logger.debug(f"Retrieved {len(errors)} crawl errors out of {total_count} total")

            return list(errors), total_count

        except Exception as e:
            logger.error(f"Error retrieving crawl errors: {e}")
            raise

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            # Simple query to test connection
            result = await self.db.execute(text("SELECT 1"))
            return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
