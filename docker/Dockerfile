FROM alpine:latest

RUN set -xe && \
    apk add --update --no-cache python py-pip git && \
    pip2 install icloudpd && \
    adduser -D -h /home/user -u 1000 user && \
    rm -fr /var/cache/apk/*

USER user
