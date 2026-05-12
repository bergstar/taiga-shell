# taiga-shell

Command-line interface for the [Taiga](https://taiga.io) project management API.

## Installation

```bash
pip install taiga-shell
```

## Setup

Create `~/.taiga/credentials.json` with your Taiga credentials:

```bash
mkdir -p ~/.taiga
cat > ~/.taiga/credentials.json << 'EOF'
{
  "username": "you@example.com",
  "password": "your-password",
  "host": "https://api.taiga.io"
}
EOF
chmod 600 ~/.taiga/credentials.json
```

The `host` field is optional and defaults to `https://api.taiga.io`. You can also pass credentials via CLI flags `--username` / `--password`.

## Usage

```
taiga [OPTIONS] COMMAND [ARGS]
```

### Commands

| Command | Description |
|---------|-------------|
| `taiga projects` | List your projects |
| `taiga stories <slug>` | List all user stories in a project |
| `taiga story <slug> <ref>` | Show user story details |
| `taiga tasks <slug>` | List all tasks in a project |
| `taiga task <slug> <ref>` | Show task details |
| `taiga comment <slug> <ref> <text>` | Add a comment (Markdown) to a user story |
| `taiga comment <slug> <ref> -f comment.md` | Add comment from a file |
| `taiga attach <slug> <ref> <file> [-d desc]` | Attach a file to a user story |

### Examples

```bash
# List your projects
taiga projects

# List all user stories
taiga stories gcardinal-pikipi

# View a specific user story
taiga story gcardinal-pikipi 441

# Add a Markdown comment
taiga comment gcardinal-pikipi 441 "**Done** in PR #42"

# Add comment from a file
taiga comment gcardinal-pikipi 441 -f review.md

# Attach a screenshot
taiga attach gcardinal-pikipi 441 screenshot.png -d "UI after fix"

# Use a custom Taiga host
taiga --host https://taiga.mycompany.com projects

# Override credentials
taiga -u admin@company.com -p secret projects
```

## License

MIT
