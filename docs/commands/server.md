# santai server

Launch a headless JSON API server for programmatic access to Santai project operations.

## Usage

```bash
santai server [OPTIONS]
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--host` | `-h` | `127.0.0.1` | Host to bind the server to |
| `--port` | `-p` | `8080` | Port to run the server on |
| `--token` | `-t` | None | Bearer token for API authentication |

## Description

The server command starts a FastAPI application that exposes Santai project operations as REST API endpoints. This is useful for integrating Santai into automation pipelines, CI/CD systems, or building custom frontends.

OpenAPI documentation is automatically available at `/docs` when the server is running.

## Authentication

When a token is provided (via `--token` or the `SANTAI_SERVER_TOKEN` environment variable), all API requests must include an `Authorization: Bearer <token>` header.

The CLI flag takes precedence over the environment variable.

**Public paths** that skip authentication:

- `/api/health`
- `/docs`
- `/openapi.json`
- `/redoc`

!!! warning
    When binding to a non-localhost address (e.g. `0.0.0.0`) without a token, the server logs a warning. Always use authentication when exposing the server on a network.

## API Endpoints

### `GET /api/health`

Health check endpoint. Always returns `{"status": "ok"}`.

### `POST /api/init`

Initialize a new Santai project.

**Request body:**

```json
{
  "path": "/path/to/new-project",
  "name": "my-project"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | Yes | Directory path to create and initialize |
| `name` | string | No | Project name (defaults to directory name) |

**Response:**

```json
{
  "status": "ok",
  "path": "/absolute/path/to/new-project"
}
```

### `POST /api/copy`

Copy a Santai project to a new location with a fresh git history.

**Request body:**

```json
{
  "source": "/path/to/source-project",
  "destination": "/path/to/destination"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | Yes | Source project path |
| `destination` | string | Yes | Destination path (must not exist) |

**Response:**

```json
{
  "status": "ok",
  "destination": "/absolute/path/to/destination"
}
```

### `POST /api/cherry-pick`

Selectively copy files between Santai projects.

**Request body:**

```json
{
  "source": "/path/to/source-project",
  "destination": "/path/to/dest-project",
  "files": ["notes/idea.md", "media/"],
  "overwrite": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `source` | string | Yes | — | Source project path |
| `destination` | string | Yes | — | Destination project path |
| `files` | list[string] | Yes | — | Files or folders to cherry-pick (relative paths) |
| `overwrite` | boolean | No | `false` | Overwrite existing files at destination |

**Response:**

```json
{
  "status": "ok",
  "copied": ["notes/idea.md", "media/architecture.md"]
}
```

### `POST /api/merge`

Merge two Santai projects into a new combined project. The primary project's files take precedence on conflicts.

**Request body:**

```json
{
  "primary": "/path/to/primary-project",
  "secondary": "/path/to/secondary-project",
  "output": "/path/to/merged-output"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `primary` | string | Yes | Primary project (its files take precedence) |
| `secondary` | string | Yes | Secondary project to merge in |
| `output` | string | Yes | Output directory (must not exist) |

**Response:**

```json
{
  "status": "ok",
  "output": "/absolute/path/to/merged-output"
}
```

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Description of the error"
}
```

Common HTTP status codes:

| Code | Meaning |
|------|---------|
| 400 | Bad request (invalid parameters) |
| 401 | Unauthorized (missing or invalid token) |
| 404 | Not found (source path doesn't exist) |
| 409 | Conflict (destination already exists, or directory is not empty) |
| 500 | Internal server error |

## Examples

Start the server with default settings (localhost only, no auth):

```bash
santai server
```

Start on a custom port with authentication:

```bash
santai server --port 9000 --token my-secret-token
```

Bind to all interfaces (for network access):

```bash
santai server --host 0.0.0.0 --token my-secret-token
```

Use an environment variable for the token:

```bash
export SANTAI_SERVER_TOKEN=my-secret-token
santai server --host 0.0.0.0
```

Make an authenticated API call:

```bash
curl -X POST http://localhost:8080/api/init \
  -H "Authorization: Bearer my-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"path": "./new-project"}'
```

Access the interactive API docs:

```bash
santai server
# Open http://localhost:8080/docs in your browser
```
