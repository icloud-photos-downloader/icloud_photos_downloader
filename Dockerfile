FROM python:3.11-alpine3.17 as build

WORKDIR /app

ENV TZ="America/Los_Angeles"

ENV CARGO_NET_GIT_FETCH_WITH_CLI=true

RUN set -xe \
  && apk update \
  && apk add git curl binutils gcc libc-dev libffi-dev cargo zlib-dev openssl-dev

COPY . .

RUN pip3 install -e .[dev]

RUN pyinstaller -y --collect-all keyrings.alt --hidden-import pkgutil --collect-all tzdata src/exec.py

FROM alpine:3.17 as runtime

WORKDIR /app

ENV TZ="America/Los_Angeles"

COPY --from=build /app/dist/exec .

ENTRYPOINT ["/app/exec"]

# RUN set -xe \
#   && ln -s /app/icloudpd /usr/local/bin/icloudpd \
#   && ln -s /app/icloud /usr/local/bin/icloud 
