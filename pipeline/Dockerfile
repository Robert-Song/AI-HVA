FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY src/ ./src/

# Domain knowledge corpus (curated docs for RAG)
COPY domain_docs/ ./domain_docs/

# Pre-built domain knowledge DB (optional — can also build at runtime)
# Uncomment if you want to bake the index into the image:
# COPY domain_knowledge_db/ ./domain_knowledge_db/

# Datasheets and output directories
RUN mkdir -p /app/datasheets /app/output

ENTRYPOINT ["python", "-m", "src.main"]
