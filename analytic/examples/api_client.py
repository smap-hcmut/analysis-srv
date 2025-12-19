"""
Analytics API Client Examples
Demonstrates how to use the Analytics Engine REST API.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import httpx


class AnalyticsAPIClient:
    """Client for Analytics Engine REST API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize API client."""
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient()
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    async def health_check(self) -> Dict:
        """Check API health status."""
        response = await self.client.get(f"{self.base_url}/health/detailed")
        response.raise_for_status()
        return response.json()
    
    async def get_posts(
        self,
        project_id: str,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None,
        platform: Optional[str] = None,
        sentiment: Optional[str] = None,
        is_viral: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "analyzed_at",
        sort_order: str = "desc"
    ) -> Dict:
        """Get paginated posts with filtering."""
        params = {
            "project_id": project_id,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
        
        # Add optional filters
        if brand_name:
            params["brand_name"] = brand_name
        if keyword:
            params["keyword"] = keyword
        if platform:
            params["platform"] = platform
        if sentiment:
            params["sentiment"] = sentiment
        if is_viral is not None:
            params["is_viral"] = is_viral
        
        response = await self.client.get(
            f"{self.base_url}/posts",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_post_detail(self, post_id: str) -> Dict:
        """Get complete post details by ID."""
        response = await self.client.get(
            f"{self.base_url}/posts/{post_id}"
        )
        response.raise_for_status()
        return response.json()
    
    async def get_summary(
        self,
        project_id: str,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict:
        """Get summary statistics."""
        params = {"project_id": project_id}
        
        if brand_name:
            params["brand_name"] = brand_name
        if keyword:
            params["keyword"] = keyword
        if from_date:
            params["from_date"] = from_date.isoformat()
        if to_date:
            params["to_date"] = to_date.isoformat()
        
        response = await self.client.get(
            f"{self.base_url}/summary",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_trends(
        self,
        project_id: str,
        from_date: datetime,
        to_date: datetime,
        granularity: str = "day",
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> Dict:
        """Get time-series trends data."""
        params = {
            "project_id": project_id,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "granularity": granularity
        }
        
        if brand_name:
            params["brand_name"] = brand_name
        if keyword:
            params["keyword"] = keyword
        
        response = await self.client.get(
            f"{self.base_url}/trends",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_top_keywords(
        self,
        project_id: str,
        limit: int = 20,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> Dict:
        """Get top keywords with sentiment."""
        params = {
            "project_id": project_id,
            "limit": limit
        }
        
        if brand_name:
            params["brand_name"] = brand_name
        if keyword:
            params["keyword"] = keyword
        
        response = await self.client.get(
            f"{self.base_url}/top-keywords",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_alerts(
        self,
        project_id: str,
        limit: int = 10,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> Dict:
        """Get posts requiring attention."""
        params = {
            "project_id": project_id,
            "limit": limit
        }
        
        if brand_name:
            params["brand_name"] = brand_name
        if keyword:
            params["keyword"] = keyword
        
        response = await self.client.get(
            f"{self.base_url}/alerts",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_crawl_errors(
        self,
        project_id: str,
        job_id: Optional[str] = None,
        error_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict:
        """Get crawl errors."""
        params = {
            "project_id": project_id,
            "page": page,
            "page_size": page_size
        }
        
        if job_id:
            params["job_id"] = job_id
        if error_code:
            params["error_code"] = error_code
        
        response = await self.client.get(
            f"{self.base_url}/errors",
            params=params
        )
        response.raise_for_status()
        return response.json()


async def main_example():
    """Example usage of the Analytics API client."""
    # Example project ID (replace with actual project ID)
    PROJECT_ID = "12345678-1234-5678-1234-567812345678"
    
    # Initialize client
    client = AnalyticsAPIClient("http://localhost:8000")
    
    try:
        print("🔍 Analytics API Client Examples")
        print("=" * 50)
        
        # 1. Health Check
        print("\n1. Health Check:")
        health = await client.health_check()
        print(f"   Status: {health.get('status', 'unknown')}")
        print(f"   Version: {health.get('version', 'unknown')}")
        
        # 2. Get Posts (basic)
        print("\n2. Get Recent Posts:")
        posts_response = await client.get_posts(
            project_id=PROJECT_ID,
            page=1,
            page_size=5
        )
        if posts_response["success"]:
            posts = posts_response["data"]
            pagination = posts_response["pagination"]
            print(f"   Found {pagination['total_items']} total posts")
            print(f"   Showing {len(posts)} posts on page {pagination['page']}")
            
            for post in posts[:2]:  # Show first 2
                print(f"   - {post['id']}: {post['platform']} post")
                print(f"     Sentiment: {post['overall_sentiment']} ({post['overall_sentiment_score']:.2f})")
                print(f"     Impact: {post['impact_score']:.1f}, Risk: {post['risk_level']}")
        
        # 3. Get Posts with Filters  
        print("\n3. Get Viral TikTok Posts:")
        viral_posts = await client.get_posts(
            project_id=PROJECT_ID,
            platform="tiktok",
            is_viral=True,
            sentiment="POSITIVE",
            page_size=3
        )
        if viral_posts["success"]:
            posts = viral_posts["data"]
            print(f"   Found {len(posts)} viral positive TikTok posts")
        
        # 4. Get Post Detail
        if posts_response["success"] and posts_response["data"]:
            first_post_id = posts_response["data"][0]["id"]
            print(f"\n4. Get Post Detail ({first_post_id}):")
            
            detail_response = await client.get_post_detail(first_post_id)
            if detail_response["success"]:
                post = detail_response["data"]
                print(f"   Content: {post.get('content_text', 'N/A')[:100]}...")
                print(f"   Author: {post.get('author_name', 'Unknown')} (@{post.get('author_username', 'unknown')})")
                print(f"   Metrics: {post['view_count']} views, {post['like_count']} likes")
                print(f"   Comments: {post['comments_total']} total")
                
                if post.get('aspects_breakdown'):
                    print("   Aspect Analysis:")
                    for aspect, data in post['aspects_breakdown'].items():
                        print(f"     - {aspect}: {data['sentiment']} ({data['score']:.2f})")
        
        # 5. Summary Statistics
        print("\n5. Summary Statistics:")
        summary_response = await client.get_summary(project_id=PROJECT_ID)
        if summary_response["success"]:
            summary = summary_response["data"]
            print(f"   Total Posts: {summary['total_posts']}")
            print(f"   Total Comments: {summary['total_comments']}")
            print(f"   Avg Sentiment: {summary['avg_sentiment_score']:.2f}")
            print(f"   Viral Posts: {summary['viral_count']}")
            print(f"   Platform Distribution: {summary['platform_distribution']}")
        
        # 6. Trends (last 7 days)
        print("\n6. Daily Trends (Last 7 Days):")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        trends_response = await client.get_trends(
            project_id=PROJECT_ID,
            from_date=start_date,
            to_date=end_date,
            granularity="day"
        )
        if trends_response["success"]:
            trends = trends_response["data"]["items"]
            print(f"   Showing {len(trends)} days of trends:")
            for trend in trends[-3:]:  # Last 3 days
                print(f"   - {trend['date']}: {trend['post_count']} posts, "
                      f"avg sentiment {trend['avg_sentiment_score']:.2f}")
        
        # 7. Top Keywords
        print("\n7. Top Keywords:")
        keywords_response = await client.get_top_keywords(
            project_id=PROJECT_ID,
            limit=5
        )
        if keywords_response["success"]:
            keywords = keywords_response["data"]["keywords"]
            print(f"   Top {len(keywords)} keywords:")
            for kw in keywords:
                print(f"   - '{kw['keyword']}': {kw['count']} mentions, "
                      f"sentiment {kw['avg_sentiment_score']:.2f} ({kw['aspect']})")
        
        # 8. Alerts
        print("\n8. Critical Alerts:")
        alerts_response = await client.get_alerts(
            project_id=PROJECT_ID,
            limit=3
        )
        if alerts_response["success"]:
            alerts = alerts_response["data"]
            print(f"   Summary: {alerts['summary']['critical_count']} critical, "
                  f"{alerts['summary']['viral_count']} viral, "
                  f"{alerts['summary']['crisis_count']} crisis")
            
            if alerts["critical_posts"]:
                print("   Critical Posts:")
                for post in alerts["critical_posts"][:2]:
                    print(f"   - {post['id']}: Impact {post['impact_score']:.1f}")
        
        # 9. Crawl Errors
        print("\n9. Recent Crawl Errors:")
        errors_response = await client.get_crawl_errors(
            project_id=PROJECT_ID,
            page_size=3
        )
        if errors_response["success"]:
            errors = errors_response["data"]
            pagination = errors_response["pagination"]
            print(f"   {pagination['total_items']} total errors, showing {len(errors)}")
            for error in errors:
                print(f"   - {error['error_code']}: {error['content_id']} ({error['platform']})")
        
        print("\n✅ All API examples completed successfully!")
        
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    """
    Run this example:
    
    1. Start the API service:
       PYTHONPATH=. uv run command/api/main.py
    
    2. Run this example:
       PYTHONPATH=. uv run python examples/api_client.py
    """
    print("Analytics API Client Examples")
    print("Make sure the API service is running on http://localhost:8000")
    print("Starting in 3 seconds...")
    
    import time
    time.sleep(3)
    
    asyncio.run(main_example())