# Deploying to Render

The assignment only requires the app to run locally. This guide is for an optional public demo.

**Architecture:** Render runs the web app from the project's `Dockerfile`. Render does not offer MySQL, so the database is a hosted **MySQL 8** on [Aiven](https://aiven.io), which has a free plan. It is real MySQL, so row locks, CHECK constraints and `FOR UPDATE OF` behave exactly as they do locally.

```
Browser ──HTTPS──> Render web service (Docker: FastAPI + uvicorn)
                        │  TLS (verified with Aiven's CA certificate)
                        ▼
                   Aiven MySQL 8
```

On every start, the container's entrypoint waits for the database, runs `alembic upgrade head`, and loads the sample data if `SEED_ON_START=true`. Seeding is idempotent. It then starts uvicorn on the port Render assigns (`$PORT`).

## 1. Create the MySQL database (Aiven)

1. Sign up at aiven.io. Choose **Create service → MySQL**, then the **Free** plan, and a region close to your Render region (e.g. Singapore).
2. When the service is *Running*, open its **Overview**. Note the **Host**, **Port**, **User** (`avnadmin`), **Password** and **Database** (`defaultdb`).
3. Download the **CA certificate** (`ca.pem`) from the same page.

Your `DATABASE_URL` is built from those values:

```
mysql+pymysql://avnadmin:<PASSWORD>@<HOST>:<PORT>/defaultdb
```

If the password contains special characters such as `@`, `:`, `/` or `#`, URL-encode them (e.g. `@` becomes `%40`).

## 2. Push the code to GitHub

Render deploys from a Git repository. The repo must contain `Dockerfile`, `render.yaml` and `docker/entrypoint.sh`.

## 3. Create the web service (Render)

**Option A: Blueprint (uses `render.yaml`)**

1. In Render, choose **New → Blueprint**, connect the GitHub repo, then **Apply**.
2. Render asks for the values marked `sync: false`: `DATABASE_URL` and the three `SEED_*_PASSWORD`s. `SECRET_KEY` is generated automatically.

**Option B: by hand**

1. In Render, choose **New → Web Service**, select the repo, and set **Runtime: Docker**.
2. Set **Health Check Path** to `/api/health`.
3. Under **Environment**, add the variables listed in `render.yaml`. Generate `SECRET_KEY` with:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`

**Both options:** add the certificate in one of two ways.

- **Secret File (default in `render.yaml`).** Under **Environment → Secret Files**, add a file named exactly **`ca.pem`** and paste the contents of Aiven's `ca.pem`. Render mounts it at `/etc/secrets/ca.pem`, which is the value of `DATABASE_SSL_CA`.
- **Or an environment variable.** Delete `DATABASE_SSL_CA` and add **`DATABASE_SSL_CA_PEM`**, pasting the whole certificate as its value (from `-----BEGIN CERTIFICATE-----` to `-----END CERTIFICATE-----`).

If neither is set correctly, the deploy log says so plainly, e.g. *"Configuration error: DATABASE_SSL_CA points to '/etc/secrets/ca.pem', but no file exists there…"*.

Then click **Deploy**. The deploy log should show:

```
Waiting for the database...
Database is ready.
Running upgrade  -> 0001, initial schema
Running upgrade 0001 -> 0002, add users session_version
Seeding users...
Starting: uvicorn app.main:app --host 0.0.0.0 --port 10000 ...
```

Open `https://<service-name>.onrender.com` and log in with `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD`.

## Environment variables

| Variable | Value on Render | Why |
|---|---|---|
| `APP_ENV` | `production` | Marks the session cookie `Secure` (HTTPS only) |
| `SECRET_KEY` | generated | Signs session cookies. Never reuse your local one. |
| `DATABASE_URL` | Aiven URL (above) | The database connection |
| `DATABASE_SSL_CA` | `/etc/secrets/ca.pem` | Enables verified TLS to Aiven (certificate as a Secret File) |
| `DATABASE_SSL_CA_PEM` | the certificate text | Alternative to `DATABASE_SSL_CA`: the certificate pasted into a variable |
| `SEED_ON_START` | `true` (then `false` if you like) | Loads sample data on start |
| `SEED_*_EMAIL` / `SEED_*_PASSWORD` | your choice | Sample accounts for the demo |
| `PORT` | set by Render | The app listens on it automatically |

## Notes and limits

- **Free plan sleep.** A free Render service sleeps after about 15 minutes without traffic. The first request after that takes around a minute while it wakes up. Open the site a minute before a demo.
- **After the first deploy** you may set `SEED_ON_START=false`. Seeding never overwrites data, but turning it off skips the step on each start.
- **Passwords changed in the app win.** Seeding skips accounts that already exist, so changing `SEED_*_PASSWORD` later does not reset an existing user. Use the Users page or My account instead.
- **Logs.** The Render **Logs** tab shows each request with its request ID. An error reference shown to a user (e.g. "quote reference abc123") can be searched for there.
- **Local development is unchanged.** Without `DATABASE_SSL_CA` the app connects without TLS, and without `PORT` it listens on 8000.
