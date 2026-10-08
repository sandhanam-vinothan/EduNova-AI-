# EduNova AI

React + Vite + Tailwind + FastAPI + Neon PostgreSQL + Gemini + Ollama + PDF.js.

## Local setup

1. Copy `.env.example` to `backend/.env`; set `SESSION_SECRET` and AI credentials.
2. `cd backend && python -m venv .venv` then activate it and `pip install -r requirements.txt`.
3. `uvicorn app:app --reload --port 8000`
4. In another terminal: `cd frontend && npm install && npm run dev`
5. Visit http://localhost:5173 and sign up. Upload the original textbook PDF through Textbook Reader.

## Neon

Set `DATABASE_URL` to Neon's PostgreSQL connection string. Tables are created at startup for development. For production schema migrations, review and apply migrations before changing the database schema.

## Render

Set Render service root to `backend`, build command `pip install -r requirements.txt && cd ../frontend && npm install && npm run build`, start `uvicorn app:app --host 0.0.0.0 --port $PORT`. Add secrets in Render dashboard. Set `CORS_ORIGINS` to your actual URL.

**Important:** Render ephemeral disks cannot reliably persist uploaded PDFs. Put the textbook in `backend/data/textbook.pdf` in a private deployment or configure persistent disk and `PDF_PATH`. Do not commit a copyrighted textbook unless authorized. For public deployment, provide persistent PDF storage and run indexing against that file. Ollama must be remotely reachable from Render.

## Scope and limitations

This is an application starter with real authentication, persisted user records, provider calls, PDF upload/index/search and reader controls. The 360-page PDF is not included. Chat responses use non-streaming provider calls. The reader text layer uses positioned PDF text but may not precisely align with all font transforms. Search highlighting is approximate, not robust substring geometry. Quiz questions are rudimentary textbook-derived recognition questions, not curated exam MCQs. Revision/flashcards are generated in AI chat. The backend does not yet serve the compiled React build: use a separate Render static site for `frontend/dist` with API proxy configured, or implement static mounting before deploying as one service. Production deployment, Neon integration, and AI endpoint responses have not been verified with live credentials. Avoid exposing the PDF upload endpoint to arbitrary students in production; add an admin role and storage quotas.

The backend also serves the compiled React frontend from `frontend/dist` when the build exists, so the provided Render configuration supports a single web service. This mounting is registered after API routes.


## Included original textbook
The 360-page Tamil Nadu Higher Secondary Second Year Computer Science English Medium PDF (2024 reprint) is bundled at `backend/data/textbook.pdf`. The backend indexes it automatically on startup when the pages table is empty. PDF page 7 corresponds to printed page 1. On Render, keep the PDF committed in Git, since runtime disk storage is ephemeral.
