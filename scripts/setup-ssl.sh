#!/bin/bash
# ═══════════════════════════════════════════════════════════
# CrossWave — SSL Certificate Setup (Let's Encrypt)
# ═══════════════════════════════════════════════════════════
# Prerequisites:
#   1. Domain DNS pointing to your server
#   2. Nginx running on port 80
#   3. Docker compose with nginx service running
# ═══════════════════════════════════════════════════════════

set -euo pipefail

DOMAINS="crosswave.app www.crosswave.app blog.crosswave.app"
EMAIL="admin@crosswave.app"
SSL_DIR="$(cd "$(dirname "$0")/.." && pwd)/ssl"

echo "🔐 CrossWave SSL Certificate Setup"
echo "=================================="
echo "Domains: $DOMAINS"
echo "SSL dir: $SSL_DIR"
echo ""

# Check prerequisites
if ! command -v docker &> /dev/null; then
  echo "❌ Docker not found. Please install Docker first."
  exit 1
fi

# Create SSL directory
mkdir -p "$SSL_DIR"

# Option 1: Self-signed (for testing)
if [ "${1:-}" = "--self-signed" ]; then
  echo "🔑 Generating self-signed certificate (for testing)..."
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$SSL_DIR/privkey.pem" \
    -out "$SSL_DIR/fullchain.pem" \
    -subj "/CN=crosswave.app" \
    -addext "subjectAltName=DNS:crosswave.app,DNS:www.crosswave.app,DNS:blog.crosswave.app"
  echo "✅ Self-signed certificate created at $SSL_DIR/"
  echo "⚠️  Browsers will show a warning — use only for testing."
  exit 0
fi

# Option 2: Let's Encrypt (production)
echo "🌐 Requesting Let's Encrypt certificates..."
echo "Make sure your domain DNS is pointed to this server."
echo ""

# Ensure nginx is running on port 80 for HTTP challenge
if ! curl -sf http://localhost/health > /dev/null 2>&1; then
  echo "⚠️  Nginx doesn't seem to be running on port 80."
  echo "   Start it first: docker compose up -d nginx"
  echo ""
  read -rp "Continue anyway? (y/N) " confirm
  if [ "$confirm" != "y" ]; then
    exit 1
  fi
fi

# Run certbot via Docker
for domain in $DOMAINS; do
  echo "  → Requesting cert for $domain ..."
done

docker run --rm -it \
  -v "$SSL_DIR:/etc/letsencrypt" \
  -p 80:80 \
  certbot/certbot certonly --standalone \
  --agree-tos \
  --email "$EMAIL" \
  --domains "$(echo $DOMAINS | tr ' ' ',')" \
  --non-interactive \
  --preferred-challenges http

# Copy certs to ssl/ directory
echo ""
echo "📋 Copying certificates to $SSL_DIR/ ..."
docker run --rm \
  -v "$SSL_DIR:/etc/letsencrypt" \
  alpine cp -L \
    /etc/letsencrypt/live/crosswave.app/fullchain.pem \
    /etc/letsencrypt/live/crosswave.app/privkey.pem \
    /etc/letsencrypt/

echo "✅ SSL certificates installed!"
echo ""
echo "Restart nginx to pick up the new certs:"
echo "  docker compose restart nginx"
echo ""
echo "Auto-renewal (add to crontab):"
echo "  0 3 * * * docker run --rm -v $SSL_DIR:/etc/letsencrypt certbot/certbot renew && docker compose restart nginx"
