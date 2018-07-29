FROM alpine:latest

RUN set -xe && \
    apk add --update --no-cache python py-pip git && \
    git clone https://github.com/ndbroadbent/icloud_photos_downloader.git && \
    cd icloud_photos_downloader && \
    pip2 install -r requirements.txt && \
    adduser -D -h /home/user -u 1000 user && \
    rm -fr /var/cache/apk/*

USER user

WORKDIR /icloud_photos_downloader
