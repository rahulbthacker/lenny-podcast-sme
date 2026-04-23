# Lenny's Podcast SME

An AI subject-matter expert trained on every episode of [Lenny Rachitsky's podcast](https://www.lennysnewsletter.com/podcast). Ask a question about product management, growth, or startups — get a grounded, cited answer with the exact episodes, guests, and timestamps the answer was drawn from.

> **Unofficial fan project.** Not affiliated with Lenny Rachitsky or Lenny's Newsletter.

Built by [Rahul Thacker](https://www.linkedin.com/in/rahulthacker/).

---

## Try it

**🔗 Live demo**: _add your Vercel URL here after deploy_

The live demo is rate-limited (30 questions per day per user). If you want to ask more, keep reading — you can run your own copy with your own API key.

---

## What makes it different from asking ChatGPT

- **Grounded in transcripts, not web search or general knowledge.** Every answer cites specific episodes, guests, and timestamps.
- **Scope-aware.** Ask about risotto and it politely redirects; ask about PM career transitions and it gives a tactical answer with sources.
- **Multi-episode coverage.** If a guest (Marty Cagan, Shreyas Doshi, April Dunford, …) has multiple episodes, relevant ones all surface.
- **Relevance-driven citations.** Sharp questions return 1–3 source cards; broad questions return up to 8. No arbitrary fixed count.

---

## Architecture

```
Browser (Next.js frontend, localStorage chat history)
    ↓ HTTPS
Backend (FastAPI)
    ├─ Retriever (BGE embeddings + LanceDB, ~7k chunks)
    ├─ Scope classifier (domain similarity + guest detection)
    └─ Answer generator (Claude Haiku 4.5 primary, Gemini Flash failover)
```

- **Frontend**: Next.js 14 + Tailwind, multi-chat with sidebar, streaming answers, citation tooltips
- **Backend**: FastAPI + LanceDB + `fastembed` (BGE-small for local embeddings)
- **LLMs**: Anthropic Claude (primary) with Gemini failover on rate limits / outages
- **Storage**: chats persist in your browser's localStorage (no database, no accounts)

---

## Run it yourself

### 0. Prerequisites

- **macOS or Linux** (Windows via WSL works)
- **Python 3.11 or 3.12** — recommended; the code runs on 3.14 too but some scientific packages lag on the newest Python
- **Node.js 18+** and **npm**
- **An Anthropic API key** — [create one here](https://console.anthropic.com/) (~$0.008 per question on Haiku 4.5)
- **Optional: a Gemini API key** — [Google AI Studio](https://aistudio.google.com/apikey), used as failover when Claude is rate-limited
- **Podcast transcripts** — see ["Getting the transcripts"](#getting-the-transcripts) below

### 1. Clone

```bash
git clone https://github.com/rahulbthacker/lenny-podcast-sme.git
cd lenny-podcast-sme
```

### 2. Getting the transcripts

**The transcripts themselves are not distributed with this repo** — they're not ours to redistribute. You need to supply your own copy.

Place `.txt` transcript files — one per episode — in `backend/data/transcripts/`. Each file should follow this format (speaker + timestamp + spoken text):

```
Lenny (00:00:00):
You were basically the 10th engineer at Facebook...

Andrew Bosworth (00:00:07):
I didn't sleep for more than four hours at a time...
```

The filename (without `.txt`) should be the guest's name or a short identifier, e.g., `Boz.txt`, `Shreyas Doshi.txt`, `Shreyas Doshi Live.txt`. Repeat-guest suffixes like `Live` or `2.0` are preserved for disambiguation.

> Sources for podcast transcripts: services like [Deepgram](https://deepgram.com/), [AssemblyAI](https://www.assemblyai.com/), [Otter.ai](https://otter.ai/), or community-maintained archives. If you find Lenny's podcast distributed as an archive anywhere, check the license before using it in a publicly-deployed service.

### 3. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY and (optionally) GEMINI_API_KEY
```

### 4. Build the index

Fetches episode metadata from the Lenny's Podcast RSS feed, parses transcripts, matches filenames to RSS episodes, chunks + embeds (~5–20 min depending on transcript count and CPU):

```bash
python -m indexing.build_index
```

You should see output about fetching episodes, parsing transcripts, matching, and finally encoding chunks.

### 5. Frontend setup

```bash
cd ../frontend
npm install
cp .env.example .env.local
# .env.local defaults are fine for local dev
```

### 6. Run

Two terminals:

```bash
# Terminal A — backend
cd backend && source .venv/bin/activate && python server.py

# Terminal B — frontend
cd frontend && npm run dev
```

Open **http://localhost:3000** and ask away.

---

## Deploy your own public instance

See [`DEPLOY.md`](./DEPLOY.md) for the full walkthrough. Short version:

- **Frontend** → Vercel (free tier)
- **Backend** → Railway (~$5/month)
- **Transcripts + index** → ship with your deploy (via Railway Volumes or a separate private data repo — do NOT commit them to this public repo)
- **API keys** → env vars on Railway, never in the repo
- Per-IP rate limit (30/day default) and CORS locked to your frontend URL

---

## Project layout

```
backend/
  indexing/              # one-time pipeline (RSS → parse → match → embed)
  data/                  # (gitignored) transcripts + LanceDB index live here
  answer.py              # Claude primary / Gemini failover streaming
  retrieval.py           # vector search + guest-aware boost + scope classifier
  server.py              # FastAPI with NDJSON streaming + rate limiting + logging
  logging_utils.py       # hashed-IP structured logs
frontend/
  app/                   # Next.js App Router
  components/
    Chat.tsx             # main chat UI with streaming + citation chips
    Sidebar.tsx          # multi-chat history (localStorage)
    CitationCard.tsx
  hooks/useChats.ts      # chat state management
  lib/chats.ts           # localStorage helpers
DEPLOY.md                # step-by-step deployment guide
```

---

## FAQ

**Q: Is the live demo always available?**
A: Yes, as long as the Railway/Vercel services are running and within their API quotas. Each visitor gets 30 questions/day.

**Q: What happens if I hit the 30/day limit?**
A: You'll see a friendly "come back tomorrow" message. The limit is per-IP and resets on a 24-hour rolling window. If you want unlimited use, [fork the repo](#run-it-yourself) and run it locally with your own key.

**Q: Why not just ask ChatGPT/Claude the same question?**
A: Those models are trained on general knowledge and may paraphrase Lenny's podcast from memory — with hallucinations and without citations. This tool retrieves the exact podcast chunks and asks an LLM to answer *only* from those, giving you source-linked answers you can verify.

**Q: Can I use this for other podcasts?**
A: Yes. Swap the RSS feed URL in `backend/indexing/parse_rss.py`, drop your transcripts into `backend/data/transcripts/`, rebuild the index. The rest is podcast-agnostic.

---

## License

MIT for the code. Podcast content (transcripts, episode metadata, audio) belongs to Lenny Rachitsky and his podcast's contributors — not included in this repo and not mine to relicense.
