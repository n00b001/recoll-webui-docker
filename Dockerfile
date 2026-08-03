FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository universe \
    && apt-get update \
    && apt-get install -y \
        python \
        recoll \
        python-recoll \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /recoll-webui

COPY recoll-webui /recoll-webui

EXPOSE 8080

CMD ["python", "/recoll-webui/webui-standalone.py", "-a", "0.0.0.0"]
