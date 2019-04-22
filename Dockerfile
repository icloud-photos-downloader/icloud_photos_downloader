FROM alpine:20190408

RUN set -xe && \
    apk add --no-cache python3 && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache

ADD http://www.imagemagick.org/download/ImageMagick.tar.gz /tmp/

ADD ./ /tmp/

# Configure HEIC and icloudpd
RUN set -xe && \ 
  echo "http://dl-cdn.alpinelinux.org/alpine/edge/testing/" >> /etc/apk/repositories && \
  apk add --no-cache x265-dev x265-libs build-base jpeg-dev libheif-dev && \
  cd /tmp/ && \
  tar -xvf ImageMagick.tar.gz && \
  cd ImageMagick-7.0.* && \
  ./configure && \
  make -j 4 && \
  make install && \
  pip install /tmp  && \
  icloudpd --version && \
  icloud -h | head -n1
