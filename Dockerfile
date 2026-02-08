FROM python:3.12-slim AS builder

RUN pip install poetry==2.1.1

WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root --only main

COPY src/ src/
RUN poetry install --only main

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY --from=builder /app/src src

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 80

CMD ["uvicorn", "meter_emulator.main:app", "--host", "0.0.0.0", "--port", "80"]
