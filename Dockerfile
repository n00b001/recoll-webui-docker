FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common=0.96.24.32.22 \
    && add-apt-repository universe \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python=2.7.15~rc1-1 \
        recoll=1.23.7-1 \
        python-recoll=1.23.7-1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /recoll-webui

COPY recoll-webui /recoll-webui

EXPOSE 8080

CMD ["python", "/recoll-webui/webui-standalone.py", "-a", "0.0.0.0"]
