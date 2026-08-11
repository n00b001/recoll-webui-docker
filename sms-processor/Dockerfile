FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends rsync && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create template and generated directories
RUN mkdir -p /templates /generated

COPY process.py .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "process.py", "/input", "/output", "300"]
