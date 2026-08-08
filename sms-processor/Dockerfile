FROM python:3.12-slim

WORKDIR /app

COPY process.py .

# Poll interval (seconds) — override at runtime via -e POLL_INTERVAL or docker-compose command
ENV POLL_INTERVAL=300

CMD ["python", "process.py", "/input", "/output", "300"]
