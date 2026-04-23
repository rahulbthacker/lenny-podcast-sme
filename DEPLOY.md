# Deploying Lenny's Podcast SME

One-time setup for public deployment. Uses Vercel (frontend) + Railway (backend).
Budget: **$0–5/month** (Railway hobby plan) + API usage.

---

## Prerequisites

- GitHub account with this repo pushed up
- Vercel account (free) — [vercel.com](https://vercel.com)
- Railway account — [railway.app](https://railway.app)
- Anthropic API key (primary LLM)
- Gemini API key (failover) — optional but recommended

---

## 1. Backend — Railway

### 1a. Create the service
1. Sign in to Railway → **New Project** → **Deploy from GitHub repo**
2. Pick this repo; set the **root directory to `backend`**
3. Railway auto-detects Python from `requirements.txt` and uses the start command in `Procfile` (`uvicorn server:app --host 0.0.0.0 --port $PORT`)

### 1b. Set environment variables
In the Railway project → **Variables** tab, add:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your Anthropic key |
| `GEMINI_API_KEY` | your Gemini key (optional) |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` (or override) |
| `CORS_ORIGINS` | `https://your-frontend.vercel.app` (set after step 2 — tighten from `*`) |
| `IP_HASH_SALT` | a random string (generate: `python -c "import secrets; print(secrets.token_hex(16))"`) |

### 1c. Deploy
Push to `main` — Railway builds and deploys automatically. Note the backend URL: something like `https://lenny-podcast-sme-production.up.railway.app`.

### 1d. Verify
```
curl https://your-backend.up.railway.app/api/health
# expect: {"status":"ok","anthropic_key_set":true,"gemini_key_set":true}
```

---

## 2. Frontend — Vercel

### 2a. Create the project
1. Sign in to Vercel → **Add New Project** → **Import Git Repository**
2. Pick this repo; set **root directory to `frontend`**
3. Vercel auto-detects Next.js. Accept defaults.

### 2b. Set environment variable
In Vercel project settings → **Environment Variables**:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE` | `https://your-backend.up.railway.app` (from step 1c) |

### 2c. Deploy
Click **Deploy**. Vercel builds and publishes; note the URL, e.g. `https://lenny-sme.vercel.app`.

### 2d. Back-fill CORS
Return to Railway → Variables → set:
```
CORS_ORIGINS=https://lenny-sme.vercel.app
```
Redeploy the backend (Railway does this automatically on var change).

---

## 3. Smoke test

1. Visit `https://lenny-sme.vercel.app`
2. Ask a question → should stream an answer and show citations
3. Verify the conversation persists after refresh
4. Open a new incognito window → start a new chat → should be isolated (no shared history)

---

## 4. Abuse protection

- **Rate limit**: 30 requests/day per IP (hardcoded). Change in `backend/server.py` → `@limiter.limit("30/day")`. Returns 429 with a friendly message when exceeded.
- **CORS**: locked to your Vercel domain. Random origins get blocked by the browser.
- **API keys**: never exposed to the browser — all LLM calls originate from the backend.

---

## 5. Analytics

### Vercel Analytics (frontend)
Auto-enabled via `@vercel/analytics`. After deploy, Vercel dashboard → Analytics. Free tier: 2.5K events/month. Gives you visits, countries, referrers, devices.

### Backend logs (what users ask)
Written to `backend/logs/chat.jsonl` inside the Railway container. Each line:
```json
{"t":"2026-04-22T11:17Z","ip_hash":"f57d...","country":"IN","q":"...","mode":"strong","cites":6,"out_chars":1308,"latency_ms":5450}
```

To inspect on Railway:
```bash
railway logs              # stdout of the running container
railway shell              # open a shell inside; then: cat logs/chat.jsonl
```

For queries like "top 20 questions this week":
```bash
jq -r '.q' logs/chat.jsonl | sort | uniq -c | sort -rn | head -20
```

Upgrade paths:
- Pipe logs to a service like **Axiom**, **Logtail**, or **Better Stack** (free tiers) for a web dashboard
- Persist logs outside the container (Railway volumes or S3) so they survive redeploys

---

## 6. Ongoing maintenance

- Index is shipped in-repo at `backend/data/index/`. To refresh with new podcast episodes:
  ```bash
  cd backend && python -m indexing.build_index
  git add data/ && git commit -m "refresh index" && git push
  ```
  Railway redeploys; Vercel is unaffected.

- Monitor your Anthropic usage at [console.anthropic.com](https://console.anthropic.com) — set a spending cap to prevent surprises.

---

## Cost snapshot (Apr 2026)

| Item | Cost |
|---|---|
| Vercel Hobby (frontend) | $0 |
| Railway Hobby (backend) | ~$5/mo container-hours |
| Anthropic (Claude Haiku 4.5) | ~$0.008/query — $5 ≈ 625 queries |
| Gemini failover | $0 until you exceed free tier |
| **Total for a typical LinkedIn-driven demo** | **~$5–10/month** |
