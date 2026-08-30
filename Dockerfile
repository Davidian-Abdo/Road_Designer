# Road Designer V 1.0 — FastAPI backend container.
#
# Portable across container hosts. Build context is the REPO ROOT (this file
# lives at the root) so the engine (road_designer/) and sample data (samples/)
# can be copied in alongside backend/:
#
#   docker build -t road-designer-api .
#   docker run --rm -p 8000:7860 road-designer-api        # → http://localhost:8000/health
#
# Port: the app listens on $PORT if set, else 7860.
#   - Google Cloud Run injects PORT (8080) automatically — nothing to configure.
#   - Hugging Face Docker Spaces set no PORT, so it falls back to 7860, which is
#     exactly what HF expects (no app_port override needed).
#   - Render / Koyeb / Fly inject their own PORT — also automatic.
#
# Cloud Run note: this backend runs design jobs in a background thread after the
# HTTP response is sent, so deploy it with CPU always allocated
# (`gcloud run deploy --no-cpu-throttling`), otherwise the background work is
# throttled once the request returns. See DEPLOYMENT.md Part A.

FROM python:3.12-slim

WORKDIR /app

# Run as a non-root user (required on HF Spaces, good practice everywhere).
RUN useradd -m -u 1000 appuser

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY road_designer /app/road_designer
COPY samples /app/samples
COPY backend /app/backend

# Notice Files required by the Beamstack Community License (LICENSE section 3.4).
# Must be present in the build context (the repo root). If this COPY fails, the
# files are missing from the context.
COPY LICENSE NOTICE THIRD-PARTY-NOTICES.md /app/

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib

RUN mkdir -p /tmp/matplotlib && chown -R appuser:appuser /app /tmp/matplotlib

USER appuser

# Informational only; the real port is $PORT (default 7860) at runtime.
EXPOSE 7860

CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
