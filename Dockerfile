# The unattended run: `tft refresh` keeps a match store and a built page current under /data.
# The key comes from RIOT_API_KEY at run time and is never part of the image.

FROM python:3.15-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable --python /usr/local/bin/python

FROM python:3.15-slim
# A numeric user with a home of its own: the run writes only under /data, and a cluster may give
# it any other user id.
RUN useradd --uid 10001 --create-home --home-dir /home/tft tft && mkdir /data && chown 10001:10001 /data
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 TFT_STATE_DIR=/data
USER 10001
VOLUME /data
ENTRYPOINT ["tft"]
CMD ["refresh", "--out", "/data/site"]
