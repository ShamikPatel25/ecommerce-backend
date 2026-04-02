#!/bin/bash
# ==============================================
# Production Deployment Script
# ==============================================
# Usage: ./deploy.sh myplatform.com your@email.com
# ==============================================

set -e

DOMAIN=${1:?"Usage: ./deploy.sh <domain> <email>"}
EMAIL=${2:?"Usage: ./deploy.sh <domain> <email>"}

echo "==> Deploying to: $DOMAIN"
echo "==> SSL email: $EMAIL"

# 1. Replace domain in nginx config
sed -i "s/myplatform.com/$DOMAIN/g" nginx/nginx.conf

# 2. Create certbot directories
mkdir -p certbot/www certbot/conf

# 3. Start services WITHOUT SSL first (for certbot challenge)
echo "==> Starting services (HTTP only for SSL certificate)..."

# Temporarily modify nginx to serve HTTP only (for initial SSL setup)
cat > nginx/nginx-init.conf << 'INITEOF'
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER *.DOMAIN_PLACEHOLDER;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'Setting up SSL...';
        add_header Content-Type text/plain;
    }
}
INITEOF

sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" nginx/nginx-init.conf

# Temporarily use init config
cp nginx/nginx.conf nginx/nginx.conf.bak
cp nginx/nginx-init.conf nginx/nginx.conf

docker compose -f docker-compose.prod.yml up -d nginx

# 4. Get SSL certificate
echo "==> Obtaining SSL certificate for $DOMAIN and *.$DOMAIN..."
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    -d "$DOMAIN" \
    -d "api.$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email

# Note: Wildcard certs (*.domain.com) require DNS challenge.
# For individual store subdomains, you have two options:
# Option A: Use a wildcard cert with DNS challenge (recommended):
#   docker compose -f docker-compose.prod.yml run --rm certbot certonly \
#     --manual --preferred-challenges dns \
#     -d "$DOMAIN" -d "*.$DOMAIN" \
#     --email "$EMAIL" --agree-tos
# Option B: Add store subdomains individually as stores are created

# 5. Restore full nginx config with SSL
echo "==> Switching to SSL nginx config..."
cp nginx/nginx.conf.bak nginx/nginx.conf
rm nginx/nginx-init.conf nginx/nginx.conf.bak

# 6. Start all services
echo "==> Starting all services..."
docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "==> Deployment complete!"
echo "    Main site: https://$DOMAIN"
echo "    API:       https://api.$DOMAIN"
echo "    Stores:    https://<store-subdomain>.$DOMAIN"
echo ""
echo "==> For wildcard SSL (all subdomains), run:"
echo "    docker compose -f docker-compose.prod.yml run --rm certbot certonly \\"
echo "      --manual --preferred-challenges dns \\"
echo "      -d '$DOMAIN' -d '*.$DOMAIN' \\"
echo "      --email '$EMAIL' --agree-tos"
