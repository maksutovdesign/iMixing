# Deploy to Render

This repository includes a first deployment path for the MIDI web service on Render.

## What is already prepared

- [render.yaml](../render.yaml)
- [.python-version](../.python-version)

The service definition uses:

- native Python runtime
- `pip install .` as the build command
- `imixing-midi-web` as the start command
- `/health` as the health-check path

## Local smoke check before deploy

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
PORT=8010 imixing-midi-web
```

Open `http://127.0.0.1:8010`.

## Deploy with Render Blueprint

1. Push the repository to GitHub, GitLab, or Bitbucket.
2. In Render, choose `New` -> `Blueprint`.
3. Connect the repository.
4. Keep the default Blueprint path if `render.yaml` is in the repo root.
5. Review the generated service plan and deploy.
6. Wait until the `/health` check passes.
7. Open the assigned `onrender.com` URL.

## Manual fallback in Render Dashboard

If you do not want to use Blueprints yet, create a `Web Service` manually with:

- Runtime: `Python`
- Build Command: `pip install .`
- Start Command: `imixing-midi-web`
- Health Check Path: `/health`

## MVP notes

- The current app is stateless, so no database is required.
- Free Render web services can spin down after inactivity.
- The first public deploy is best used as an MVP validation target, not as the final production architecture.
