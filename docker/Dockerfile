FROM alpine:latest

RUN set -xe && \
    apk add --update --no-cache python py-pip git && \
    rm -rf /var/cache/apk/*
RUN pip2 install icloudpd==1.0.5
RUN adduser -D -h /home/user -u 1000 user
USER user
