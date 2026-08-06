FROM python:3.12-slim

WORKDIR /app

COPY process.py .

# Poll interval (seconds) — override at runtime via -e POLL_INTERVAL
ENV POLL_INTERVAL=300

ENTRYPOINT ["python", "process.py"]
CMD ["/input", "/output", "300"]
