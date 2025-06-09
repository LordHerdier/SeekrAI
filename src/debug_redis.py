#!/usr/bin/env python3
"""
Debug script to test Redis connection in Docker environment
"""
import os
import sys
import logging
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import get_config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_redis_connection():
    """Test Redis connection"""
    try:
        import redis
        config = get_config()
        redis_url = config.get('cache.redis_url', 'redis://localhost:6379/0')
        
        logger.info(f"Attempting to connect to Redis at: {redis_url}")
        
        client = redis.from_url(redis_url, decode_responses=True)
        
        # Test basic operations
        client.ping()
        logger.info("✓ Redis ping successful")
        
        # Test set/get
        test_key = "test_key_12345"
        test_value = "test_value_12345"
        
        client.setex(test_key, 10, test_value)
        logger.info("✓ Redis set successful")
        
        retrieved_value = client.get(test_key)
        if retrieved_value == test_value:
            logger.info("✓ Redis get successful")
        else:
            logger.error(f"✗ Redis get failed. Expected: {test_value}, Got: {retrieved_value}")
        
        # Clean up
        client.delete(test_key)
        logger.info("✓ Redis delete successful")
        
        logger.info("🎉 All Redis operations successful!")
        return True
        
    except ImportError:
        logger.error("✗ Redis module not available")
        return False
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        return False

def test_environment():
    """Test environment variables"""
    logger.info("=== Environment Check ===")
    
    env_vars = [
        'REDIS_URL',
        'FLASK_ENV',
        'SECRET_KEY',
        'OPENAI_API_KEY'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Don't log sensitive values in full
            if 'KEY' in var or 'SECRET' in var:
                display_value = f"{value[:8]}..." if len(value) > 8 else "***"
            else:
                display_value = value
            logger.info(f"✓ {var}: {display_value}")
        else:
            logger.warning(f"✗ {var}: Not set")

if __name__ == "__main__":
    logger.info("=== SeekrAI Redis Debug Tool ===")
    
    test_environment()
    
    logger.info("\n=== Redis Connection Check ===")
    success = test_redis_connection()
    
    if success:
        logger.info("\n🎉 Redis setup is working correctly!")
        sys.exit(0)
    else:
        logger.error("\n❌ Redis setup has issues.")
        sys.exit(1) 