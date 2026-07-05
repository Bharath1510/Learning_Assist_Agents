# Study Notes Generator 📖

Turn any topic into clear, exam-ready study notes you'll actually want to read.

Type what you're studying (e.g. *Photosynthesis*, *TCP handshake*, *French Revolution*), and an AI study crew researches it and writes structured notes — an overview, key concepts, detailed notes, examples, and quick revision questions. Read them on the page in a friendly handwriting style, switch the difficulty level, save them as a Word doc or PDF, and keep your own sticky notes on a per-topic notepad.

> A learning / portfolio project built to run entirely on **free** Google AI Studio (Gemini) and Serper tiers.

## Features

- **Topic → study notes** using Gemini-powered agents (a researcher and a notes author)
- **Three difficulty levels** — Easy, Medium, and In-depth, produced on demand by a third "adapter" agent that rewrites the notes without re-researching. Each level is cached in MongoDB, so switching back to one you've seen is instant (no extra API call)
- **Study-friendly UI** — notebook paper look with a handwriting font, plus an "Easy read" toggle for a clean sans-serif
- **Read on the site** — notes render right in the page
- **Download as Word** (`.docx`) or **PDF** (via your browser's print-to-PDF)
- **Recent notes** — past notes are listed and reopenable; delete any of them (with a confirm) to remove them from the list and disk
- **Per-note sticky notepad** — jot quick notes on the topic you're viewing, edit inline, delete; scoped to each note and saved to MongoDB
- **Live progress** — see each stage (research → writing → export) as it happens

## Tech stack

- **Backend:** Python + Starlette + Uvicorn
- **AI:** CrewAI with Google Gemini (`gemini-2.5-flash`, via the native `google-genai` provider) + Serper web search
- **Storage:** MongoDB (browse it with MongoDB Compass)
- **Frontend:** plain HTML/CSS/JS (no framework)

## MongoDB layout

Everything is stored in one easy-to-read database. Open **MongoDB Compass** and connect to `mongodb://localhost:27017` to see:

```
study_notes_app            (database)
├── study_notes            generated notes (topic, status, stages, per-level file paths)
└── sticky_notes           notepad notes, each linked to a note via note_id (text, color, timestamps)
```

Failed jobs stay in `study_notes` (with their `error` field) for debugging, but are hidden from the "Recent notes" list.

## Setup

> ⚠️ Requires **Python 3.10–3.13** — CrewAI does not support 3.14 yet. If you clone this
> fresh, create your own `.venv` as below.

1. **Install MongoDB Community Server** and make sure the service is running (`mongod` on `localhost:27017`). MongoDB Compass is only a GUI client — it connects to that same server but does not provide one.

2. **Create a virtual environment and install dependencies:**

   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Set your keys.** Copy `.env.example` to `.env` and fill in `GEMINI_API_KEY` (free from Google AI Studio) and `SERPER_API_KEY` (free from serper.dev).

## Run

```powershell
.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>, type a topic, and click **Make my notes**.

You can also generate notes from the command line:

```powershell
.venv\Scripts\python research_crew.py
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | The web app |
| `POST` | `/api/reports` | Start a notes job — body: `{"topic": "..."}` |
| `GET` | `/api/reports` | List recent notes (failed jobs excluded) |
| `GET` | `/api/reports/{id}` | Poll a job; returns markdown + rendered HTML when done |
| `POST` | `/api/reports/{id}/level` | Switch/generate a difficulty level — body: `{"level": "easy"\|"medium"\|"high"}` |
| `DELETE` | `/api/reports/{id}` | Delete a note (removes its files from disk too) |
| `GET` | `/api/reports/{id}/download` | Download the Word document for the active level |
| `GET` | `/api/stickies?note_id={id}` | List sticky notes for a note |
| `POST` | `/api/stickies` | Create a sticky — body: `{"text": "...", "color": "yellow", "note_id": "..."}` |
| `PUT` | `/api/stickies/{id}` | Update a sticky's text/color |
| `DELETE` | `/api/stickies/{id}` | Delete a sticky |

Generated `.md` and `.docx` files are saved under `reports/` with timestamped names.

## Later: MongoDB Atlas

To move off your local machine, create a free Atlas cluster and set `MONGODB_URI`
in `.env` to its connection string. No code changes needed.

## Roadmap / future scope

Planned next, built in phases (each stays scoped to a specific note):

1. **🔊 Read aloud** — a button to have any note read out using the browser's built-in
   speech (free, offline, no server cost).
2. **🎧 Podcast agent** — a short two-host audio conversation that explains the topic, so
   you can learn by listening. Generated in the background and cached.
3. **🎭 Emotional narration** — expressive, natural-sounding voice-over of the notes, built
   on Gemini TTS behind a swappable engine so a local open-source model can drop in later.
4. **🖊️ Highlight & ask** — select a phrase or paragraph and ask a question about it; an agent
   answers using the note as context. Questions and highlights are saved per note.
5. **🗄️ Storage upgrade** — move note text into the database and generated audio into
   MongoDB GridFS (with a clean path to cloud object storage), replacing local files.

Further ideas: flashcard / quiz mode from the revision questions, search across notes,
retry/backoff for Gemini rate limits, and user accounts.

> Note: free-tier Gemini audio is great for a demo but isn't licensed for commercial
> resale — that would need paid Google Cloud billing.
