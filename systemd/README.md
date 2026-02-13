# Systemd setup for Johny Sins

## Install

1. **Copy the unit file:**
   ```bash
   sudo cp /home/ec2-user/Johny-Sins/systemd/johny-sins.service /etc/systemd/system/
   ```

2. **If your app lives elsewhere**, edit the service file after copying:
   - `WorkingDirectory=`
   - `EnvironmentFile=`
   - `User=` / `Group=` if not `ec2-user`

3. **Reload systemd and enable the service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable johny-sins
   sudo systemctl start johny-sins
   ```

4. **Check status:**
   ```bash
   sudo systemctl status johny-sins
   ```

## Commands

| Command | Description |
|--------|-------------|
| `sudo systemctl start johny-sins` | Start the service |
| `sudo systemctl stop johny-sins` | Stop the service |
| `sudo systemctl restart johny-sins` | Restart the service |
| `sudo systemctl status johny-sins` | Show status |
| `journalctl -u johny-sins -f` | Follow logs |

## Notes

- The service runs on **port 8002** and binds to **127.0.0.1** (use nginx to proxy).
- `.env` is loaded from the project root; ensure `APP_BASE_URL`, `GOOGLE_REDIRECT_URI`, and `SECRET_KEY` are set for production.
- To use a virtualenv, set `ExecStart` to `/home/ec2-user/Johny-Sins/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8002` and ensure `User`/`Group` can read the venv.
