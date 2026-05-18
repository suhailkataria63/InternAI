# InternAI Architecture

## Overview

InternAI is planned as a full-stack internship assistant with a web interface, API backend, local development database, and future AI orchestration layer. The system is intentionally modular so each concern can evolve independently.

## High-Level Components

### Frontend

The frontend will use Next.js with Tailwind CSS. It will provide the main user experience for onboarding, profile management, internship discovery, application tracking, and agent-assisted preparation.

### Backend

The backend uses FastAPI. It will expose REST endpoints for frontend workflows, coordinate business logic, manage persistence, and later host or call AI agent workflows.

### Database

SQLite is used during early development for simple local persistence. The database file is created at `backend/internai.db` when the FastAPI app starts.

Current tracker storage:

- `applications` table stores saved internship analyses.
- Compact columns store candidate name, company, role, score, match level, status, notes, and timestamps.
- Nested agent outputs are stored as JSON strings for resume profile, job profile, match result, skill gap result, application answer, cover letter, and pipeline summary.
- SQLAlchemy provides the engine, session, declarative base, and request-scoped database dependency.

### AI Workflow Layer

LangChain or LangGraph will be introduced later to coordinate multi-agent behavior. The first version will keep agent modules as placeholders so the backend structure remains clean while the product model is still being shaped.

## Planned Request Flow

1. The user interacts with the Next.js frontend.
2. The frontend calls FastAPI endpoints.
3. FastAPI validates requests using schema models.
4. Services perform business logic and database operations.
5. Agent modules are invoked when AI-assisted work is needed.
6. The backend returns structured responses to the frontend.

## Application Tracker Flow

1. User runs the orchestrator from the Next.js frontend.
2. User saves the result from the results dashboard.
3. Frontend calls `POST /api/tracker/applications`.
4. FastAPI validates the payload with tracker schemas.
5. Tracker service serializes nested outputs with `json.dumps`.
6. SQLAlchemy persists the row in SQLite.
7. Tracker list endpoint returns compact rows for the frontend table.

## Backend Module Plan

- `api/`: Route definitions and API composition.
- `agents/`: Future AI agents and orchestration logic.
- `services/`: Business logic shared across routes.
- `database/`: SQLite connection, models, migrations, and persistence helpers.
- `schemas/`: Pydantic request and response models.
- `utils/`: Shared utility functions.

## Current Status

The current architecture includes a FastAPI application with CORS configured for local frontend development, a `/health` endpoint for verification, a multi-agent orchestrator, and a SQLite-backed application tracker.
