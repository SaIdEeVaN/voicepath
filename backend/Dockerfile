# VoicePath backend -- Hugging Face Docker Space, free CPU tier.
#
# Two things here are load-bearing and easy to get wrong:
#
# 1. Torch is installed from the CPU index FIRST. Left to itself, pip resolves
#    sentence-transformers' torch dependency to the CUDA build -- several GB of
#    NVIDIA runtime on a tier that has no GPU, which overruns the image budget
#    for no benefit.
#
# 2. Models are baked in at build time rather than fetched on first request.
#    Free Spaces sleep when idle, and a cold start that also has to download
#    1.1GB of embedding weights is a request that times out rather than a
#    request that is merely slow.

FROM python:3.11-slim

# Spaces run the container as uid 1000. Writing the model cache anywhere else
# fails at runtime with a permission error that reads like a network problem.
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1

# libgomp is OpenMP, which torch and onnxruntime both link against; the slim
# image does not carry it and the failure surfaces as an import error.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Owned by uid 1000 before the switch: fetch_voices writes models/piper in here
# during the build, and a root-owned WORKDIR makes that a permission error.
RUN mkdir -p /app && chown user:user /app
WORKDIR /app

USER user

COPY --chown=user requirements.txt requirements-ml.txt ./

# CPU wheel explicitly. See note 1 above.
RUN pip install --no-cache-dir --user torch==2.14.0 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --user -r requirements-ml.txt

COPY --chown=user . .

# Bake the embedding model and the Piper voices into the image. See note 2.
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('intfloat/multilingual-e5-base')" \
    && python -m app.scripts.fetch_voices

# Must match `app_port` in the Space README front matter.
EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
