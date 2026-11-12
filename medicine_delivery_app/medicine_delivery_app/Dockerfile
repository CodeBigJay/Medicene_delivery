# Backend server image.  Build: docker build -t doorstep-api .   Run: see DEPLOY.md
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY models.py storage.py notifier.py ./
COPY backend backend
ENV DOORSTEP_ENV=production DOORSTEP_DB=/data/doorstep.db PORT=8000
VOLUME /data
EXPOSE 8000
# One worker + threads: the server keeps its data rules in one process (see DEPLOY.md).
CMD ["sh", "-c", "gunicorn -w 1 --threads 8 -b 0.0.0.0:${PORT} backend.app:app"]
