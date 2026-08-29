FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286 AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY --from=builder /install /usr/local
RUN groupadd --gid 65532 robot && \
    useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin robot
USER 65532:65532
WORKDIR /app
EXPOSE 8080
CMD ["uvicorn", "physical_robot.api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
