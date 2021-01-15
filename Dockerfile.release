FROM alpine:latest

RUN set -xe && \
    apk add --no-cache python3 tzdata && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime

ARG ICLOUDPD_VERSION
COPY dist/* /tmp
RUN set -xe \
  && pip install wheel==0.35.1 \
  && pip install /tmp/icloudpd-${ICLOUDPD_VERSION}-py2.py3-none-any.whl \
  && icloudpd --version \
  && icloud -h | head -n1
