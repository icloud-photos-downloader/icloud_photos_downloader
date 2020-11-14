# This image is mainly used for development and testing

FROM python:3.9 as base

WORKDIR /app
# explicit requirements because runtime does not need ALL dependencies
COPY requirements-pip.txt .
COPY requirements.txt .
RUN pip3 install -r requirements-pip.txt
RUN pip3 install --use-feature=2020-resolver -r requirements.txt

FROM base as test

RUN apt-get update && apt-get install -y dos2unix
RUN mkdir Photos
COPY requirements*.txt .
COPY scripts/install_deps scripts/install_deps
RUN dos2unix scripts/install_deps
RUN scripts/install_deps
COPY . .
RUN dos2unix scripts/*
ENV TZ="America/Los_Angeles"
RUN scripts/test
RUN scripts/lint

FROM base as runtime

COPY . .
RUN python setup.py install

# copy from test to ensure test stage runs before runtime stage in buildx
COPY --from=test /app/.coverage .
