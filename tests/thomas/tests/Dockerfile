FROM thomas-portability-runtime:local
USER root
COPY *.whl /wheels/
RUN python3 -m venv /tmp/fetch \
    && for wheel in /wheels/portfolio_advisory-*.whl; do /tmp/fetch/bin/pip download --only-binary=:all: --dest /wheels "$wheel" || exit 1; done \
    && rm -rf /tmp/fetch
ENV PIP_NO_INDEX=1 PIP_FIND_LINKS=/wheels
USER node
