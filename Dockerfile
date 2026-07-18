FROM scratch

ARG VERSION=dev
ARG REVISION=unknown
ARG CREATED=unknown
ARG SOURCE_STATE=unknown
ARG BINARY_SHA256=unknown

LABEL org.opencontainers.image.title="frame" \
      org.opencontainers.image.description="Pure x86_64 assembly X11 display server" \
      org.opencontainers.image.source="https://github.com/tacitness/frame" \
      org.opencontainers.image.licenses="Unlicense" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.created="${CREATED}" \
      io.github.tacitness.frame.source-state="${SOURCE_STATE}" \
      io.github.tacitness.frame.binary-sha256="${BINARY_SHA256}"

COPY --chmod=0755 frame /usr/local/bin/frame

# The image is non-root by default. Hardware-backed use must deliberately map
# the required devices, groups, and /tmp/.X11-unix; CI never does so.
USER 65532:65532
STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/local/bin/frame"]
