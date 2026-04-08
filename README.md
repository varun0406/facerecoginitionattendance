# Face Recognition Attendance (Web)

Web application for **vendor / staff attendance** using the device camera. Each person is identified with **OpenCV LBPH** face recognition; the model label is the same as **`vendor_id`** in the database, so attendance is always tied to that registered user.

## Behaviour

- **First successful recognition today** → records **start time** (clock in).
- **Second successful recognition the same day** → records **stop time** (clock out).
- **Further scans** after both are set → face may still match, but the app explains that the day is already complete (no duplicate punches).

Offline punches are queued and synced when the database is reachable again.

## Strict training (production / VM)

Training captures are **rejected** unless the server accepts a single, large-enough, sharp face with reasonable brightness. **Train model** stays disabled until **every** `vendor_id` that has files under `data/` has at least **`TRAINING_MIN_IMAGES`** (default **18**) samples and a matching user row in the database.

Tune without editing code:

| Environment variable | Default | Purpose |
|----------------------|---------|---------|
| `FLASK_HOST` | `0.0.0.0` | Bind address (VM: keep `0.0.0.0` to reach from browser/phone) |
| `FLASK_PORT` | `8002` | HTTP port |
| `FLASK_DEBUG` | `false` | Set `true` only while developing |
| `TRAINING_MIN_IMAGES` | `18` | Minimum saved faces per user who has any training data |
| `TRAINING_RECOMMENDED_IMAGES` | `30` | Shown in UI as “recommended” |
| `FACE_CONFIDENCE_MIN` | `78` | Attendance: higher = stricter match (fewer wrong accepts) |
| `FACE_REJECT_MULTIPLE` | `true` | Reject attendance frame if more than one face is detected |

## Stack

- **Backend:** Flask, MySQL or PostgreSQL (`database.py`, `config.py`)
- **Frontend:** React + Vite (`frontend/`, built to `static/`)
- **Recognition:** `opencv-contrib-python` (Haar + LBPH), `face_recognition_service.py`, `training_service.py`

## Fast start with SQLite (no MySQL)

```bash
git clone https://github.com/varun0406/facerecoginitionattendance.git
cd facerecoginitionattendance
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_TYPE=sqlite   # default in config if unset
export FLASK_PORT=8002
python3 test_connection.py
cd frontend && npm install && npm run build && cd ..
python3 app.py
```

Open `http://localhost:8002`. The DB file is `attendance.db` in the project folder.

**VM tip:** If `frontend/package.json` is missing after `git clone`, your remote repo is incomplete. Push the full tree (including `frontend/`) from your dev machine, or `scp -r frontend user@server:/opt/facerecoginitionattendance/`.

## Run (local or VM)

1. **Database:** default is **SQLite** (`DATABASE_TYPE=sqlite`, `SQLITE_PATH=attendance.db`). For MySQL/PostgreSQL, set env vars (see `deploy/env.example`) or legacy fields in `config.py`.
2. `pip install -r requirements.txt`
3. Build UI. From another machine, point the UI at your VM API:

   ```bash
   cd frontend
   npm install
   VITE_API_URL=http://YOUR_VM_IP:8002/api npm run build
   cd ..
   ```

   If you only open the app on the same machine as Flask, `npm run build` without `VITE_API_URL` is enough (defaults to `http://localhost:8002/api`).

4. Start the server:

   ```bash
   export FLASK_HOST=0.0.0.0
   export FLASK_DEBUG=false
   python app.py
   ```

   Or `./start.sh` / `start.bat`. Open firewall / security group for `FLASK_PORT` if needed.

5. **Test flow:** Users → Training (capture until green minimum) → **Train model** (button enables when `GET /api/training/readiness` reports `can_train: true`) → Attendance.

6. **API smoke test** (with Flask running):

   ```bash
   API_BASE=http://127.0.0.1:8002/api python3 smoke_test_api.py
   ```

## Registering people (face → person)

1. Add the person under **Users** (`vendor_id`, name, etc.).
2. Under **Training**, capture faces for that **same numeric ID** until you meet the minimum (progress bar + server errors guide you).
3. Under **Train Model**, train only when the readiness table allows it.

Training filenames use `user.{vendor_id}.{n}.jpg`, so the recognizer’s numeric label matches `vendor_id`.

## API (summary)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/recognize` | Image → identify user → clock in or out |
| GET | `/api/attendance` | List records (`date`, `limit`) |
| GET/POST | `/api/vendors` | User / vendor CRUD |
| GET | `/api/training/readiness` | Strict checklist + `can_train` |
| POST | `/api/training/*` | Capture images, train model |

See `END_TO_END_GUIDE.md` and `QUICK_START.md` for detailed setup.

## VM production deploy

Use **`deploy/install.sh`**, **`deploy/env.example`**, and **`deploy/README.md`** for systemd + Gunicorn + optional nginx. Database credentials are read from **`DATABASE_*`** environment variables (see `deploy/env.example`).
