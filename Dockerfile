# Stage 1: Build stage
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
RUN useradd --no-create-home --shell /bin/false appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app.py .
USER appuser
EXPOSE 8080
ENV POD_NAME=""
CMD ["python", "app.py"]
