# Two stages: build installs the pinned freeze file into a venv, runtime copies only the venv and the package.
# Never built by verify.sh (see docs/RUNBOOK.md for the owner path).
FROM python:3.11-slim AS build
WORKDIR /build
COPY requirements.freeze.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.freeze.txt

FROM python:3.11-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONPATH=/srv/src HF_HUB_OFFLINE=1
RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /opt/venv /opt/venv
WORKDIR /srv
COPY src ./src
COPY configs ./configs
COPY receipts ./receipts
USER app
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["python", "-c", "import ftlab"]
ENTRYPOINT ["python", "-m", "ftlab.cli"]
CMD ["audit"]
