"""
Celery Application Configuration

Configures Celery with Redis broker and backend.
Defines two queues:
- audio_processing: High-concurrency queue for audio analysis tasks
- notifications: Lower-concurrency queue for sending alerts
"""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Redis configuration from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "vocalvitals",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["services.analyze_tasks"],  # Will include task modules
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Result expiration (1 hour)
    result_expires=3600,
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Rate limiting
    worker_prefetch_multiplier=4,
    
    # Retry configuration
    task_default_retry_delay=30,
    task_max_retries=3,
    
    # Queues
    task_queues={
        "audio_processing": {
            "exchange": "audio_processing",
            "routing_key": "audio.#",
        },
        "notifications": {
            "exchange": "notifications",
            "routing_key": "notify.#",
        },
    },
    
    # Default queue
    task_default_queue="audio_processing",
    
    # Task routes
    task_routes={
        "services.analyze_tasks.analyze_audio_chunk": {"queue": "audio_processing"},
        "services.analyze_tasks.send_caregiver_notification": {"queue": "notifications"},
        "services.analyze_tasks.cleanup_old_audio": {"queue": "audio_processing"},
    },
    
    # Beat schedule (periodic tasks)
    beat_schedule={
        "cleanup-old-s3-audio": {
            "task": "services.analyze_tasks.cleanup_old_audio",
            "schedule": 86400.0,  # Daily
        },
    },
)


def get_celery_app() -> Celery:
    """Get the configured Celery application."""
    return celery_app


# For running worker: celery -A services.celery_app worker -Q audio_processing --concurrency=4
# For running beat: celery -A services.celery_app beat
# For flower monitoring: celery -A services.celery_app flower --port=5555
