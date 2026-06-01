# CrossDeploy Standard — Delivery Template

## Files to Create
```
project/
├── docker-compose.yml       # Multi-service stack
├── Dockerfile               # App image
├── .env.example
├── nginx/
│   └── app.conf
├── .github/
│   └── workflows/
│       └── deploy.yml       # CI/CD
└── README.md
```

## Docker Compose Template
```yaml
version: '3.8'
services:
  app:
    build: .
    restart: always
    ports:
      - "127.0.0.1:8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started

  db:
    image: postgres:16-alpine
    restart: always
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASS}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 5s

  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redisdata:/data

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx:/etc/nginx/conf.d
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - app

volumes:
  pgdata:
  redisdata:
```

## CI/CD (GitHub Actions)
```yaml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USER }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd /opt/app
            git pull
            docker compose pull
            docker compose up -d --build
            docker image prune -f
```
