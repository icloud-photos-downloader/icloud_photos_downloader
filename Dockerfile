FROM alpine:3.18 AS runtime_amd64_none
ENV MUSL_LOCPATH="/usr/share/i18n/locales/musl"
RUN apk update && apk add --no-cache tzdata musl-locales musl-locales-lang
WORKDIR /app
COPY dist/icloud-*.*.*-linux-musl-amd64 icloud
COPY dist/icloudpd-*.*.*-linux-musl-amd64 icloudpd

FROM alpine:3.18 AS runtime_arm64_none
ENV MUSL_LOCPATH="/usr/share/i18n/locales/musl"
RUN apk update && apk add --no-cache tzdata musl-locales musl-locales-lang
WORKDIR /app
COPY dist/icloud-*.*.*-linux-musl-arm64 icloud
COPY dist/icloudpd-*.*.*-linux-musl-arm64 icloudpd

FROM alpine:3.18 AS runtime_arm_v7
ENV MUSL_LOCPATH="/usr/share/i18n/locales/musl"
RUN apk update && apk add --no-cache tzdata musl-locales musl-locales-lang
WORKDIR /app
COPY dist/icloud-*.*.*-linux-musl-arm32v7 icloud
COPY dist/icloudpd-*.*.*-linux-musl-arm32v7 icloudpd

FROM runtime_${TARGETARCH}_${TARGETVARIANT:-none} AS runtime
ENV TZ=UTC
EXPOSE 8080
WORKDIR /app
RUN chmod +x /app/icloud /app/icloudpd

# Use a shell script to allow command selection and environment variable conversion
COPY entrypoint-wrapper.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Default entrypoint allows command selection and env var conversion
ENTRYPOINT ["/app/entrypoint.sh"]
