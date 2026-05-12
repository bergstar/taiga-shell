#!/usr/bin/env python3
"""Taiga CLI — command-line interface for the Taiga project management API."""

import argparse
import json
import stat
import sys
from pathlib import Path

from taiga import TaigaAPI
from taiga.exceptions import TaigaException

CONFIG_DIR = Path.home() / ".taiga"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"

COMMANDS = {}


def register(name):
    def decorator(fn):
        COMMANDS[name] = fn
        return fn
    return decorator


def _resolve_status(obj):
    info = getattr(obj, "status_extra_info", None)
    if isinstance(info, dict):
        return info.get("name", "?")
    return str(obj.status) if obj.status else "-"


def _resolve_assigned(obj):
    info = getattr(obj, "assigned_to_extra_info", None)
    if isinstance(info, dict):
        return info.get("full_name_display", info.get("username", "?"))
    return str(obj.assigned_to) if obj.assigned_to else "unassigned"


def _paginate(api_method, project_id, page_size=100):
    page = 1
    while True:
        results = api_method(project=project_id, page=page, page_size=page_size)
        if not results:
            break
        yield from results
        if len(results) < page_size:
            break
        page += 1


def _load_credentials_file():
    if not CREDENTIALS_FILE.exists():
        return {}, None
    mode = CREDENTIALS_FILE.stat().st_mode
    if mode & stat.S_IRWXG or mode & stat.S_IRWXO:
        return {}, f"{CREDENTIALS_FILE} has overly permissive permissions (run: chmod 600 {CREDENTIALS_FILE})"
    try:
        return json.loads(CREDENTIALS_FILE.read_text()), None
    except (json.JSONDecodeError, OSError) as exc:
        return {}, f"Failed to read {CREDENTIALS_FILE}: {exc}"


def load_credentials(args):
    if args.username and args.password:
        return args.username, args.password, args.host

    creds, err = _load_credentials_file()
    if err:
        print(f"Warning: {err}", file=sys.stderr)

    username = args.username or creds.get("username")
    password = args.password or creds.get("password")
    host = args.host or creds.get("host")

    if not username or not password:
        print(
            f"Error: credentials not found.\n"
            f"  Create {CREDENTIALS_FILE} with \"username\" and \"password\" fields,\n"
            f"  or pass --username / --password on the command line.\n"
            f"  Example: {{\"username\": \"you@example.com\", \"password\": \"secret\"}}",
            file=sys.stderr,
        )
        sys.exit(1)

    return username, password, host


def connect(username, password, host=None):
    try:
        api = TaigaAPI(host=host) if host else TaigaAPI()
        api.auth(username=username, password=password)
        return api
    except TaigaException as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        sys.exit(1)


@register("projects")
def cmd_projects(api, args):
    me = api.me()
    projects = api.projects.list(member=me.id, page=1, page_size=100)
    for p in projects:
        print(f"{p.slug}\t{p.name}\t(id={p.id})")


@register("stories")
def cmd_stories(api, args):
    project = api.projects.get_by_slug(args.project)
    print(f"# Project: {project.name} (slug={project.slug}, id={project.id})\n")
    total = 0
    for s in _paginate(api.user_stories.list, project.id):
        status = _resolve_status(s)
        milestone = s.milestone or "-"
        print(f"#{s.ref}\t{s.subject}\t[{status}]\tmilestone={milestone}")
        total += 1
    print(f"\nTotal user stories: {total}")


@register("story")
def cmd_story(api, args):
    project = api.projects.get_by_slug(args.project)
    us = project.get_userstory_by_ref(args.ref)
    print(f"User Story #{us.ref}: {us.subject}")
    print(f"  Status:     {_resolve_status(us)}")
    print(f"  Assigned:   {_resolve_assigned(us)}")
    print(f"  Milestone:  {us.milestone or '-'}")
    print(f"  Created:    {us.created_date}")
    print(f"  Modified:   {us.modified_date}")
    print(f"  Finish:     {getattr(us, 'finish_date', None) or '-'}")
    print(f"  Tags:       {us.tags}")
    print(f"  Comments:   {us.total_comments}")
    print(f"  Attachments:{us.total_attachments}")


@register("tasks")
def cmd_tasks(api, args):
    project = api.projects.get_by_slug(args.project)
    print(f"# Project: {project.name} (slug={project.slug}, id={project.id})\n")
    total = 0
    for t in _paginate(api.tasks.list, project.id):
        status = _resolve_status(t)
        assigned = _resolve_assigned(t)
        us_ref = f" [US#{t.user_story}]" if t.user_story else ""
        print(f"#{t.ref}\t{t.subject}\t[{status}]\t{assigned}{us_ref}")
        total += 1
    print(f"\nTotal tasks: {total}")


@register("task")
def cmd_task(api, args):
    project = api.projects.get_by_slug(args.project)
    task = project.get_task_by_ref(args.ref)
    print(f"Task #{task.ref}: {task.subject}")
    print(f"  Status:     {_resolve_status(task)}")
    print(f"  Assigned:   {_resolve_assigned(task)}")
    print(f"  Milestone:  {task.milestone or '-'}")
    print(f"  User Story: {task.user_story or '-'}")
    print(f"  Created:    {task.created_date}")
    print(f"  Modified:   {task.modified_date}")
    print(f"  Finished:   {task.finished_date or '-'}")
    print(f"  Due Date:   {task.due_date or '-'}")
    print(f"  Tags:       {task.tags}")
    print(f"  Blocked:    {task.is_blocked}")


@register("comment")
def cmd_comment(api, args):
    project = api.projects.get_by_slug(args.project)
    us = project.get_userstory_by_ref(args.ref)
    text = args.text
    if args.file:
        text = Path(args.file).read_text()
    us.add_comment(text)
    print(f"Comment added to #{us.ref}: {us.subject}")


@register("attach")
def cmd_attach(api, args):
    project = api.projects.get_by_slug(args.project)
    us = project.get_userstory_by_ref(args.ref)
    filepath = Path(args.file).expanduser().resolve()
    if not filepath.is_file():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    us.attach(str(filepath), description=args.description or "")
    print(f"Attached {filepath.name} to #{us.ref}: {us.subject}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="taiga",
        description="Taiga CLI — interact with Taiga from the command line",
    )
    parser.add_argument("--host", help="Taiga host URL (default: https://api.taiga.io)")
    parser.add_argument("--username", "-u", help="Username (overrides config)")
    parser.add_argument("--password", "-p", help="Password (overrides config)")

    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("projects", help="List your projects")
    p.add_argument("--all", action="store_true", help="Fetch all pages")

    p = sub.add_parser("stories", help="List user stories in a project")
    p.add_argument("project", help="Project slug")

    p = sub.add_parser("story", help="Show user story details")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="User story ref")

    p = sub.add_parser("tasks", help="List tasks in a project")
    p.add_argument("project", help="Project slug")

    p = sub.add_parser("task", help="Show task details")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="Task ref")

    p = sub.add_parser("comment", help="Add a comment to a user story")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="User story ref")
    p.add_argument("text", nargs="?", help="Comment text (Markdown supported)")
    p.add_argument("--file", "-f", help="Read comment text from file")

    p = sub.add_parser("attach", help="Attach a file to a user story")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="User story ref")
    p.add_argument("file", help="Path to file to attach")
    p.add_argument("--description", "-d", default="", help="Attachment description")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    username, password, host = load_credentials(args)
    api = connect(username, password, host)

    try:
        COMMANDS[args.command](api, args)
    except TaigaException as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        sys.exit(130)
