# AI supported shoppig list
- Users can add items to the sopping list and remove them
- In a prompt users can tell an AI what they want to eat. 
    - The AI should then offer recommended items for the shopping list.
    - Users can accept these items and add them to their existing shopping list or discard them.
    - The recommendations should be recognizable as such
    - There should be a note that AI may make mistakes
- We do not plan to have multiple shopping lists
- Before they can use the app, they must authenticate first

## Frontend
- The Web App should have a valid Impressum
- The Web should have a responsive UI

## Backend
- The items should be stored on the backend inside the Database
- users should only be able to see their own items and never those of other peoples
- users should only be able to use the backend (manage items, process prompts) after they have authenticated

## AI communication
- There must not be any direct communication between ollama and the Frontend
- All communication between the frontend and ollama must run through the backend
- The backend is the only one allowed to communicate with ollama
- The backend must check the prompt first
    - Check for prompt injection
    - Constrain the length of the prompt
- The backend must validate and parse the response of model into a consitent form
    - For example it should limit the length of the output
    - It must make sure that no arbitrary response from the model is send back to provent abuse
- The backend must allways respond with a correctly formated json even if something went wrong or the ai returned bullshit
    - There should be defined responses for error cases like invalid response, invalid prompt, timeout, etc.
- Every user must have a Rate Limit

## Configuration
- The frontend should have configuration options for:
    - The URL of the Backend
- The backend should have configuration options for:
    - The URL of the Ollama Server
    - Model to use

## Logging
- The Backend should log which model was used and how many tokens it burned
- The Backend should not log the prompt or response by default

## Tech Stack
- keep dependecies as low as possible
### Frontend
- Sveltekit
- Typescript
- Tailwind CSS
### Backend
- Python
    - Use some kind of dependecy tracking for easy creation of venv
### Authentication
- Firebase Authentication
### DB
- Firestore
### Containerisation
- 2 Containers (Backend, Frontend)
- Docker
- Compose
### LLM
- Ollama
- Running on the OS, outside of Docker


## Other
- The prototype in `/prototype` should be ignored and not used as reference
- API Keys and secrets should never be tracked by git and should live in seprate files