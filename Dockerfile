# Multi-stage Dockerfile for Question Bank Generator
# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

# Ensure npm is up-to-date for modern Vite builds
RUN npm i -g npm@10

WORKDIR /app/frontend

# Copy frontend package files
COPY app/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY app/ ./

# Optionally skip frontend build when building backend-only images
ARG SKIP_FRONTEND_BUILD=false
RUN if [ "$SKIP_FRONTEND_BUILD" = "false" ]; then npm run build; else echo "Skipping frontend build (SKIP_FRONTEND_BUILD=true)"; fi ; \
    mkdir -p /app/frontend/dist

# Stage 2: Setup Python backend and serve frontend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create directory for database
RUN mkdir -p /app/data

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///./data/question_bank.db
ENV HOST=0.0.0.0
ENV PORT=8000

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
