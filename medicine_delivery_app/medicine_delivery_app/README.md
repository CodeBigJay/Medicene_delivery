# Doorstep Meds

**A Python Flet application with a Flask API and SQLite storage.**

Doorstep Meds is my FNB App Academy capstone project. It is a prototype for managing medicine deliveries from a clinic to patients in their villages. Clinic staff prepare deliveries, messengers collect them, and the recipient confirms delivery with a PIN.

> **Project status:** This is an educational prototype for demonstration and assessment. It is not a production healthcare service. Do not enter real patient, personal or health information. The application has not had an independent security or regulatory assessment.

## Technologies used

| Part | Technology |
|---|---|
| Client interface | Python, Flet |
| Backend API | Python, Flask |
| API communication | REST, HTTP, JSON, Requests |
| Data storage | SQLite and JSON |
| Tests | Python `unittest` |
| Notifications | SMS and email provider adapters |

## How the application works

The Flet client contains the screens and navigation. It communicates with the Flask API through `api_client.py`. The API uses the models for application rules and `storage.py` to save and retrieve data.

```text
Flet client
  main.py, views/, theme.py
       |
       v
API client (Requests)
       |
       v
Flask API (backend/app.py)
       |
       +---- models.py
       |
       +---- storage.py
       |
       +---- notifier.py
```

## Features

- Separate clinic and messenger accounts
- Messenger registration and clinic approval
- Patient and delivery records
- PIN confirmation when a delivery is completed
- Delivery status updates
- Messages between clinic staff and messengers

## Main project files

| Path | Purpose |
|---|---|
| `main.py` | Starts the Flet application |
| `views/` | Application screens |
| `theme.py` | Shared interface styling |
| `api_client.py` | Sends requests to the backend |
| `backend/app.py` | Flask API routes |
| `models.py` | Application data and rules |
| `storage.py` | SQLite and JSON storage |
| `notifier.py` | SMS and email notification adapters |
| `tests/` | Automated tests |
| `assets/` | Application images and other static files |

## Running the application locally

Open a terminal in this directory.

1. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   pip install -r backend/requirements.txt
   ```

2. Start the backend in the first terminal:

   ```bash
   python -m backend.app
   ```

3. Start the Flet client in a second terminal:

   ```bash
   python main.py
   ```

The client uses `http://127.0.0.1:8000` by default. Set `DOORSTEP_API_URL` if the backend is running at a different address.

## Demo login details

Use these accounts for the main application demonstration:

| Role | Username | PIN |
|---|---|---|
| Clinic | `clinic1` | `1234` |
| Messenger | `thabo` | `1111` |

The existing `thabo` messenger demo account is already approved. It can sign in without waiting for approval.

### Testing a new messenger registration

1. On the login screen, select **Create account** and register a messenger. Enter **Lekubu** as the village.
2. Sign in with the clinic account, `clinic1` / `1234`.
3. Find the new account under **Waiting for approval** and select **Approve**.
4. The new messenger can then sign in with the username and PIN created during registration.

A newly registered messenger must wait for clinic approval. This does not apply to the existing `thabo` demo account.

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for the steps used in the application demonstration.

The demo credentials are for this project only. Do not use them for real accounts or enter real patient information.

## Running the tests

From this directory, run:

```bash
python -m unittest discover -s tests -v
```

The test suite includes tests for the models, API and client. Run the command above to see the current results.

## Limitations

- This is a learning project, not a production healthcare application.
- Authentication and PIN handling have not been independently security-audited.
- Some rate-limiting information is held in process memory.
- The backend is designed for a single-process demonstration and has scaling limitations.
- Live SMS and email provider operation has not been verified.
- Do not use real personal or health information in the application.

## Project work

The project brings together Python programming, object-oriented design, file handling, error management, API communication, data storage and interface development.