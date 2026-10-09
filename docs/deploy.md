# Deploy (Phase 10)

## Run with Docker on any computer

```bash
docker build -t chemready .
docker run -p 7860:7860 \
  -e CHEMREADY_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  -e CHEMREADY_LLM_PROVIDER=rules -e CHEMREADY_DEMO=true \
  -v chemready-data:/data chemready
# open http://localhost:7860  (demo login: demo@chemready.app / demo1234)
```

| Variable | Meaning |
| --- | --- |
| `CHEMREADY_SECRET_KEY` | **Required.** 32+ random characters; signs session cookies |
| `CHEMREADY_LLM_PROVIDER` | `rules` (demo, no AI), `ollama` or `gemini` |
| `CHEMREADY_DEMO=true` | Create the demo account with fictional SDS files at start-up |
| `-v chemready-data:/data` | Keeps the database and uploads when the container restarts |

The image runs as a normal user (uid 1000), defaults to production mode (secure
cookies, JSON logs) and refuses to start without a secret key.

## Free public demo on Hugging Face Spaces

Hugging Face Spaces can run a Docker app for free on a CPU machine. Check the
current free hardware and limits on the Spaces pricing page when you start; they
change. Free Spaces do not keep files after a restart, which is fine for the demo
because it rebuilds the demo account each time.

1. Create an account at huggingface.co, then **New Space** → name `chemready` →
   SDK **Docker** → template **Blank** → **Public**.
2. In the Space **Settings → Variables and secrets** add:
   - secret `CHEMREADY_SECRET_KEY` = output of `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
   - variable `CHEMREADY_LLM_PROVIDER` = `rules`
   - variable `CHEMREADY_DEMO` = `true`
3. Push the app to the Space (the Space needs its own README with the settings header):

```bash
git clone https://huggingface.co/spaces/<your-username>/chemready hf-space
cp -r Dockerfile .dockerignore pyproject.toml uv.lock src hf-space/
cp deploy/huggingface/README.md hf-space/README.md
cd hf-space && git add . && git commit -m "Deploy ChemReady demo" && git push
```

4. Wait for the build (a few minutes), open the Space and sign in with the demo account.

### Rules for the public demo

- **Fictional data only.** Never upload a factory's files to a public Space.
- Keep `CHEMREADY_LLM_PROVIDER=rules`. If you switch the demo to Gemini, use the free
  tier only with public SDS files, and set a spending limit first.
- A pilot with real factory files needs a private deployment: a local machine or a
  private server running Ollama (`CHEMREADY_LLM_PROVIDER=ollama`), with a volume for `/data`.

## Before a real pilot

- [ ] Private deployment with Ollama, or a paid AI tier with the factory's written consent
- [ ] Connect an email service for password reset links (today they are written to the log)
- [ ] Regular backups of `/data` (SQLite database and uploaded PDFs)
- [ ] HTTPS in front of the app (Spaces and most hosts do this for you)
