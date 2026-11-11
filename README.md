# AI supported shoppig list Repo
- See [specification](specification.md)
- See [GH repo](https://github.com/CoderTobi/Studium_MSC_Prk_A2)
## Devcontainer Setup
- Install WSL 2
- Install Distro (I use Debian, but I guess Ubuntu is fine too)
- Install Docker Desktop in WSL mode [Download here](https://docs.docker.com/desktop/setup/install/windows-install/)
    - If you have problems when staring the container, maybe select the distro manually in Docker Desktop
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