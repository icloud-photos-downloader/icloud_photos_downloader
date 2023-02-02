FROM python:3.11-alpine3.17 as build

WORKDIR /app

ENV TZ="America/Los_Angeles"

RUN set -xe \
  && apk update \
  && apk add git curl binutils gcc libc-dev libffi-dev cargo zlib-dev openssl-dev

COPY . .

RUN pip3 install -r requirements-pip.txt -r requirements.txt -r requirements-dev.txt

RUN pyinstaller -y --collect-all keyrings.alt --hidden-import pkgutil icloudpd.py icloud.py
RUN pyinstaller -y --collect-all keyrings.alt --hidden-import pkgutil icloud.py
RUN cp dist/icloud/icloud dist/icloudpd/

FROM alpine:3.17 as runtime

WORKDIR /app

COPY --from=build /app/dist/icloudpd .

RUN set -xe \
  && ln -s /app/icloudpd /usr/local/bin/icloudpd \
  && ln -s /app/icloud /usr/local/bin/icloud 
