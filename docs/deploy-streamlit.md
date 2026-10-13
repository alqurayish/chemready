# Deploy on Streamlit Community Cloud

`streamlit_app.py` is a Streamlit front end for the same ChemReady engine (parsing,
extraction, validation, review, inventory, flags, Excel export). Streamlit Community
Cloud runs it for free from your GitHub repository.

## Files it uses

| File | Why |
| --- | --- |
| `streamlit_app.py` | The app (entry point) |
| `requirements.txt` | Tells Streamlit Cloud to install this package (`.`) and its dependencies |
| `.streamlit/config.toml` | Theme (white background, ChemReady blue) and a 20 MB upload limit |

## Steps

1. Make sure the code is on GitHub (branch `main`, or the branch you choose below).
2. Go to **share.streamlit.io** and sign in with **GitHub**. Allow Streamlit to read your repositories.
3. Click **Create app** → **Deploy a public app from GitHub** (the wording may differ slightly).
4. Fill in:
   - **Repository:** `alqurayish/chemready`
   - **Branch:** `main` (or `claude/intelligent-davinci-ifpa0v` until you merge)
   - **Main file path:** `streamlit_app.py`
   - **App URL:** choose a name, for example `chemready`
5. Open **Advanced settings**:
   - **Python version:** **3.12** (required: the code uses Python 3.12 features)
   - **Secrets:** paste
     ```toml
     CHEMREADY_LLM_PROVIDER = "rules"
     ```
6. Click **Deploy**. The first build takes a few minutes. Watch the log on the right.
7. Open the app, click **Try the demo** (`demo@chemready.app` / `demo1234`).

## Optional: Gemini for public SDS files

In the app's **Settings → Secrets**:

```toml
CHEMREADY_LLM_PROVIDER = "gemini"
CHEMREADY_GEMINI_API_KEY = "your key from aistudio.google.com"
CHEMREADY_GEMINI_MODEL = "a current free-tier model name from Google's pricing page"
CHEMREADY_GEMINI_FREE_TIER = "true"
```

With the free tier, private factory files are refused automatically. Only tick
"public SDS" uploads.

## Good to know

- **Public app:** anyone with the link can open it. Use fictional or public SDS files only.
- **Storage resets:** Community Cloud does not keep files when the app restarts or sleeps.
  The demo account is recreated on start; anything else uploaded is lost. That is fine
  for a demo; a real pilot needs a private deployment (see `docs/deploy.md`).
- **Sleeping:** free apps go to sleep after a period without visitors; the next visitor
  wakes them up (takes a minute).
- **Updates:** every push to the chosen branch redeploys the app automatically.

## If the build fails

| Log message | Fix |
| --- | --- |
| `requires a different Python` / syntax error at `def ...[T` | Set Python **3.12** in Advanced settings (delete and redeploy if needed) |
| `ModuleNotFoundError: chemready` | Check `requirements.txt` contains a line with `.` and is in the repository root |
| `Settings are not valid` | Check the secrets: names start with `CHEMREADY_`, values in quotes |
