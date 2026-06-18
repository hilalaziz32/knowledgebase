# Single image for Railway: Next.js frontend + Python agents (the web server
# spawns the agents via child_process, so both live in one container).
FROM node:20-slim

# Python for the agents
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-pip build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Python deps into a venv (cached unless requirements change)
COPY agents/requirements.txt ./agents/requirements.txt
RUN python3 -m venv /app/agents/.venv \
    && /app/agents/.venv/bin/pip install --no-cache-dir -r agents/requirements.txt

# 2) Node deps (cached unless package.json changes)
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install

# 3) App source + build
COPY . .
RUN cd frontend && npm run build

ENV NODE_ENV=production
ENV AGENTS_DIR=/app/agents
ENV PYTHON_BIN=/app/agents/.venv/bin/python
ENV PORT=3000
EXPOSE 3000

# Railway injects SUPABASE_DB_URL, GEMINI_API_KEY, AIRTABLE_API_KEY, AIRTABLE_BASE_ID
# as service variables; the spawned python inherits them (no .env needed in the image).
CMD ["sh", "-c", "cd frontend && npm run start -- -p ${PORT:-3000} -H 0.0.0.0"]
