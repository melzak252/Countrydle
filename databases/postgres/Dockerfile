FROM postgres:14

# Install the pgvector extension
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-14-pgvector \
    && rm -rf /var/lib/apt/lists/*

USER postgres

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD pg_isready -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}" || exit 1
