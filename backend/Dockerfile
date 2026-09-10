# VoicePath backend -- container image for any host that wants one.
#
# Render does not need this: pick "Python 3" as the Language there and it uses
# the build and start commands instead. This exists for hosts that only take an
# image, and it deliberately matches the same slim dependency set.
#
# Nothing here installs torch. Embeddings run through the Hugging Face
# Inference API (EMBEDDING_PROVIDER=hf_api) against the same
# multilingual-e5-base the database was embedded with -- measured cosine 1.0000
# against the local model, so stored vectors stay valid. That drops the image
# from ~1.16GB to ~300MB, which is the difference between fitting a free tier
# and not.

FROM python:3.11-slim

RUN useradd -m -u 1000 user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# libgomp is OpenMP, which onnxruntime links against; the slim image does not
# carry it and the failure surfaces as an import error at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Owned by uid 1000 before the switch: fetch_voices writes models/piper in here
# during the build, and a root-owned WORKDIR makes that a permission error.
RUN mkdir -p /app && chown user:user /app
WORKDIR /app

USER user

COPY --chown=user requirements.txt requirements-deploy.txt ./
RUN pip install --no-cache-dir --user -r requirements-deploy.txt

COPY --chown=user . .

# Piper voices, ~182MB. Baked in so a cold start does not also download them.
RUN python -m app.scripts.fetch_voices

# Hosts that inject $PORT override this; 8000 is the local default.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
