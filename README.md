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

### 7. Attach a file (image or any other file)

```bash
taiga attach gcardinal-pikipi 441 screenshot.png -d "UI after the fix"
```

Attach to an issue or task instead with `-t issue` / `-t task`:

```bash
taiga attach gcardinal-pikipi 50 bug.png -t issue -d "Console error"
```

### 8. Create a new user story or issue

```bash
taiga new-story gcardinal-pikipi "Add dark mode" -d "Toggle in settings" --tags ui,frontend
taiga new-issue gcardinal-pikipi "Login fails on Safari" --priority High --severity Critical --type Bug --tags safari,auth
```

For `new-issue`, the API requires priority, status, type, and severity — if you omit the flags the first available value in the project is used. Pass `?` style lookup by trying a name like `--priority High`; if no exact match is found, the CLI suggests valid options.

### 9. Manage tags

```bash
taiga tag gcardinal-pikipi 50 list -t issue
taiga tag gcardinal-pikipi 50 add ui,regression -t issue
taiga tag gcardinal-pikipi 50 remove regression -t issue
taiga tag gcardinal-pikipi 50 set ui,bug -t issue       # replaces all tags
taiga tag gcardinal-pikipi 50 clear -t issue
```

Tag colors are picked up from the project's existing tag palette automatically.

### 10. Filter list commands

`stories`, `tasks`, and `issues` accept the same filter flags. Issues also accept `--priority`, `--severity`, and `--issue-type`. Names are looked up against the project's available values, so you don't need IDs.

```bash
taiga stories gcardinal-pikipi --status "In progress" --assigned-to dmitry@bergstar.no
taiga issues gcardinal-pikipi --priority High --severity Critical --tags safari,auth
taiga tasks gcardinal-pikipi --milestone sprint-2026-05-08
```

### 11. Search

Hits stories, tasks, issues, epics, and wiki pages in one go (Taiga `/search` endpoint):

```bash
taiga search gcardinal-pikipi "dark mode"
```

### 12. Edit and delete

Patch any subset of subject / description / assignee / due-date:

```bash
taiga edit gcardinal-pikipi 50 --subject "New title" -t issue
taiga edit gcardinal-pikipi 441 --description "Updated spec" --due-date 2026-06-01
taiga edit gcardinal-pikipi 441 --assigned-to none        # clear assignee
taiga edit gcardinal-pikipi 441 --due-date clear          # remove due date
```

Delete requires explicit confirmation:

```bash
taiga delete gcardinal-pikipi 50 -t issue --yes
```

## All Commands

```
taiga [options] <command> [arguments]
```

| Command | Arguments | Description |
|---------|-----------|-------------|
| `projects` | — | List your projects |
| `stories` | `<slug>` | List user stories — filter with `--status`, `--assigned-to`, `--tags`, `--milestone` |
| `story` | `<slug> <ref>` | Show user story details |
| `tasks` | `<slug>` | List tasks — same filter flags as `stories` |
| `task` | `<slug> <ref>` | Show task details |
| `issues` | `<slug>` | List issues — same filters plus `--priority`, `--severity`, `--issue-type` |
| `issue` | `<slug> <ref>` | Show issue details |
| `new-story` | `<slug> <subject>` | Create a user story (`-d`, `-s`, `--tags`, `-a`) |
| `new-issue` | `<slug> <subject>` | Create an issue (`-d`, `-s`, `--priority`, `--type`, `--severity`, `--tags`, `-a`) |
| `comment` | `<slug> <ref> [text]` | Add a Markdown comment (`-t story\|task\|issue`, `-f file`) |
| `attach` | `<slug> <ref> <file>` | Attach a file (`-t story\|task\|issue`, `-d "description"`) |
| `attachments` | `<slug> <ref>` | List attachments (`-t story\|task\|issue`) |
| `move` | `<slug> <ref> <status>` | Change status (`-t story\|task\|issue`, status `?` lists options) |
| `tag` | `<slug> <ref> <action> [tags]` | Manage tags: `add`, `remove`, `set`, `list`, `clear` (`-t story\|task\|issue`) |
| `search` | `<slug> <text>` | Search stories, tasks, issues, epics, and wiki pages in one call |
| `edit` | `<slug> <ref>` | Patch subject / description / assignee / due-date (`-t story\|task\|issue`) |
| `delete` | `<slug> <ref> --yes` | Delete a story, task, or issue (`-t`); `--yes` is required |

**Options:**

| Flag | Description |
|------|-------------|
| `--host <url>` | Override the Taiga host URL |
| `-u, --username` | Override username |
| `-p, --password` | Override password |

## License

MIT
