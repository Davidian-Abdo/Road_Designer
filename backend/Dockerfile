# Road Designer V 1.0 — FastAPI backend, Hugging Face Spaces (Docker SDK).
#
# HF Spaces' Docker SDK expects the container to listen on port 7860 by
# convention (override via the Space's `app_port` README front-matter if you
# need a different port). Build context is the REPO ROOT (not backend/), so
# that both road_designer/ (the engine) and samples/ (bundled sample files)
# can be copied in alongside backend/ itself:
#
#   docker build -f backend/Dockerfile -t road-designer-api .
#
# On HF Spaces, point the Space's Dockerfile path at "backend/Dockerfile"
# and leave the build context as the repo root (the default).

FROM python:3.12-slim

WORKDIR /app

# HF Spaces containers run as a non-root user by convention.
RUN useradd -m -u 1000 appuser

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY road_designer /app/road_designer
COPY samples /app/samples
COPY backend /app/backend

# Notice Files required by the Beamstack Community License (LICENSE section 3.4).
# They must be present in the build context: the repo root for a local build,
# and the assembled Space repo for Hugging Face (DEPLOYMENT.md Part A copies
# them in). If this COPY fails, that copy step was skipped.
COPY LICENSE NOTICE THIRD-PARTY-NOTICES.md /app/

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib

RUN mkdir -p /tmp/matplotlib && chown -R appuser:appuser /app /tmp/matplotlib

USER appuser

EXPOSE 7860

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "7860"]
