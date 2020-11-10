# This image is mainly used for development and testing

FROM python:3.9 as base

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base as test

RUN mkdir Photos
COPY requirements*.txt .
COPY scripts/install_deps scripts/install_deps
RUN scripts/install_deps
COPY . .
ENV TZ="America/Los_Angeles"
RUN scripts/test
RUN scripts/lint

FROM base as runtime

COPY . .
RUN python setup.py install

# copy from test to ensure test stage runs before runtime stage in buildx
COPY --from=test /app/.coverage .
