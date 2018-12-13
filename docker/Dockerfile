FROM alpine:latest

RUN set -xe && \
    apk add --no-cache python3 && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache

ARG ICLOUDPD_VERSION
RUN set -xe \
  && pip install icloudpd==${ICLOUDPD_VERSION} \
  && icloudpd --version \
  && icloud -h | head -n1

RUN adduser -D -h /home/user -u 1000 user
USER user
