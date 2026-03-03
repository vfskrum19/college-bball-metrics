# Dockerfile
# Builds the full Court Vision app: React frontend + Flask backend
#
# WHY A DOCKERFILE INSTEAD OF NIXPACKS:
#   Nixpacks auto-detects languages but gets confused when a project
#   has both package.json (Node) and requirements.txt (Python).
#   A Dockerfile gives us explicit control over exactly what gets
#   installed and in what order - no guessing.
#
# BUILD STAGES:
#   Stage 1 (frontend-builder): Install Node, build React app to dist/
#   Stage 2 (final): Install Python, copy built frontend, run Flask
#
# Multi-stage builds keep the final image small - the Node runtime
# and node_modules are only needed to BUILD the frontend, not to
# RUN it. The final image only contains Python and the built assets.

# ============================================================
# STAGE 1: Build the React frontend
# ============================================================
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Copy package files first - Docker caches this layer
# so npm install only reruns when dependencies change
COPY frontend/package*.json ./
RUN npm install

# Copy source and build
COPY frontend/ ./
RUN npm run build
# Result: /app/frontend/dist/ contains the built React app


# ============================================================
# STAGE 2: Python backend + built frontend
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code (validators.py lives inside backend/)
COPY backend/ ./backend/

# Copy built React app from Stage 1
# Flask serves these static files directly
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Railway injects PORT at runtime - default to 8080 if not set
ENV PORT=8080
ENV FLASK_ENV=production

# Use shell form (not array form) so $PORT gets expanded at runtime
CMD python -m gunicorn "backend.app:create_app()" --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile -