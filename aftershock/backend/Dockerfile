FROM node:20-slim AS fe
WORKDIR /fe
COPY frontend/package.json ./
RUN npm install --silent
COPY frontend/ .
RUN sed -i 's#"../backend/static_react"#"/out"#' vite.config.ts && npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=fe /out ./static_react
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000"]
