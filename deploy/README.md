# School Sansar - Production Deployment Guide

This guide covers deploying the multi-tenant **School Sansar** ERP on a cloud virtual machine (AWS EC2, DigitalOcean Droplet, Hetzner, or VPS) using the unified Docker Compose stack.

---

## 1. Prerequisites

* **Operating System:** Ubuntu 22.04 LTS / 24.04 LTS (recommended)
* **Compute:** Minimum 2 vCPU, 4 GB RAM, 20 GB SSD
* **Docker & Compose:** Docker Engine 24+ and Docker Compose v2
* **DNS Configuration:**
  * Base Domain: `schoolsansar.com` ➔ `YOUR_SERVER_IP`
  * Wildcard A Record: `*.schoolsansar.com` ➔ `YOUR_SERVER_IP` (for multi-tenant school subdomains)

---

## 2. Server Setup & Cloning

```bash
# Update server packages
sudo apt update && sudo apt upgrade -y

# Install Docker & Docker Compose
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Clone the repository
git clone <YOUR_GIT_REPO_URL> /opt/schoolsansar
cd /opt/schoolsansar
```

---

## 3. Configure Production Secrets

Copy the production environment template:
```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

Generate secure production keys:
```bash
# Generate Django SECRET_KEY
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))"

# Generate FIELD_ENCRYPTION_KEY for sensitive database columns
python3 -c "from cryptography.fernet import Fernet; print('FIELD_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```
Edit `.env.production` using `nano` or `vim` and update:
1. `SECRET_KEY` and `FIELD_ENCRYPTION_KEY`
2. `DB_PASSWORD` (use a strong random password)
3. `ALLOWED_HOSTS` and `TENANT_BASE_DOMAIN` (match your real domain)
4. `RAZORPAY_*` keys (for fee payments and subscriptions)
5. `EMAIL_*` SMTP credentials (for absence alerts, receipts, and fee reminders)

---

## 4. Build and Launch the Stack

Start all 7 services in the background:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Check container status:
```bash
docker compose -f docker-compose.prod.yml ps
```
You should see all containers running and healthy:
- `schoolsansar_db` (PostgreSQL 15)
- `schoolsansar_redis` (Redis 7)
- `schoolsansar_backend` (Gunicorn Django API)
- `schoolsansar_worker` (Celery background worker)
- `schoolsansar_beat` (Celery cron scheduler)
- `schoolsansar_frontend` (Next.js 16 production server)
- `schoolsansar_nginx` (Nginx reverse proxy)

---

## 5. Database Schema Initialization

Run the initial schema migrations:

```bash
# The migration gate needs --apply and --confirm-database <DB_NAME> (the compose file already sets
# EDUSEKAI_EXPECTED_DATABASE from DB_NAME). Replace schoolsansar_production with your DB_NAME.

# 1. Sync Shared (Public) Schema
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate_schemas --shared --apply --confirm-database schoolsansar_production

# 2. Sync Tenant Schemas
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate_schemas --tenant --apply --confirm-database schoolsansar_production

# 3. Collect Django Static Assets (Admin & API styles)
docker compose -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput

# 4. Create Platform Superuser (for System Administration)
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

---

## 6. SSL / TLS Certificates (Let's Encrypt / Certbot)

To secure all subdomains with HTTPS:
```bash
sudo apt install certbot -y

# Issue wildcard certificate via DNS challenge (Cloudflare, Route53, etc.)
sudo certbot certonly --manual --preferred-challenges=dns -d "schoolsansar.com" -d "*.schoolsansar.com"
```
Mount the generated certificates into `/deploy/nginx/ssl` and update `deploy/nginx/conf.d/schoolsansar.conf` to enable the SSL listener on port 443.

Django redirects HTTP to HTTPS by default in production (`SECURE_SSL_REDIRECT`). Until TLS works end to end
(your own certificates, or a CDN/load balancer in front that sends `X-Forwarded-Proto: https`), a plain-HTTP trial
will loop or fail. For a trial over HTTP only, set `SECURE_SSL_REDIRECT=False` and
`USE_SECURE_PROXY_SSL_HEADER=False` in `.env.production`, and turn them back on before real use.

---

## 7. Ongoing Maintenance & Operations

### View Live Logs:
```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific container
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f frontend
docker compose -f docker-compose.prod.yml logs -f celery_worker
```

### Apply New Migrations After Code Updates:
```bash
git pull origin main
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate_schemas --shared --apply --confirm-database schoolsansar_production
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate_schemas --tenant --apply --confirm-database schoolsansar_production
```

### PostgreSQL Database Backups:
```bash
# Create automated backup dump
docker compose -f docker-compose.prod.yml exec db pg_dump -U postgres schoolsansar_production | gzip > /opt/backups/schoolsansar_$(date +%Y%m%d_%H%M%S).sql.gz
```
