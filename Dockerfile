FROM alpine:3.18 AS runtime_amd64_none
ENV MUSL_LOCPATH="/usr/share/i18n/locales/musl"
RUN apk update && apk add --no-cache tzdata musl-locales musl-locales-lang curl
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-musl-amd64 icloudpd_ex

FROM alpine:3.18 AS runtime_arm64_none
ENV MUSL_LOCPATH="/usr/share/i18n/locales/musl"
RUN apk update && apk add --no-cache tzdata musl-locales musl-locales-lang curl
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-musl-arm64 icloudpd_ex

FROM alpine:3.18 AS runtime_arm_v7
ENV MUSL_LOCPATH="/usr/share/i18n/locales/musl"
RUN apk update && apk add --no-cache tzdata musl-locales musl-locales-lang curl
WORKDIR /app
COPY dist/icloudpd-ex-*.*.*-linux-musl-arm32v7 icloudpd_ex

FROM runtime_${TARGETARCH}_${TARGETVARIANT:-none} AS runtime
ENV TZ=UTC
EXPOSE 8080
WORKDIR /app
RUN chmod +x /app/icloudpd_ex
ENTRYPOINT ["/app/icloudpd_ex"]
