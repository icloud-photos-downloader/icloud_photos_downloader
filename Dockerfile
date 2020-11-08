# This image is mainly used for development and testing

FROM python:3.9 as base

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base as test

RUN mkdir Photos
COPY requirements-test.txt .
RUN pip install -r requirements-test.txt
COPY . .
RUN py.test --cov=icloudpd --timeout=3 --cov-report term-missing
RUN pylint icloudpd

FROM base as runtime

COPY . .
RUN python setup.py install

# copy from test to ensure test stage runs before runtime stage in buildx
COPY --from=test /app/.coverage .
