# Running the system in production

The website runs on this PC in Docker: **nginx** receives every request and sends it to the
**frontend** (the React pages) or the **backend** (the API). The backend reads the local
database file **read-only**, so the website can never change the data. A Cloudflare tunnel can
give the site a public link. To update the data and the NM-index, see
[RUN_EQUATIONS.md](RUN_EQUATIONS.md).

```
 visitor ──► Cloudflare tunnel ──► nginx (localhost:80) ──┬──► frontend   (the web pages)
 (optional, public link)                                  └──► backend    (/api/…)
                                                                  │ read-only
                                                                  ▼
                                    OpenAlex_Data_Collection\database\openalex.db
```

All commands below run in PowerShell **from the project folder**:

```powershell
cd D:\SoftwareProject
```

## What you need (once)

| | |
|---|---|
| **Docker Desktop** | installed. Start it and wait for **Engine running** before any `docker` command |
| **`production\.env`** | the settings, see the table below |
| **The database** | `OpenAlex_Data_Collection\database\openalex.db`. Docker reads it where it is |
| **Lock files** | `frontend\package-lock.json` and `backend\package-lock.json` are in git, so every PC builds exactly the same package versions; they must match `package.json` (see Problems) |
| **cloudflared** | only for a public link: `winget install --id Cloudflare.cloudflared` |

Settings in `production\.env`:

| Setting | Meaning |
|---|---|
| `JWT_SECRET` | long random secret for login sessions: at least 32 characters (the backend refuses to start otherwise), and different from the one in `backend\.env` |
| `JWT_EXPIRES_IN` | how long a login lasts, e.g. `1d` (logout and password reset end it earlier) |
| `FIREBASE_SERVICE_ACCOUNT_BASE64` | the Firebase Admin key (server side only) |
| `CORS_ALLOWED_ORIGINS` | usually **empty**. The site's own address is always allowed: `http://localhost` and every tunnel link. List only *other* websites that must call this API, comma-separated |
| `REACT_APP_FIREBASE_API_KEY`, `…_AUTH_DOMAIN`, `…_PROJECT_ID`, `…_STORAGE_BUCKET`, `…_MESSAGING_SENDER_ID`, `…_APP_ID` | the Firebase **web** settings, built into the pages |

The old `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` lines are not used any more.
They can stay.

## 1. Build (first time, and after every code change)

Build one part at a time: Docker's network on this PC is slow and works better that way.

```powershell
docker compose --env-file production/.env -f production/compose.yaml build backend
docker compose --env-file production/.env -f production/compose.yaml build frontend
```

The first build downloads a lot and can take a long time. If it stops with a network error,
**run the same command again**: packages already downloaded are kept, so it continues.

## 2. Start

```powershell
docker compose --env-file production/.env -f production/compose.yaml up -d
```

## 3. Check

```powershell
docker compose --env-file production/.env -f production/compose.yaml ps
```

`backend` should be **running** and **healthy**, and `frontend` and `nginx` **running**.

## 4. Open the website

- Website: **http://localhost**
- Health check: http://localhost/api/health should show
  `{"status":"ok","dependencies":{"database":"connected","firebaseAdmin":"configured"}}`

The first pages after a start can take up to about a minute, because Docker reads the large
database file slowly at first. After that it gets faster.

## 5. Share a public link (optional)

1. Start the tunnel in its **own** PowerShell window, and keep that window open:

   ```powershell
   cloudflared tunnel --url http://localhost:80
   ```

   After a few seconds it prints a link like `https://something-random.trycloudflare.com`.
   **The link changes every time** you start the tunnel, so repeat step 2 each time.

   Use exactly this command for the Docker site. Do not add `--http-host-header`: that
   option is only for sharing the `npm start` development server, and with it the backend
   would no longer recognise the link as its own address.

   Nothing has to change in `production\.env`: the backend allows its own address, whatever
   the link is (`CORS_ALLOWED_ORIGINS` is only for other websites).

2. In the [Firebase Console](https://console.firebase.google.com), open the project, then
   **Authentication → Settings → Authorized domains → Add domain**, and enter
   `something-random.trycloudflare.com` (without `https://`). Without this, login does not
   work on the link.

3. Open the link on another device (for example a phone on mobile data) to test it, then share
   it.

To stop sharing, press **Ctrl+C** in the tunnel window.

## 6. Stop

```powershell
docker compose --env-file production/.env -f production/compose.yaml down
```

## Everyday use

| I want to… | Do this |
|---|---|
| start the site | `docker compose --env-file production/.env -f production/compose.yaml up -d` |
| stop the site | `docker compose --env-file production/.env -f production/compose.yaml down` |
| use changed code | build again (section 1), then start (section 2) |
| show new results after running the equations | nothing: refresh the page (the backend reads the database live) |
| see what the backend is doing | `docker compose --env-file production/.env -f production/compose.yaml logs -f backend` (Ctrl+C to leave) |
| see the nginx requests | `docker compose --env-file production/.env -f production/compose.yaml logs -f nginx` |

Tip: in a PowerShell window, this makes the commands short. `dc up -d`, `dc ps`, `dc down`
then work in that window:

```powershell
function dc { docker compose --env-file production/.env -f production/compose.yaml @args }
```

## Problems

| Problem | Fix |
|---|---|
| `error during connect` or `cannot find the file specified` on any `docker` command | Docker Desktop is not running: start it and wait for **Engine running** |
| Build fails at `npm ci` with `package.json and package-lock.json … are in sync` | The lock file is out of date. Run `npm install --package-lock-only` in `frontend` (or `backend`), then build again |
| Build stops with network errors (`ECONNRESET`, `ETIMEDOUT`, TLS) | Run the same build command again; it continues where it stopped |
| `port is already allocated` / port 80 in use | Another program uses port 80 (IIS, another web server). Stop it, then start again |
| Health check shows `"database":"unavailable"` | Check that `OpenAlex_Data_Collection\database\openalex.db` exists, then look at the backend logs |
| First page is very slow, or `504 Gateway Timeout` | Normal right after a start: wait a little and refresh |
| Login fails on the trycloudflare link | Add the link's domain to Firebase's authorized domains (section 5, step 2). If the backend log shows `CORS: refused a request from …`, the tunnel was started with `--http-host-header` or points somewhere other than `http://localhost:80`: start it again with exactly `cloudflared tunnel --url http://localhost:80` |
| `cloudflared is not recognized` | Open a new PowerShell window after installing it, or run `& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:80` |
| Pages show errors while a Python script runs | Docker cannot see the script's file locks. Wait for the script to finish, or stop the site while scripts run |

## Good to know

- **Keep the PC on**, with Docker running (and the tunnel window open, for the public link).
- **Anyone with the link** can open the site while the tunnel runs.
- The backend answers **one database query at a time**, so the site gets slower when several
  people use it at once.
- The database is mounted **read-only**: the website can never change the data. Its location
  is set in `production\compose.yaml` (the `volumes:` line of the backend).

## Without Docker (for development)

Two PowerShell windows. This needs Node.js 22.13 or newer.

```powershell
cd D:\SoftwareProject\backend
npm install
npm run dev          # backend on http://localhost:5005
```

```powershell
cd D:\SoftwareProject\frontend
npm install
npm start            # website on http://localhost:3000
```

The backend reads `backend\.env` (`PORT=5005`, Firebase key, `JWT_SECRET`). The frontend reads
`frontend\.env` (`REACT_APP_API_URL=http://localhost:5005` and the Firebase web settings). If
port 3000 is in use, `npm start` asks to use another port: press `Y`.
