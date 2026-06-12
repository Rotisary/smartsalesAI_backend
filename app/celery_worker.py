"""

Celery worker entrypoint — lives at the project root alongside main.py.

Start the worker (development):
  celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2

Start with a dedicated queue (production):
  celery -A celery_worker.celery_app worker \
      --loglevel=info \
      --concurrency=2 \
      --queues=knowledge \
      --hostname=knowledge-worker@%h

Flower monitoring (optional):
  celery -A celery_worker.celery_app flower --port=5555

The --concurrency flag controls how many documents are processed in parallel.
2 is a safe default — each job downloads from S3, calls Google's embedding API,
and writes to Postgres, so CPU is not the bottleneck.
Increase if you have network headroom and want faster throughput.
"""

from app.celery import celery_app