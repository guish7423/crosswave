# CrossDeploy Delivery Checklist

## Pre-Deployment
- [ ] Customer requirements collected
- [ ] Tech stack confirmed
- [ ] VPS credentials received
- [ ] Domain DNS pointed to VPS
- [ ] Tier selected and payment confirmed

## Environment
- [ ] SSH access verified
- [ ] Docker + Docker Compose installed
- [ ] Python 3.12+ / Node.js 20+ available
- [ ] Firewall configured (80/443/22 only)
- [ ] Fail2ban installed
- [ ] Swap configured (2GB)

## Deployment
- [ ] Code cloned / uploaded
- [ ] Dockerfile created (if not exists)
- [ ] docker-compose.yml created
- [ ] .env generated with secrets
- [ ] Services start without errors
- [ ] Health endpoint responds 200

## SSL & Domain
- [ ] Nginx/Caddy reverse proxy configured
- [ ] Let's Encrypt SSL via acme.sh or Caddy
- [ ] HTTPS forced
- [ ] Domain resolves correctly
- [ ] www redirect configured

## CI/CD (Standard+)
- [ ] GitHub Actions workflow created
- [ ] Automatic deploy on push
- [ ] Rollback mechanism documented

## Monitoring (Enterprise)
- [ ] Prometheus + Grafana dashboard
- [ ] Alert rules configured
- [ ] Backup schedule set
- [ ] Log rotation configured

## Handover
- [ ] Customer tested the live URL
- [ ] All credentials securely sent (1-time link)
- [ ] README written in Chinese
- [ ] Support period confirmed
- [ ] Invoice/receipt sent
