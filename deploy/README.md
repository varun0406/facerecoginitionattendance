# VM deployment

## What you get

- **Gunicorn** (`wsgi.py`) — production process; **one worker** so the offline sync thread runs once.
- **`/etc/face-attendance.env`** — database URL, `VITE_API_URL` for the React build, optional CORS.
- **systemd** unit `face-attendance.service`.
- Optional **nginx** TLS example in `nginx-face-attendance.conf`.

## Prerequisites (Ubuntu 22.04+)

**SQLite (simplest — no database server):**

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nodejs npm
```

Use `deploy/env.example` with `DATABASE_TYPE=sqlite` and `SQLITE_PATH=attendance.db` (default). The file is created next to the app when the service runs.

**MySQL (optional):**

```bash
sudo apt install -y mysql-server
```

```sql
CREATE DATABASE attendance CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'attendance'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL ON attendance.* TO 'attendance'@'localhost';
FLUSH PRIVILEGES;
```

Set `DATABASE_TYPE=mysql` and the `DATABASE_*` variables in `/etc/face-attendance.env`.

## If `npm` says `package.json` not found

The GitHub repo must contain the **`frontend/`** directory (Vite + React). If you cloned an old or partial repo, either:

- **Push** the complete project from your machine (including `frontend/`), then on the server: `git pull`, or  
- **Copy only the frontend:** from your laptop:  
  `scp -r /path/to/project/frontend root@SERVER:/opt/facerecoginitionattendance/`

Then run `npm install` and `npm run build` inside `frontend/`.

## Install

1. Clone or copy the project to the VM, e.g. `/opt/face-attendance`.
2. Copy and edit environment file:

   ```bash
   sudo cp deploy/env.example /etc/face-attendance.env
   sudo chmod 640 /etc/face-attendance.env
   sudo nano /etc/face-attendance.env
   ```

   Set at least: `DATABASE_*`, `FLASK_PORT=8002`, `VITE_API_URL` (must match, e.g. `http://203.0.113.10:8002/api` or `https://your.domain/api`).

3. Run the installer from the project root:

   ```bash
   chmod +x deploy/install.sh
   ./deploy/install.sh
   ```

4. Start the service:

   ```bash
   sudo systemctl start face-attendance
   sudo systemctl status face-attendance
   ```

5. Open firewall for port **8002** (or only **443** if using nginx).

## Rebuild UI after changing public URL

After you change `VITE_API_URL` in `/etc/face-attendance.env`:

```bash
./deploy/install.sh --build-only
```

## HTTPS (recommended)

Use the sample `nginx-face-attendance.conf`, obtain certificates (e.g. Certbot), and set:

- `VITE_API_URL=https://your.domain/api`
- `CORS_ORIGINS=https://your.domain`

Then rebuild with `--build-only` and restart nginx.

## Smoke test

With the service up:

```bash
API_BASE=http://127.0.0.1:8002/api python3 smoke_test_api.py
```

## Paths on the server

| Path | Purpose |
|------|---------|
| `data/` | Training face crops |
| `classifier.xml` | LBPH model |
| `offline_queue/` | Pending attendance sync |
| `static/` | Built React app |

Back these up or store the VM disk on durable storage.
