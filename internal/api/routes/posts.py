"""Posts API routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.logger import logger
from interfaces.analytics_api_repository import PostFilters
from models.schemas.base import (
    ApiResponse,
    ListResponse,
    PaginatedResponse,
    PaginationParams,
    create_list_response_meta,
    create_pagination_info,
)
from models.schemas.posts import PostListItem, PostDetail, PostFiltersRequest, PostSortingRequest
from repository.analytics_api_repository import AnalyticsApiRepository

router = APIRouter()


@router.get("/posts", response_model=PaginatedResponse[PostListItem])
async def get_posts(
    request: Request,
    filters: PostFiltersRequest = Depends(),
    sorting: PostSortingRequest = Depends(),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of analyzed posts with filtering and sorting."""
    try:
        request_id = getattr(request.state, "request_id", "unknown")

        logger.info(
            f"Request {request_id}: Getting posts for project {filters.project_id}, "
            f"page {pagination.page}, size {pagination.page_size}"
        )

        # Create repository
        repo = AnalyticsApiRepository(db)

        # Convert request filters to repository filters
        post_filters = PostFilters(
            project_id=filters.project_id,
            brand_name=filters.brand_name,
            keyword=filters.keyword,
            platform=filters.platform,
            sentiment=filters.sentiment,
            risk_level=filters.risk_level,
            intent=filters.intent,
            is_viral=filters.is_viral,
            is_kol=filters.is_kol,
            from_date=filters.from_date,
            to_date=filters.to_date,
        )

        # Get posts from repository
        posts, total_count = await repo.get_posts(
            filters=post_filters,
            pagination=pagination,
            sort_by=sorting.sort_by,
            sort_order=sorting.sort_order,
        )

        # Convert to response format with truncated content
        post_items = []
        for post in posts:
            # Truncate content for list view
            content_text = post.content_text
            if content_text and len(content_text) > 300:
                content_text = content_text[:300] + "..."

            post_item = PostListItem(
                id=post.id,
                platform=post.platform,
                permalink=post.permalink,
                content_text=content_text,
                author_name=post.author_name,
                author_username=post.author_username,
                author_is_verified=post.author_is_verified,
                overall_sentiment=post.overall_sentiment,
                overall_sentiment_score=post.overall_sentiment_score,
                primary_intent=post.primary_intent,
                impact_score=post.impact_score,
                risk_level=post.risk_level,
                is_viral=post.is_viral,
                is_kol=post.is_kol,
                view_count=post.view_count,
                like_count=post.like_count,
                comment_count=post.comment_count,
                published_at=post.published_at,
                analyzed_at=post.analyzed_at,
                brand_name=post.brand_name,
                keyword=post.keyword,
                job_id=post.job_id,
            )
            post_items.append(post_item)

        return PaginatedResponse(
            success=True,
            data=post_items,
            meta=create_pagination_info(
                page=pagination.page, page_size=pagination.page_size, total_items=total_count
            ),
        )

    except Exception as e:
        logger.error(f"Error in get_posts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/posts/all", response_model=ListResponse[PostListItem])
async def get_all_posts(
    request: Request,
    filters: PostFiltersRequest = Depends(),
    sorting: PostSortingRequest = Depends(),
    limit: int = Query(
        default=1000, ge=1, le=10000, description="Maximum number of records (max 10000)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get all posts without pagination. Use for export or when full data is needed."""
    try:
        request_id = getattr(request.state, "request_id", "unknown")

        logger.info(
            f"Request {request_id}: Getting all posts for project {filters.project_id}, "
            f"limit {limit}"
        )

        # Create repository
        repo = AnalyticsApiRepository(db)

        # Convert request filters to repository filters
        post_filters = PostFilters(
            project_id=filters.project_id,
            brand_name=filters.brand_name,
            keyword=filters.keyword,
            platform=filters.platform,
            sentiment=filters.sentiment,
            risk_level=filters.risk_level,
            intent=filters.intent,
            is_viral=filters.is_viral,
            is_kol=filters.is_kol,
            from_date=filters.from_date,
            to_date=filters.to_date,
        )

        # Get all posts from repository (no pagination)
        posts, total_count = await repo.get_posts_all(
            filters=post_filters,
            sort_by=sorting.sort_by,
            sort_order=sorting.sort_order,
            limit=limit,
        )

        # Convert to response format with truncated content
        post_items = []
        for post in posts:
            # Truncate content for list view
            content_text = post.content_text
            if content_text and len(content_text) > 300:
                content_text = content_text[:300] + "..."

            post_item = PostListItem(
                id=post.id,
                platform=post.platform,
                permalink=post.permalink,
                content_text=content_text,
                author_name=post.author_name,
                author_username=post.author_username,
                author_is_verified=post.author_is_verified,
                overall_sentiment=post.overall_sentiment,
                overall_sentiment_score=post.overall_sentiment_score,
                primary_intent=post.primary_intent,
                impact_score=post.impact_score,
                risk_level=post.risk_level,
                is_viral=post.is_viral,
                is_kol=post.is_kol,
                view_count=post.view_count,
                like_count=post.like_count,
                comment_count=post.comment_count,
                published_at=post.published_at,
                analyzed_at=post.analyzed_at,
                brand_name=post.brand_name,
                keyword=post.keyword,
                job_id=post.job_id,
            )
            post_items.append(post_item)

        # Return response with total count (no pagination)
        return ListResponse(
            success=True,
            data=post_items,
            meta=create_list_response_meta(total_count),
        )

    except Exception as e:
        logger.error(f"Error in get_all_posts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/posts/{post_id}", response_model=ApiResponse[PostDetail])
async def get_post_by_id(post_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Get complete post details by ID including comments."""
    try:
        request_id = getattr(request.state, "request_id", "unknown")

        logger.info(f"Request {request_id}: Getting post details for {post_id}")

        # Create repository
        repo = AnalyticsApiRepository(db)

        # Get post by ID
        post = await repo.get_post_by_id(post_id)

        if not post:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": {
                        "code": "RES_001",
                        "message": f"Post with id '{post_id}' not found",
                        "details": [],
                    },
                },
            )

        # Convert to detailed response format
        from models.schemas.posts import (
            CommentItem,
            SentimentProbabilities,
            ImpactBreakdown,
            AspectBreakdown,
            KeywordItem,
        )

        # Process comments
        comments = []
        for comment in post.comments:
            comments.append(
                CommentItem(
                    id=comment.id,
                    comment_id=comment.comment_id,
                    text=comment.text,
                    author_name=comment.author_name,
                    likes=comment.likes,
                    sentiment=comment.sentiment,
                    sentiment_score=comment.sentiment_score,
                    commented_at=comment.commented_at,
                )
            )

        # Process optional JSONB fields
        sentiment_probs = None
        if post.sentiment_probabilities:
            sentiment_probs = SentimentProbabilities(**post.sentiment_probabilities)

        impact_breakdown = None
        if post.impact_breakdown:
            impact_breakdown = ImpactBreakdown(**post.impact_breakdown)

        aspects_breakdown = None
        if post.aspects_breakdown:
            aspects_breakdown = {}
            for aspect, data in post.aspects_breakdown.items():
                aspects_breakdown[aspect] = AspectBreakdown(**data)

        keywords = None
        if post.keywords:
            keywords = [KeywordItem(**kw) for kw in post.keywords]

        post_detail = PostDetail(
            id=post.id,
            platform=post.platform,
            permalink=post.permalink,
            content_text=post.content_text,
            content_transcription=post.content_transcription,
            hashtags=post.hashtags,
            media_duration=post.media_duration,
            author_id=post.author_id,
            author_name=post.author_name,
            author_username=post.author_username,
            author_avatar_url=post.author_avatar_url,
            author_is_verified=post.author_is_verified,
            follower_count=post.follower_count,
            overall_sentiment=post.overall_sentiment,
            overall_sentiment_score=post.overall_sentiment_score,
            overall_confidence=post.overall_confidence,
            sentiment_probabilities=sentiment_probs,
            primary_intent=post.primary_intent,
            intent_confidence=post.intent_confidence,
            impact_score=post.impact_score,
            risk_level=post.risk_level,
            is_viral=post.is_viral,
            is_kol=post.is_kol,
            impact_breakdown=impact_breakdown,
            aspects_breakdown=aspects_breakdown,
            keywords=keywords,
            view_count=post.view_count,
            like_count=post.like_count,
            comment_count=post.comment_count,
            share_count=post.share_count,
            save_count=post.save_count,
            published_at=post.published_at,
            analyzed_at=post.analyzed_at,
            crawled_at=post.crawled_at,
            brand_name=post.brand_name,
            keyword=post.keyword,
            job_id=post.job_id,
            comments=comments,
            comments_total=len(comments),
        )

        return ApiResponse(success=True, data=post_detail)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_post_by_id: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
