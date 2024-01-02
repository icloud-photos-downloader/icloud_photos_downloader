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
COPY dist/icloudpd-ex-*.*.*-linux-arm32v6 icloudpd_ex

FROM runtime_${TARGETARCH}_${TARGETVARIANT:-none} as runtime
RUN apk add --no-cache tzdata
ENV TZ=UTC
WORKDIR /app
RUN chmod +x /app/icloudpd_ex
ENTRYPOINT ["/app/icloudpd_ex"]
