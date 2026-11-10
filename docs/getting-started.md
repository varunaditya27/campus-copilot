<div align="center">

# Getting started

Run Campus Copilot on your own machine, then optionally deploy it.

</div>

You need a [Groq](https://console.groq.com/docs/overview) API key for the language model. The tests do not need one.

## With Docker

This is the quickest way. It starts everything: the backend, the frontend, PostgreSQL, Redis and the two background job services.

```bash
cp .env.example .env
```

Open `.env` and set `POSTGRES_PASSWORD`, `JWT_SECRET` (make one with `openssl rand -hex 32`) and `GROQ_API_KEY`. Then:

```bash
docker compose up -d --build
docker compose exec backend python -m app.cli create-user --role admin
```

Open <http://localhost:3000>. The first start downloads the search models (about 170 MB) while a one-shot `ingest` service builds the knowledge base. After that, starts are fast.

Students register on the sign-up page with a student id and name from the sample roster, for example `1RV23IS101` and `Aarav Sharma` (`data/students.json` lists all 20). Faculty, staff and admin accounts cannot be made on the sign-up page, because anyone could make themselves an admin. They are created with the `create-user` command above.

`make help` lists the everyday commands.

## By hand

You need Python 3.14 and Node.js 22.

**Backend**

```bash
cd backend
python -m venv venv
source venv/bin/activate          # on Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then add your GROQ_API_KEY
alembic upgrade head              # creates the SQLite database, backend/campus.db
python -m app.db.seed             # loads the sample data from data/
python -m app.rag.ingest          # builds the knowledge base from knowledge/
uvicorn app.main:app --reload --port 8000
```

Check that it is running with `curl http://localhost:8000/health`.

**Frontend**, in another terminal

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open <http://localhost:3000>.

The sample data is fictional. Its dates are moved to the day you load it: the first event is tomorrow, and the library loans, appointment slots, placement drives and exams are placed around today. Loading again does not move anything, because only empty tables are filled.

### Sign-in buttons for local use

To get "Fill in demo student" and "Fill in demo admin" buttons on the sign-in page, put the accounts in `frontend/.env.local`:

```bash
NEXT_PUBLIC_DEMO_STUDENT_EMAIL=
NEXT_PUBLIC_DEMO_STUDENT_PASSWORD=
NEXT_PUBLIC_DEMO_ADMIN_EMAIL=
NEXT_PUBLIC_DEMO_ADMIN_PASSWORD=
```

Use them for local work only. Anything starting with `NEXT_PUBLIC_` is built into the page and can be read by every visitor, so never set these on a deployed site.

## Notifications and background jobs

Push notifications are off until you give the server a key pair, which identifies it to the browsers' push services.

```bash
make vapid-keys        # with the Docker stack running
# or, by hand: python -m app.cli create-vapid-keys
```

Set the two keys it prints, plus a contact for the push services, in the backend's settings:

```bash
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:admin@your-college.example
```

Then restart the backend. Students can turn notifications on from their profile page. Browsers allow push on `localhost`; any other address needs HTTPS. The service worker only exists in a production build (`npm run build`), so notifications cannot be tried with `npm run dev`.

The Docker stack already runs the two jobs: `celery-worker` does them and `celery-beat` starts them on time. Run exactly one `celery-beat`, or every message is sent twice. Without Docker, set `REDIS_URL` and run:

```bash
cd backend
celery -A app.worker:celery_app worker
celery -A app.worker:celery_app beat
```

## Tests

```bash
make test
```

This runs the backend tests (`pytest`) and the frontend checks (type check, lint and component tests). They need no API key. The first backend run downloads the search models (about 170 MB), so it needs a network once. `make test` expects the Python environment in `backend/venv`, as made above, and the frontend dependencies installed.

## Deploying

`docker-compose.prod.yml` is the production version of the stack. It pulls the images that the *Build and publish images* workflow pushes to the GitHub Container Registry, and puts Caddy in front. Caddy gets and renews a certificate for your domain, redirects HTTP to HTTPS, and serves the pages and the API from one address. Only ports 80 and 443 are published.

```bash
cp .env.example .env              # set DOMAIN, POSTGRES_PASSWORD and IMAGE_PREFIX
mkdir -p secrets
openssl rand -hex 32 > secrets/jwt_secret
printf '%s' "$GROQ_KEY" > secrets/groq_api_key
chmod 600 secrets/*
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

- **Secrets stay in `./secrets`**, which is git-ignored, and not in `.env`. The files must be readable by the container's user (uid 1000). To rotate one, replace its file and recreate the backend container.
- **The domain must already point at the machine**, because Caddy needs ports 80 and 443 to get a certificate.
- **The frontend image has the API address built in.** Set the repository variable `NEXT_PUBLIC_API_BASE_URL` to `https://<your domain>` before the first publish.
- **Push in production** needs the private key in `secrets/vapid_private_key`, and `VAPID_PRIVATE_KEY_FILE=/secrets/vapid_private_key`, `VAPID_PUBLIC_KEY` and `VAPID_SUBJECT` in `.env`. Without them push stays off and everything else works.
- **Scripts that call the admin endpoints** use an API key from `docker compose exec backend python -m app.cli create-admin-key`.

The full list of settings, and what the security measures protect and do not protect, are in the [backend documentation](../backend/README.md).
