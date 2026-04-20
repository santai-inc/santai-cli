# Authentication

Santai CLI can authenticate with Santai Hub for cloud sync features (`push` and `pull`). Three commands manage authentication: `login`, `logout`, and `whoami`.

Credentials are stored locally at `~/.config/santai/credentials.json` with restricted permissions (600).

---

## santai login

Authenticate with Santai Hub via the browser.

### Usage

```bash
santai login [OPTIONS]
```

### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--hub-url` | — | `SANTAI_HUB_URL` or `http://localhost:3000` | Santai Hub URL |
| `--port` | `-p` | Auto-detected | Fixed port for callback server (useful for SSH tunneling) |

### Behavior

1. Starts a local HTTP server to receive the authentication callback
2. Opens your browser to the Hub's CLI authentication page
3. After you authenticate in the browser, the Hub redirects back to the local server with a token
4. The token and username are saved to `~/.config/santai/credentials.json`

### Examples

Standard login:

```bash
santai login
```

Login to a custom Hub instance:

```bash
santai login --hub-url https://hub.example.com
```

Login with a fixed callback port (useful when port-forwarding over SSH):

```bash
santai login --port 9876
```

### Timeout

The login flow times out after **120 seconds**. Press `Ctrl+C` to cancel early.

---

## santai logout

Log out of Santai Hub by clearing stored credentials.

### Usage

```bash
santai logout
```

### Behavior

Removes the credentials file at `~/.config/santai/credentials.json`. If not currently logged in, prints a message and exits.

---

## santai whoami

Show the currently authenticated user and verify the session is still valid.

### Usage

```bash
santai whoami
```

### Behavior

1. Reads stored credentials
2. Verifies the token against the Hub server
3. Displays username, name, email, Hub URL, and session expiration

If the session has expired, credentials are cleared and you're prompted to re-authenticate.

If the Hub is unreachable (offline), it falls back to showing the cached username.

### Example Output

```
Logged in as johndoe
  Name:  John Doe
  Email: john@example.com
  Hub:   http://localhost:3000
  Expires: 2025-05-17T08:00:00Z
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SANTAI_HUB_URL` | `http://localhost:3000` | Override the default Hub URL for all auth commands |
