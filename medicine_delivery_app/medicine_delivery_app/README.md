# Doorstep Meds — FNB App Academy Capstone

![Project logo](assets/logo.svg)

**A Python application-development capstone demonstrating a multi-screen client, a REST API, persistence and object-oriented design.**

Doorstep Meds was developed as part of the FNB App Academy's *Introduction to Python: Mobile and Web Application Development* programme. The project gave me an opportunity to bring together concepts from the course in a larger application.

> **Project status:** Educational prototype for portfolio demonstration only. It is not a production healthcare service. Do not enter real patient, personal or health information. The code has not undergone an independent security or regulatory assessment.

## Technology stack

| Layer | Technology |
|---|---|
| Client UI | Python, Flet |
| Backend | Python, Flask |
| API communication | REST, HTTP, JSON, Requests |
| Persistence | SQLite and JSON |
| Automated tests | Python `unittest` |
| External service adapters | Notification-provider abstractions |

## Architecture

The codebase separates the main technical responsibilities:

- **Client application** — application entry point, screens, shared theme and navigation.
- **API client** — centralises communication between the client and backend.
- **Flask API** — provides server endpoints and server-side request checks.
- **Domain models** — uses classes to represent application data and validation.
- **Storage layer** — separates persistence from the rest of the application.
- **Tests** — contains automated tests for models, storage and API/client components.

```text
Flet client
  main.py | views/ | theme.py
       |
       v
API client (Requests)
       |
       v
Flask REST API
  backend/app.py
       |
       +---- models.py
       |
       +---- storage.py
       |
       +---- notifier.py
```

## Concepts demonstrated

- **Object-oriented programming:** classes, inheritance, composition, polymorphism and `super()`.
- **Application structure:** separation of UI, API communication, models and persistence.
- **File handling:** JSON and SQLite data storage.
- **Error management:** input validation, exceptions and API error handling.
- **API development:** HTTP requests, JSON payloads and a client/server architecture.
- **Testing:** unit and integration-style tests using Python's standard `unittest` framework.
- **User interface development:** multi-view navigation, reusable styling, dialogs and form validation.

## Repository structure

The application source is in `medicine_delivery_app/medicine_delivery_app/`.

| Path | Purpose |
|---|---|
| `main.py` | Application entry point |
| `views/` | UI screens |
| `theme.py` | Shared interface styling |
| `api_client.py` | Client-side API communication |
| `backend/app.py` | Flask API |
| `models.py` | Application models |
| `storage.py` | Persistence implementations |
| `notifier.py` | Notification adapter code |
| `tests/` | Automated tests |
| `assets/` | Static assets |

## Running the test suite

From this directory, install the dependencies listed in `requirements.txt` and `backend/requirements.txt`, then run:

```bash
python -m unittest discover -s tests -v
```

The original project notes report 43 tests. That count should be treated as a project-reported figure until the suite has been run successfully in a clean environment.

## Limitations and responsible-use notes

- This is a learning project, not a production-ready healthcare application.
- Authentication and PIN-related code has not been independently security-audited. Different credential flows use different hashing approaches; do not treat the current implementation as a security standard.
- Some rate-limiting state is held in process memory and may not persist across restarts.
- The backend has documented single-process and scaling limitations.
- External SMS and email integrations are documented, but live-provider operation has not been independently verified.
- No real personal or health data should be used for demonstrations or testing.

## What I learned

This capstone helped me practise combining Python fundamentals into a larger codebase. In particular, it strengthened my understanding of object-oriented programming, file handling, exception management, API communication, persistence and testing.

The project is presented as evidence of my learning and development—not as a claim that the application is ready for real-world healthcare use.
