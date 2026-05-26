FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN python -m pip install --upgrade pip \
    && pip install .

EXPOSE 8000

CMD ["python", "-m", "atlassian_mcp_server", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
