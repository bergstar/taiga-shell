# taiga-shell

Command-line interface for the [Taiga](https://taiga.io) project management API.

## Quick Start

### 1. Install

```bash
pip install taiga-shell
```

### 2. Add your credentials

```bash
mkdir -p ~/.taiga
cat > ~/.taiga/credentials.json << 'EOF'
{
  "username": "you@example.com",
  "password": "your-password"
}
EOF
chmod 600 ~/.taiga/credentials.json
```

The `host` field is optional — it defaults to `https://api.taiga.io`. Add it only if you use a self-hosted Taiga instance:

```json
{
  "username": "you@example.com",
  "password": "your-password",
  "host": "https://taiga.mycompany.com"
}
```

### 3. Find your project

Every command targets a project by its **slug** (the short name in the URL). List your projects to find it:

```bash
$ taiga projects
9tee9-migfull    Migfull     (id=1774674)
gcardinal-pikipi PiKiPi      (id=1747301)
```

The slug is the first column — e.g. `gcardinal-pikipi`.

### 4. Browse user stories

List all user stories in a project:

```bash
$ taiga stories gcardinal-pikipi
# Project: PiKiPi (slug=gcardinal-pikipi, id=1747301)

#445  После завершения раздела реализовать переход...  [Новая]  milestone=-
#441  Обновить надпись в разделе "Тест"              [Новая]  milestone=-
#440  Обновить страницу личных данных ребенка...      [Новая]  milestone=-
...

Total user stories: 295
```

The number after `#` is the **ref** — e.g. `441`.

### 5. View a user story

Use the slug and the ref to see details:

```bash
$ taiga story gcardinal-pikipi 441
User Story #441: Обновить надпись в разделе "Тест"
  Status:     Новая
  Assigned:   unassigned
  Milestone:  -
  Created:    2026-05-11T08:07:53.267Z
  Modified:   2026-05-12T08:27:54.064Z
  Finish:     -
  Tags:       [['фронтенд', '#AC51D3']]
  Comments:   2
  Attachments:1
```

### 6. Add a comment

Comments support full Markdown:

```bash
taiga comment gcardinal-pikipi 441 "**Done** — fixed in PR #42"
```

Or read from a file:

```bash
taiga comment gcardinal-pikipi 441 -f review.md
```

### 7. Attach a file

```bash
taiga attach gcardinal-pikipi 441 screenshot.png -d "UI after the fix"
```

## All Commands

```
taiga [options] <command> [arguments]
```

| Command | Arguments | Description |
|---------|-----------|-------------|
| `projects` | — | List your projects |
| `stories` | `<slug>` | List all user stories |
| `story` | `<slug> <ref>` | Show user story details |
| `tasks` | `<slug>` | List all tasks |
| `task` | `<slug> <ref>` | Show task details |
| `comment` | `<slug> <ref> [text]` | Add a Markdown comment (or use `-f file`) |
| `attach` | `<slug> <ref> <file>` | Attach a file (`-d "description"`) |

**Options:**

| Flag | Description |
|------|-------------|
| `--host <url>` | Override the Taiga host URL |
| `-u, --username` | Override username |
| `-p, --password` | Override password |

## License

MIT
