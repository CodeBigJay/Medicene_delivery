# Doorstep Meds

**A Python application prototype built with Flet, Flask and SQLite.**

Doorstep Meds is a course capstone project created for the FNB App Academy's Introduction to Python programme. It explores how a multi-role client application can communicate with a separate REST API and persist application data.

> **Project status:** Educational prototype. It is not a production healthcare service and has not been validated for real-world clinical use. Do not use it with real patient information.

## Technical overview

| Area | Technologies |
|---|---|
| Client application | Python, Flet |
| Backend API | Python, Flask |
| Persistence | SQLite and JSON storage |
| Client/server communication | REST, HTTP, JSON |
| Testing | Python `unittest` |
| Integrations | Notification-provider abstractions |

## Architecture

The project separates the client interface from the backend:

- **Flet client** — application entry point, views, shared theme and navigation.
- **API client** — centralises HTTP requests and session handling.
- **Flask backend** — exposes the API and applies server-side authentication and role checks.
- **Models** — represents the application's domain objects and validation.
- **Storage layer** — provides SQLite and JSON persistence implementations.
- **Tests** — contains automated tests for core modules and API behaviour.

## Engineering concepts demonstrated

- Object-oriented programming, inheritance and composition
- Separation of concerns between UI, API, domain logic and persistence
- REST API design and client/server communication
- Input validation and exception handling
- Authentication, authorization and session management concepts
- Automated testing and persistence testing

## Repository layout

The application source is currently nested under:

`medicine_delivery_app/medicine_delivery_app/`

The project README, setup notes, deployment notes and test instructions are located in that directory.

[Open the application README](medicine_delivery_app/medicine_delivery_app/README.md)

## Running tests

From the application directory, consult its README for environment setup and the documented test commands. Tests have not been represented here as a guarantee of production readiness.

## Current limitations

- The project is an educational prototype, not a production-ready healthcare system.
- The existing design has documented single-process and scalability limitations.
- Some external notification integrations are documented but have not been verified as live services.
- The interface and backend require further independent review, testing and security assessment before any real-world use.

## What this project demonstrates

This repository is included as a portfolio example of a Python full-stack application, with a distinct client, REST backend, persistence layer and automated tests. The emphasis is on the software structure and engineering concepts demonstrated by the code—not on providing a live healthcare service.
