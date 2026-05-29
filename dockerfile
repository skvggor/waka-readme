FROM docker.io/python:3.14-slim

ENV PATH="${PATH}:/root/.local/bin" \
    # python
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PYTHONDONTWRITEBYTECODE=1 \
    # pip
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=100

# copy project files
COPY --chown=root:root pyproject.toml main.py /app/

# install dependencies
RUN python -m pip install /app/

# execute program
CMD ["python", "/app/main.py"]
