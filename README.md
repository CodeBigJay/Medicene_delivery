# Doorstep Meds

**Python Flet application with a Flask API and SQLite storage.**

Doorstep Meds is my FNB App Academy capstone project. It is a prototype for managing medicine deliveries from a clinic to patients in their villages. Clinic staff prepare deliveries, messengers collect them, and the recipient confirms delivery with a PIN.

This project was built for learning and demonstration. It is not a production healthcare service. Do not enter real patient or health information.

## Technologies

- Python and Flet for the application interface
- Python and Flask for the API
- SQLite and JSON for data storage
- Requests for communication between the client and API
- Python `unittest` for automated tests

## How the application is organised

The Flet client contains the screens and navigation. It sends requests through `api_client.py` to the Flask API in `backend/app.py`. The models contain the main application rules, while `storage.py` handles data persistence.

## Main features

- Separate clinic and messenger accounts
- Messenger registration and clinic approval
- Patient and delivery records
- PIN confirmation when a delivery is completed
- Delivery status updates
- Messages between clinic staff and messengers

## Project files

The application source is in `medicine_delivery_app/medicine_delivery_app/`. The README in that folder contains setup instructions and the demo login details.

[Open the application README](medicine_delivery_app/medicine_delivery_app/README.md)

## Running tests

Open the application folder and follow the test instructions in its README. The test suite is useful for checking the current implementation, but passing tests do not make this prototype suitable for real healthcare use.

## Limitations

This is a student project. The application has not had an independent security or regulatory assessment. Its current backend also has single-process and scaling limitations. Live SMS and email services have not been verified.

The project demonstrates the Python, API, database and interface work completed for the capstone.