# syntax=docker/dockerfile:1.7

# ===============================
# Stage 1: Build frontend assets
# ===============================
FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build


# ==============================================
# Stage 2: Runtime backend (FastAPI + Playwright)
# ==============================================
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy backend source
COPY backend/ /app/backend/

# Copy built frontend to be served by backend/main.py
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

# Runtime writable dirs
RUN mkdir -p /app/app_data /app/downloads_contracts

EXPOSE 8000

WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
