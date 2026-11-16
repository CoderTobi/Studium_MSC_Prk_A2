# AI supported shoppig list Repo
- See [specification](specification.md)
- See [backend](backend/README.md) for setup, configuration and running the backend
- See [frontend](frontend/README.md) for setup, configuration and running the frontend
- See [GH repo](https://github.com/CoderTobi/Studium_MSC_Prk_A2)
## Deployment with Docker Compose
- Ollama runs on the host OS, not in Docker
    - Pull the model: `ollama pull <model>`
    - On Linux, start it with `OLLAMA_HOST=0.0.0.0` so the backend container can reach it
- Create `backend/.env` and `frontend/.env` from their `.env.example`
- Put the Firestore service account key at `backend/secrets/firebase-service-account.json` and make it readable (`chmod 644`), the backend container runs as uid 10001
- Optional: create `.env` from [.env.example](.env.example) to set ports and the URLs the browser uses
    - Needed whenever the app is not opened via `localhost`, e.g. on a home server: `FRONTEND_ORIGIN=http://homeserver:3000` and `BACKEND_URL=http://homeserver:8000`
- Start: `docker compose up -d --build`
- Frontend: http://localhost:3000, backend: http://localhost:8000
## Devcontainer Setup
- Install WSL 2
- Install Distro (I use Debian, but I guess Ubuntu is fine too)
- Update the distro `sudo apt update` und `sudo apt upgrade`
- Install extension in VS Code `ms-vscode-remote.vscode-remote-extensionpack`
- Install Docker Desktop in WSL mode [Download here](https://docs.docker.com/desktop/setup/install/windows-install/)
    - If you have problems when staring the container, maybe select the distro manually in Docker Desktop
        - The Setting is called `Enable integration with additional distros`
        - There select your distro
- Install git if needed `sudo apt install git`
- Clone the repository in WSL `git clone https://github.com/CoderTobi/Studium_MSC_Prk_A2.git`
- Switch to the folder `cd Studium_MSC_Prk_A2`
- Install wget if needed `sudo apt install wget`
- Open VS Code `code .`
- Reopen in Dev Container:
    - Crtl + Shift + P
    - "Dev Containers: Reopen in Container"
### Troubleshooting
- I have rebooted my Windows pc and now I get an error when opening VSCode in the devcontainer
    - It starts docker desktop automatically, but it takes too long
    - Start Docker Desktop manually and wait for the engine to start before you open VSCode