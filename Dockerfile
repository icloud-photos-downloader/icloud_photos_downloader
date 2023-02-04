FROM python:3.11-alpine3.17 as build

WORKDIR /app

ENV TZ="America/Los_Angeles"

ENV CARGO_NET_GIT_FETCH_WITH_CLI=true

RUN set -xe \
  && apk update \
  && apk add git curl binutils gcc libc-dev libffi-dev cargo zlib-dev openssl-dev

COPY . .

RUN pip3 install -r requirements-pip.txt -r requirements.txt -r requirements-dev.txt

RUN pyinstaller -y --collect-all keyrings.alt --hidden-import pkgutil --collect-all tzdata icloudpd.py icloud.py
RUN pyinstaller -y --collect-all keyrings.alt --hidden-import pkgutil --collect-all tzdata icloud.py
RUN cp dist/icloud/icloud dist/icloudpd/

FROM alpine:3.17 as runtime

WORKDIR /app

ENV TZ="America/Los_Angeles"

COPY --from=build /app/dist/icloudpd .

RUN set -xe \
  && ln -s /app/icloudpd /usr/local/bin/icloudpd \
  && ln -s /app/icloud /usr/local/bin/icloud 
