# Nginx configuration for jsins.oshaani.com

## Install

1. **Copy the config** (choose one):

   - **RHEL / Amazon Linux** (conf.d):
     ```bash
     sudo cp nginx/jsins.oshaani.com.conf /etc/nginx/conf.d/jsins.oshaani.com.conf
     ```
   - **Debian / Ubuntu** (sites-available):
     ```bash
     sudo cp nginx/jsins.oshaani.com.conf /etc/nginx/sites-available/jsins.oshaani.com.conf
     sudo ln -s /etc/nginx/sites-available/jsins.oshaani.com.conf /etc/nginx/sites-enabled/
     ```

2. **Test and reload nginx:**
   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```

3. **SSL (HTTPS)** with Let's Encrypt:
   ```bash
   sudo certbot --nginx -d jsins.oshaani.com
   ```
   Renewal is automatic (certbot installs a timer). Test with: `sudo certbot renew --dry-run`.

## Prerequisites

- App running in production on port **8002**, e.g.:
  ```bash
  ENVIRONMENT=production uvicorn main:app --host 127.0.0.1 --port 8002
  ```
- DNS for **jsins.oshaani.com** pointing to this server.
