# EduNova AI: GitHub → Neon → Render (no local installs)

## 1. GitHub
Open https://github.com/sandhanam-vinothan/EduNova-AI- and use **Add file → Upload files**. Upload the contents of this extracted folder, not the enclosing folder. GitHub browser upload may limit file counts and file size; use GitHub Desktop or GitHub web editor if necessary. Do not upload `.env`, `.venv`, or `node_modules`.

**Textbook permission:** The bundled textbook is a Government of Tamil Nadu publication. Check redistribution/hosting permissions before uploading to a public GitHub repository. If not authorized, remove `backend/data/textbook.pdf` from the public repo and configure separately licensed storage; the reader cannot work until the PDF is available to the deployed server.

## 2. Neon
At https://console.neon.tech create a project named `edunova-ai`, choose a region near your users, and copy the PostgreSQL connection string (prefer pooled URL with `sslmode=require`). Never post the URL publicly. No manual SQL table creation needed for this initial schema: SQLAlchemy creates tables on first app start. Schema changes later require migrations.

## 3. Render
At https://dashboard.render.com choose **New → Blueprint** and connect the GitHub repository. The root `render.yaml` provisions a Docker web service. Set `DATABASE_URL` to the Neon URL and `GEMINI_API_KEY` to your Gemini key as secret environment values. `SESSION_SECRET` is generated. Keep `AI_PROVIDER=gemini` until a reachable Ollama service exists. Leave `OLLAMA_BASE_URL` blank unless it is an externally reachable Ollama endpoint. Deploy.

Open `https://YOUR-RENDER-SERVICE.onrender.com/api/health` and verify `status=ok` and `pdf=true`. Open `/api/book/pages` and verify `count=360` (initial indexing can take time). Then open the root URL, sign up, log in, search for a book sentence, and test Gemini chat.

## 4. Persistence and storage
Neon stores accounts, chat history, bookmarks, and indexed page text; Render's ephemeral filesystem does not store persistent uploads. The bundled PDF is baked into the Docker image, so it remains available across redeploys. If you need larger or user-uploaded PDF storage, configure an object store (e.g. S3-compatible bucket) and adapt the upload/download handlers; increasing Neon's database capacity does not increase Render's disk capacity.

## 5. Production cautions
This is a starter, not a verified complete production release. It has no automated migrations, rate limiting, password reset, robust quiz generation, or admin-only textbook management. Textbook upload is disabled by default to prevent arbitrary student replacement of the shared PDF. The API health check does not prove Gemini, Neon, or Ollama are functioning; test each separately. Verify npm security advisories before production launch.
