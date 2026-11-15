FROM docker.io/library/python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace

COPY requirements-test.lock ./requirements-test.lock
RUN python -m pip install --no-cache-dir --require-hashes \
    -r requirements-test.lock

COPY . .

CMD ["sh", "tests/test.sh"]
