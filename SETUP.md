# Agent Dorcas 1 — Nia's Rhythm Room

Agent Dorcas 1 makes and uploads an original kids' learning song video every **Monday, Wednesday and Friday**. You don't need to do anything once it's set up.

| Step | Tool |
|---|---|
| Picks a topic it hasn't used yet, then writes the lyrics, shot list, title, description and tags | Claude API |
| Checks the lyrics for copyright, age-fit and learning value (it rewrites them if they fail) | Claude API |
| Makes the song with a child lead singer | ElevenLabs Music API |
| Draws each scene with the Nia character | Gemini image model |
| Animates 4 key scenes (8 s each) | Veo 3.1 (the model behind Google Flow) |
| Edits the 1080p video with sing-along lyrics, a corner logo and an end card | ffmpeg |
| Makes the thumbnail | Gemini art + a template |
| Checks the frames and thumbnail for problems (if they fail, the video uploads as **private**) | Claude vision |
| Uploads the video as Made for Kids, with the AI label, scheduled to go public at 4 pm ET | YouTube Data API |

Runs on GitHub Actions (free), so your computer can be off.

---

## One-time setup (about 30 minutes, then never again)

### 1. API keys
| Secret | Where to get it | Rough monthly cost at 13 videos |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API keys | ~$3–8 |
| `ELEVENLABS_API_KEY` | elevenlabs.io → a paid plan that allows commercial use of music → API keys | ~$22–99 depending on plan |
| `GEMINI_API_KEY` | aistudio.google.com → Get API key (billing turned on) | Veo is the big cost: roughly $5–13 per video at 4 clips (≈ $65–165/mo, check ai.google.dev/pricing), plus images ≈ $1–2/video |

Set `VEO_CLIPS` to control cost: 0 means stills with slow camera moves only (≈ $25/mo total), and 8 means more animation.

### 2. YouTube API access
✅ **Already done in Google Cloud:** project **Dorcas1**, YouTube Data API v3 turned on, sign-in screen "Agent Dorcas 1" (External), Desktop app login "Agent Dorcas 1", and your Google account added as a test user. You downloaded the client ID and secret as a JSON file.

What's left:
1. On your computer, run `pip install requests`, then:
   `python scripts/get_refresh_token.py CLIENT_ID CLIENT_SECRET` (both are in the JSON file you downloaded).
   Sign in, choose the **Nia's Rhythm Room** channel, and click **Allow**. You'll see an "unverified app" warning; click *Advanced → Go to Agent Dorcas 1*, because it's your own app. Copy the token it prints.
2. **Switch the app to production** so the token doesn't expire after 7 days. Do this after GitHub Pages is live (step 3.2):
   Google Cloud → Google Auth Platform → **Branding**: add the home page `https://vince16-crypto.github.io/agent-dorcas-1/` and the privacy policy `https://vince16-crypto.github.io/agent-dorcas-1/privacy.html`, and add `vince16-crypto.github.io` under Authorized domains. Then go to **Audience → Publish app**. After that, run step 1 again to get a token that doesn't expire.
3. **Important:** fill in the **YouTube API Services audit form** (support.google.com/youtube/contact/yt_api_form). Google keeps videos uploaded through a new, unaudited API project **private** until the project passes the audit, which usually takes 1–3 weeks. Until then Dorcas still uploads every video on schedule, but they stay private.
4. In YouTube Studio → Settings → Channel → Feature eligibility, **verify your phone number** so custom thumbnails work.

### 3. GitHub
1. Create a repo and upload this folder to it. On a free GitHub account the repo has to be **public** for step 2 to work. Your keys stay safe either way, because they go in encrypted Secrets and never in the code.
2. Go to Settings → **Pages** → Source: *Deploy from a branch* → `main` / `docs`. This publishes the home page and privacy policy Google needs.
3. Go to Settings → Secrets and variables → Actions and add these secrets:
   `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
   You can also add these *variables*: `VEO_CLIPS` (default 4), `SONG_SECONDS` (default 120), `YT_PLAYLIST_ID`.
4. Go to Actions → **Agent Dorcas 1** → Run workflow:
   - Run it with `dry-run` first. This checks the build without any paid services and doesn't upload.
   - Run it with `branding` next. This pushes the banner, channel description and keywords to the channel.
   - Run it with `run` to make and upload your first real video.
   After that it runs on its own every Mon/Wed/Fri. Each run's video and plan are kept as a downloadable file for 14 days.

### 4. YouTube Studio
✅ Already done: name **Nia's Rhythm Room**, handle **@NiasRhythmRoom**, profile picture, banner, description, keywords, and the channel set to "made for kids."

---

## Files
- `brand/`: the Nia mascot (original art), profile picture, 2560×1440 banner, and `brand.json` (name, channel description, keywords, title format, palette)
- `data/topics.json`: 63 learning topics. Add more whenever you like. `data/history.json` records past uploads so topics aren't repeated.
- `dorcas/`: the agent (`main.py` runs everything)
- `.github/workflows/agent-dorcas-1.yml`: the Mon/Wed/Fri schedule
- `docs/`: the public home page and privacy policy, served by GitHub Pages

## About Suno and Google Flow
Suno and Flow don't have official APIs, so they can't run without someone clicking through them. Dorcas uses the **Veo** model (the one Flow runs on) through Google's official Gemini API, and uses ElevenLabs for music because it has a commercial API.
