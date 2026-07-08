from celery import Celery

from ..config import settings

celery = Celery("structai", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.task_track_started = True
celery.conf.imports = ["app.workers.reconstruction"]
