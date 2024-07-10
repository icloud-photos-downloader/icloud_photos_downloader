FROM ubuntu:24.04 as runtime_amd64_none
RUN apt-get update && apt-get install -y tzdata locales-all
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-amd64 icloudpd_ex

# focal is the last ubuntu for 386
FROM i386/ubuntu:focal as runtime_386_none
RUN apt-get update && apt-get install -y tzdata locales-all
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-386 icloudpd_ex

FROM ubuntu:24.04 as runtime_arm64_none
RUN apt-get update && apt-get install -y tzdata locales-all
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-arm64 icloudpd_ex

FROM ubuntu:24.04 as runtime_arm_v7
RUN apt-get update && apt-get install -y tzdata locales-all
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-arm32v7 icloudpd_ex

FROM alpine:3.18 as runtime_arm_v6
ENV MUSL_LOCPATH="/usr/share/i18n/locales/musl"
RUN apk update && apk add --no-cache tzdata must-locale must-locale-lang
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-arm32v6 icloudpd_ex

FROM runtime_${TARGETARCH}_${TARGETVARIANT:-none} as runtime
ENV TZ=UTC
EXPOSE 8080
WORKDIR /app
RUN chmod +x /app/icloudpd_ex
ENTRYPOINT ["/app/icloudpd_ex"]
