FROM python:3.12-alpine3.18 as build

WORKDIR /app

ENV CARGO_NET_GIT_FETCH_WITH_CLI=true

RUN set -xe \
  && apk update \
  && apk add git curl binutils gcc libc-dev libffi-dev cargo zlib-dev openssl-dev

COPY pyproject.toml .
COPY src src

RUN pip3 install -e .[dev]

RUN pyinstaller -y --collect-all keyrings.alt --hidden-import pkgutil --collect-all tzdata --onefile src/starters/icloudpd_ex.py


FROM alpine:3.18 as runtime_amd64_none
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-amd64 icloudpd_ex

FROM alpine:3.18 as runtime_386_none
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-386 icloudpd_ex

FROM alpine:3.18 as runtime_arm64_none
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-arm64 icloudpd_ex

FROM alpine:3.18 as runtime_arm_v7
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-arm32v7 icloudpd_ex

FROM alpine:3.18 as runtime_arm_v6
WORKDIR /app
COPY --from=build /app/dist/icloudpd_ex .

FROM alpine:3.18 as runtime_arm_v5
WORKDIR /app
COPY --from=build /app/dist/icloudpd_ex .

FROM runtime_${TARGETARCH}_${TARGETVARIANT:-none} as runtime
RUN apk add --no-cache tzdata
ENV TZ=UTC
WORKDIR /app
RUN chmod +x /app/icloudpd_ex
ENTRYPOINT ["/app/icloudpd_ex"]
