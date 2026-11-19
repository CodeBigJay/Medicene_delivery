# Deployment notes

This document describes possible ways to run the Doorstep Meds backend outside a local development environment. These deployment steps are guidance only; the project has not been confirmed as running on a live hosting service.

## 1. Run the backend

### Render

The repository includes a `render.yaml` Blueprint configuration. A persistent disk is required if the SQLite database must retain its data between restarts. Check the current Render plan and pricing before choosing this option; persistent disks may require a paid plan.

### Docker

Build and run the backend from this directory:

```bash
docker build -t doorstep-api .
docker run -d -p 8000:8000 -v doorstep-data:/data \
  -e DOORSTEP_ADMIN_PIN=choose-a-long-pin \
  doorstep-api
```

For a production profile, configure the required environment variables before starting the container. The first production setup creates an admin account; it does not load the demo accounts. Sign in as the admin, add the required records and approve messenger registrations.

Use HTTPS when making the API available outside a local development machine.

## 2. SMS notifications

The notifier supports a Twilio configuration through the `SMS_PROVIDER` and `TWILIO_*` environment variables. Without a live SMS provider, the PIN is written to the server log and shown on the clinic screen.

The live SMS integration has not been tested with a provider account.

## 3. Email notifications

Email can be configured through SMTP using `EMAIL_PROVIDER=smtp` and the `SMTP_*` environment variables. Without SMTP settings, email output is written to the server log.

The live email integration has not been tested with a mail account.

## 4. Configure the client

Set `DOORSTEP_API_URL` to the address of the backend before starting the client. For example:

```bash
DOORSTEP_API_URL=https://your-server.example python main.py
```

For packaged applications, configure the API address in the client settings as described in the source.

## 5. Before any real-world use

This project is a learning prototype and must not be used with real patient information. A real deployment would need an independent security review, appropriate privacy and legal review, access controls, secure backups and tested notification services. South African patient information may be subject to POPIA requirements.

## 6. Scaling

The current backend is designed for a small demonstration and runs as a single process. A larger deployment would need a production database, such as PostgreSQL, and further work on concurrent updates, monitoring and operational security.