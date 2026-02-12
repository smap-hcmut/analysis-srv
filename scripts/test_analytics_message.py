"""Test script to send analytics message to RabbitMQ."""

import asyncio
import json
from datetime import datetime
import aio_pika


async def send_test_message():
    """Send a test message to analytics queue."""
    
    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust(
        "amqp://admin:21042004@172.16.21.206:5672/"
    )
    
    async with connection:
        channel = await connection.channel()
        
        # Declare exchange
        exchange = await channel.declare_exchange(
            "smap.events",
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        
        # Create test message
        test_message = {
            "event_id": "test-001",
            "event_type": "data.collected",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_id": "550e8400-e29b-41d4-a716-446655440000-test",
                "batch_index": 1,
                "platform": "tiktok",
                "task_type": "keyword_search",
                "brand_name": "Toyota",
                "keyword": "xe ô tô",
                
                # Post data (inline)
                "meta": {
                    "id": "test-post-001",
                    "platform": "tiktok",
                    "permalink": "https://tiktok.com/@user/video/123",
                    "published_at": "2024-02-10T10:00:00Z",
                },
                "content": {
                    "text": "Xe Toyota Camry 2024 rất đẹp và tiết kiệm nhiên liệu. Tôi rất hài lòng với chiếc xe này!",
                    "description": "Review xe Toyota Camry",
                    "hashtags": ["toyota", "camry", "xe", "review"],
                },
                "interaction": {
                    "views": 15000,
                    "likes": 1200,
                    "comments_count": 45,
                    "shares": 30,
                    "saves": 20,
                },
                "author": {
                    "id": "user123",
                    "name": "Nguyễn Văn A",
                    "username": "@nguyenvana",
                    "followers": 50000,
                    "is_verified": True,
                    "avatar_url": "https://example.com/avatar.jpg",
                },
                "comments": [],
            }
        }
        
        # Send message
        print("📤 Sending test message to RabbitMQ...")
        print(f"Exchange: smap.events")
        print(f"Routing Key: data.collected")
        print(f"\nMessage Preview:")
        print(f"  Event ID: {test_message['event_id']}")
        print(f"  Post ID: {test_message['payload']['meta']['id']}")
        print(f"  Platform: {test_message['payload']['platform']}")
        print(f"  Text: {test_message['payload']['content']['text'][:50]}...")
        
        message_body = json.dumps(test_message, ensure_ascii=False)
        
        await exchange.publish(
            aio_pika.Message(
                body=message_body.encode(),
                content_type="application/json",
            ),
            routing_key="data.collected",
        )
        
        print("\n✅ Message sent successfully!")
        print("⏳ Check consumer logs for processing...")


if __name__ == "__main__":
    asyncio.run(send_test_message())
