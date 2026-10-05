services:
  postgres:
    image: postgres:16
    environment: {POSTGRES_USER: aftershock, POSTGRES_PASSWORD: "${PG_PASSWORD:?set PG_PASSWORD}", POSTGRES_DB: aftershock}
    volumes: [pgdata:/var/lib/postgresql/data]
  backend:
    build: {context: ., dockerfile: backend/Dockerfile}
    environment:
      DATABASE_URL: postgresql://aftershock:${PG_PASSWORD}@postgres:5432/aftershock
      SECRET_KEY: "${SECRET_KEY:?set SECRET_KEY}"
      DEMO_PASSWORD: "${DEMO_PASSWORD:?set DEMO_PASSWORD}"
    ports: ["80:8000"]
    depends_on: [postgres]
volumes: {pgdata: {}}
