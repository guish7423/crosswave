# CrossDeploy Enterprise — Delivery Template

## Files to Create
```
project/
├── k3s/
│   ├── app-deployment.yaml
│   ├── app-service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   └── hpa.yaml
├── monitoring/
│   ├── prometheus.yml
│   └── grafana-dashboard.json
├── backup/
│   └── backup.sh
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── README.md
```

## K3s Deployment Template
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: app
  template:
    metadata:
      labels:
        app: app
    spec:
      containers:
      - name: app
        image: ${IMAGE}:${TAG}
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: app-config
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: app
spec:
  selector:
    app: app
  ports:
  - port: 80
    targetPort: 8000
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Backup Automation
```bash
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR="/backup/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Database dump
docker exec $(docker ps -q -f name=db) pg_dump -U $DB_USER $DB_NAME > "$BACKUP_DIR/db.sql"
gzip "$BACKUP_DIR/db.sql"

# Upload to S3-compatible storage
rclone copy "$BACKUP_DIR" s3:crosswave-backups/

# Keep 30 days
find /backup -type d -mtime +30 -exec rm -rf {} \;
```

## Monitoring (Prometheus + Grafana)
```yaml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana-dashboard.json:/etc/grafana/provisioning/dashboards/app.json

volumes:
  prometheus-data:
  grafana-data:
```
