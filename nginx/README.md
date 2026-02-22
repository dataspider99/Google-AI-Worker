# Nginx configuration for g.oshaani.com

## Install

**If you don’t have SSL certs yet** (first-time or certs missing), use the HTTP-only config so nginx can start and certbot can run:

1. **Copy the HTTP-only config** (RHEL / Amazon Linux):
   ```bash
   sudo cp nginx/g.oshaani.com.http-only.conf /etc/nginx/conf.d/g.oshaani.com.conf
   ```
2. **Test and reload nginx:**
   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. **Obtain SSL cert** (DNS for g.oshaani.com must point to this server):
   ```bash
   sudo certbot --nginx -d g.oshaani.com
   ```
   Certbot will get the cert and update the config. To use the repo’s full HTTPS config (redirect HTTP→HTTPS, etc.), replace the site config with the SSL version:
   ```bash
   sudo cp nginx/g.oshaani.com.conf /etc/nginx/conf.d/g.oshaani.com.conf
   sudo nginx -t && sudo systemctl reload nginx
   ```

**If you already have certs** at `/etc/letsencrypt/live/g.oshaani.com/`:

1. **Copy the full (HTTPS) config** (RHEL / Amazon Linux):
   ```bash
   sudo cp nginx/g.oshaani.com.conf /etc/nginx/conf.d/g.oshaani.com.conf
   ```
   On Debian/Ubuntu use `sites-available` and symlink into `sites-enabled` instead of `conf.d`.

2. **Test and reload nginx:**
   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```

Renewal is automatic (certbot installs a timer). Test with: `sudo certbot renew --dry-run`.

## Prerequisites

- App running in production on port **8002**, e.g.:
  ```bash
  ENVIRONMENT=production uvicorn main:app --host 127.0.0.1 --port 8002
  ```
- DNS for **g.oshaani.com** pointing to this server.
