#!/usr/bin/env python3
"""Taiga Shell — command-line interface for the Taiga project management API."""

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

ITEM_KINDS = ("story", "task", "issue")


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


def _paginate(api_method, project_id, page_size=100, **filters):
    page = 1
    while True:
        results = api_method(project=project_id, page=page, page_size=page_size, **filters)
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


def _get_item(project, kind, ref):
    if kind == "task":
        return project.get_task_by_ref(ref)
    if kind == "issue":
        return project.get_issue_by_ref(ref)
    return project.get_userstory_by_ref(ref)


def _history_endpoint(api, kind):
    if kind == "task":
        return api.history.task
    if kind == "issue":
        return api.history.issue
    return api.history.user_story


def _kind_label(kind):
    return {"story": "User Story", "task": "Task", "issue": "Issue"}.get(kind, kind.title())


def _parse_tag_names(tags):
    """Normalize the API's tags field to a list of plain string names.

    The API returns tags as either ``["name", ...]`` or ``[["name", "#color"], ...]``.
    """
    if not tags:
        return []
    names = []
    for t in tags:
        if isinstance(t, (list, tuple)):
            if t:
                names.append(t[0])
        else:
            names.append(t)
    return names


def _split_csv(value):
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _find_by_name(items, name, kind_label):
    if not items:
        return None
    for it in items:
        if it.name.lower() == name.lower():
            return it
    for it in items:
        if name.lower() in it.name.lower():
            return it
    available = ", ".join(i.name for i in items)
    print(f"Error: {kind_label} '{name}' not found. Available: {available}", file=sys.stderr)
    sys.exit(1)


def _find_milestone(project, value):
    """Resolve a milestone by ID, slug, or name."""
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    milestones = project.list_milestones()
    for m in milestones:
        if m.slug.lower() == value.lower() or m.name.lower() == value.lower():
            return m.id
    available = ", ".join(f"{m.name} ({m.slug})" for m in milestones)
    print(f"Error: milestone '{value}' not found. Available: {available}", file=sys.stderr)
    sys.exit(1)


def _build_list_filters(project, kind, args):
    """Translate CLI filter args into Taiga API query params."""
    filters = {}
    if getattr(args, "status", None):
        statuses = _list_statuses_for(project, kind)
        filters["status"] = _find_by_name(statuses, args.status, "status").id
    if getattr(args, "assigned_to", None):
        filters["assigned_to"] = _resolve_assigned_to(project, args.assigned_to)
    if getattr(args, "tags", None):
        filters["tags"] = args.tags
    if getattr(args, "milestone", None):
        filters["milestone"] = _find_milestone(project, args.milestone)
    if kind == "issue":
        if getattr(args, "priority", None):
            filters["priority"] = _find_by_name(project.list_priorities(), args.priority, "priority").id
        if getattr(args, "severity", None):
            filters["severity"] = _find_by_name(project.list_severities(), args.severity, "severity").id
        if getattr(args, "issue_type", None):
            filters["type"] = _find_by_name(project.list_issue_types(), args.issue_type, "issue type").id
    return filters


@register("projects")
def cmd_projects(api, args):
    me = api.me()
    projects = api.projects.list(member=me.id, page=1, page_size=100)
    for p in projects:
        print(f"{p.slug}\t{p.name}\t(id={p.id})")


@register("stories")
def cmd_stories(api, args):
    project = api.projects.get_by_slug(args.project)
    filters = _build_list_filters(project, "story", args)
    print(f"# Project: {project.name} (slug={project.slug}, id={project.id})\n")
    total = 0
    for s in _paginate(api.user_stories.list, project.id, **filters):
        status = _resolve_status(s)
        milestone = s.milestone or "-"
        print(f"#{s.ref}\t{s.subject}\t[{status}]\tmilestone={milestone}")
        total += 1
    print(f"\nTotal user stories: {total}")


def _format_size(size):
    if size < 1024:
        return f"{size}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size / (1024 * 1024):.1f}MB"


def _print_comments(api, history_endpoint, item_id):
    try:
        history = history_endpoint.get(item_id)
    except Exception:
        return
    comments = [h for h in history if h.get("comment", "").strip()]
    comments.reverse()
    if not comments:
        return
    print(f"\n  Comments ({len(comments)}):")
    for c in comments:
        user = c.get("user", {}).get("name", "?")
        created = c.get("created_at", "")
        text = c["comment"].strip()
        print(f"    [{user} @ {created}]")
        for line in text.splitlines():
            print(f"      {line}")
        print()


def _print_attachments(item):
    try:
        attachments = item.list_attachments()
    except Exception:
        return
    if not attachments:
        return
    print(f"\n  Attachments ({len(attachments)}):")
    for a in attachments:
        size = _format_size(a.size) if a.size else "?"
        print(f"    {a.name} ({size})")
        if a.description:
            print(f"      {a.description}")
        print(f"      {a.url}")


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
    _print_comments(api, api.history.user_story, us.id)
    _print_attachments(us)


@register("tasks")
def cmd_tasks(api, args):
    project = api.projects.get_by_slug(args.project)
    filters = _build_list_filters(project, "task", args)
    print(f"# Project: {project.name} (slug={project.slug}, id={project.id})\n")
    total = 0
    for t in _paginate(api.tasks.list, project.id, **filters):
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
    _print_comments(api, api.history.task, task.id)
    _print_attachments(task)


@register("issues")
def cmd_issues(api, args):
    project = api.projects.get_by_slug(args.project)
    filters = _build_list_filters(project, "issue", args)
    print(f"# Project: {project.name} (slug={project.slug}, id={project.id})\n")
    total = 0
    for i in _paginate(api.issues.list, project.id, **filters):
        status = _resolve_status(i)
        assigned = _resolve_assigned(i)
        print(f"#{i.ref}\t{i.subject}\t[{status}]\t{assigned}")
        total += 1
    print(f"\nTotal issues: {total}")


@register("issue")
def cmd_issue(api, args):
    project = api.projects.get_by_slug(args.project)
    issue = project.get_issue_by_ref(args.ref)
    print(f"Issue #{issue.ref}: {issue.subject}")
    print(f"  Status:     {_resolve_status(issue)}")
    print(f"  Assigned:   {_resolve_assigned(issue)}")
    print(f"  Milestone:  {issue.milestone or '-'}")
    print(f"  Priority:   {issue.priority or '-'}")
    print(f"  Severity:   {issue.severity or '-'}")
    print(f"  Type:       {getattr(issue, 'type', None) or '-'}")
    print(f"  Created:    {issue.created_date}")
    print(f"  Modified:   {issue.modified_date}")
    print(f"  Finished:   {getattr(issue, 'finished_date', None) or '-'}")
    print(f"  Due Date:   {getattr(issue, 'due_date', None) or '-'}")
    print(f"  Tags:       {issue.tags}")
    print(f"  Blocked:    {issue.is_blocked}")
    _print_comments(api, api.history.issue, issue.id)
    _print_attachments(issue)


@register("attachments")
def cmd_attachments(api, args):
    project = api.projects.get_by_slug(args.project)
    item = _get_item(project, args.type, args.ref)
    attachments = item.list_attachments()
    if not attachments:
        print("No attachments.")
        return
    for a in attachments:
        size = _format_size(a.size) if a.size else "?"
        print(f"{a.name}\t{size}\t{a.url}")
        if a.description:
            print(f"  {a.description}")


def _find_status(statuses, name):
    for s in statuses:
        if s.name.lower() == name.lower():
            return s
    for s in statuses:
        if name.lower() in s.name.lower():
            return s
    return None


def _list_statuses_for(project, kind):
    if kind == "task":
        return list(project.task_statuses)
    if kind == "issue":
        return project.list_issue_statuses()
    return project.list_user_story_statuses()


@register("move")
def cmd_move(api, args):
    project = api.projects.get_by_slug(args.project)
    statuses = _list_statuses_for(project, args.type)
    item = _get_item(project, args.type, args.ref)

    if args.status == "?":
        current = _resolve_status(item)
        print(f"Current: {current}")
        print("Available:")
        for s in statuses:
            closed = " (closed)" if s.is_closed else ""
            print(f"  {s.name}{closed}")
        return

    target = _find_status(statuses, args.status)
    if not target:
        names = ", ".join(s.name for s in statuses)
        print(f"Error: status '{args.status}' not found. Available: {names}", file=sys.stderr)
        sys.exit(1)

    item.update(status=target.id)
    print(f"{_kind_label(args.type)} #{item.ref} moved to [{target.name}]: {item.subject}")


@register("comment")
def cmd_comment(api, args):
    project = api.projects.get_by_slug(args.project)
    item = _get_item(project, args.type, args.ref)
    text = args.text
    if args.file:
        text = Path(args.file).read_text()
    item.add_comment(text)
    print(f"Comment added to #{item.ref}: {item.subject}")


@register("attach")
def cmd_attach(api, args):
    project = api.projects.get_by_slug(args.project)
    item = _get_item(project, args.type, args.ref)
    filepath = Path(args.file).expanduser().resolve()
    if not filepath.is_file():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    item.attach(str(filepath), description=args.description or "")
    print(f"Attached {filepath.name} to #{item.ref}: {item.subject}")


def _resolve_assigned_to(project, username):
    """Look up a project member by username, email, or full name."""
    for m in project.list_memberships():
        candidates = [
            getattr(m, "user_email", None),
            getattr(m, "email", None),
            getattr(m, "full_name", None),
        ]
        if any(c and c.lower() == username.lower() for c in candidates):
            return m.user
    print(f"Error: member '{username}' not found in project", file=sys.stderr)
    sys.exit(1)


@register("new-story")
def cmd_new_story(api, args):
    project = api.projects.get_by_slug(args.project)
    attrs = {}
    if args.description:
        attrs["description"] = args.description
    if args.tags:
        attrs["tags"] = _split_csv(args.tags)
    if args.status:
        status = _find_by_name(project.list_user_story_statuses(), args.status, "status")
        attrs["status"] = status.id
    if args.assigned_to:
        attrs["assigned_to"] = _resolve_assigned_to(project, args.assigned_to)

    us = project.add_user_story(args.subject, **attrs)
    print(f"Created user story #{us.ref}: {us.subject}")


@register("new-issue")
def cmd_new_issue(api, args):
    project = api.projects.get_by_slug(args.project)

    priorities = project.list_priorities()
    statuses = project.list_issue_statuses()
    types_ = project.list_issue_types()
    severities = project.list_severities()

    if not (priorities and statuses and types_ and severities):
        print(
            "Error: project is missing one of priorities/statuses/types/severities — cannot create an issue.",
            file=sys.stderr,
        )
        sys.exit(1)

    priority = _find_by_name(priorities, args.priority, "priority") if args.priority else priorities[0]
    status = _find_by_name(statuses, args.status, "status") if args.status else statuses[0]
    issue_type = _find_by_name(types_, args.type, "issue type") if args.type else types_[0]
    severity = _find_by_name(severities, args.severity, "severity") if args.severity else severities[0]

    attrs = {}
    if args.description:
        attrs["description"] = args.description
    if args.tags:
        attrs["tags"] = _split_csv(args.tags)
    if args.assigned_to:
        attrs["assigned_to"] = _resolve_assigned_to(project, args.assigned_to)

    issue = project.add_issue(args.subject, priority.id, status.id, issue_type.id, severity.id, **attrs)
    print(f"Created issue #{issue.ref}: {issue.subject}")


@register("tag")
def cmd_tag(api, args):
    project = api.projects.get_by_slug(args.project)
    item = _get_item(project, args.type, args.ref)
    current = _parse_tag_names(item.tags)

    if args.action == "list":
        if not current:
            print("(no tags)")
        else:
            for n in current:
                print(n)
        return

    incoming = _split_csv(args.tags)

    if args.action == "set":
        new_tags = incoming
    elif args.action == "add":
        new_tags = list(current)
        for t in incoming:
            if t not in new_tags:
                new_tags.append(t)
    elif args.action == "remove":
        new_tags = [n for n in current if n not in incoming]
    elif args.action == "clear":
        new_tags = []
    else:
        print(f"Error: unknown tag action '{args.action}'", file=sys.stderr)
        sys.exit(1)

    item.tags = new_tags
    item.patch(["tags", "version"])
    label = _kind_label(args.type)
    print(f"{label} #{item.ref} tags: {new_tags or '(none)'}")


@register("search")
def cmd_search(api, args):
    project = api.projects.get_by_slug(args.project)
    result = api.search(project.id, args.text)
    print(f"# Project: {project.name} (slug={project.slug}) — {result.count} matches for {args.text!r}\n")

    sections = [
        ("Epics", result.epics),
        ("User Stories", result.user_stories),
        ("Tasks", result.tasks),
        ("Issues", result.issues),
        ("Wiki Pages", result.wikipages),
    ]
    for label, items in sections:
        if not items:
            continue
        print(f"== {label} ({len(items)}) ==")
        for it in items:
            ref = getattr(it, "ref", None)
            ref_str = f"#{ref}\t" if ref else ""
            subject = getattr(it, "subject", None) or getattr(it, "slug", "?")
            print(f"  {ref_str}{subject}")
        print()


@register("edit")
def cmd_edit(api, args):
    project = api.projects.get_by_slug(args.project)
    item = _get_item(project, args.type, args.ref)

    changed = []
    if args.subject is not None:
        item.subject = args.subject
        changed.append("subject")
    if args.description is not None:
        item.description = args.description
        changed.append("description")
    if args.assigned_to is not None:
        item.assigned_to = (
            None if args.assigned_to.lower() in ("none", "unassigned", "")
            else _resolve_assigned_to(project, args.assigned_to)
        )
        changed.append("assigned_to")
    if args.due_date is not None:
        item.due_date = None if args.due_date.lower() in ("none", "clear", "") else args.due_date
        changed.append("due_date")

    if not changed:
        print("Error: nothing to edit — pass at least one of --subject / --description / --assigned-to / --due-date", file=sys.stderr)
        sys.exit(1)

    item.patch(changed + ["version"])
    print(f"{_kind_label(args.type)} #{item.ref} updated ({', '.join(changed)}): {item.subject}")


@register("delete")
def cmd_delete(api, args):
    if not args.yes:
        print("Error: refusing to delete without --yes confirmation.", file=sys.stderr)
        sys.exit(1)
    project = api.projects.get_by_slug(args.project)
    item = _get_item(project, args.type, args.ref)
    label = _kind_label(args.type)
    subject = item.subject
    ref = item.ref
    item.delete()
    print(f"Deleted {label} #{ref}: {subject}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="taiga",
        description="Taiga Shell — interact with Taiga from the command line",
    )
    parser.add_argument("--host", help="Taiga host URL (default: https://api.taiga.io)")
    parser.add_argument("--username", "-u", help="Username (overrides config)")
    parser.add_argument("--password", "-p", help="Password (overrides config)")

    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("projects", help="List your projects")
    p.add_argument("--all", action="store_true", help="Fetch all pages")

    p = sub.add_parser("stories", help="List user stories in a project")
    p.add_argument("project", help="Project slug")
    p.add_argument("--status", "-s", help="Filter by status name")
    p.add_argument("--assigned-to", "-a", help="Filter by assignee (username, email, or full name)")
    p.add_argument("--tags", help="Filter by tags (comma-separated)")
    p.add_argument("--milestone", "-m", help="Filter by milestone (id, slug, or name)")

    p = sub.add_parser("story", help="Show user story details")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="User story ref")

    p = sub.add_parser("tasks", help="List tasks in a project")
    p.add_argument("project", help="Project slug")
    p.add_argument("--status", "-s", help="Filter by status name")
    p.add_argument("--assigned-to", "-a", help="Filter by assignee (username, email, or full name)")
    p.add_argument("--tags", help="Filter by tags (comma-separated)")
    p.add_argument("--milestone", "-m", help="Filter by milestone (id, slug, or name)")

    p = sub.add_parser("task", help="Show task details")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="Task ref")

    p = sub.add_parser("issues", help="List issues in a project")
    p.add_argument("project", help="Project slug")
    p.add_argument("--status", "-s", help="Filter by status name")
    p.add_argument("--assigned-to", "-a", help="Filter by assignee (username, email, or full name)")
    p.add_argument("--tags", help="Filter by tags (comma-separated)")
    p.add_argument("--milestone", "-m", help="Filter by milestone (id, slug, or name)")
    p.add_argument("--priority", help="Filter by priority name")
    p.add_argument("--severity", help="Filter by severity name")
    p.add_argument("--issue-type", help="Filter by issue type name")

    p = sub.add_parser("issue", help="Show issue details")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="Issue ref")

    p = sub.add_parser("new-story", help="Create a new user story")
    p.add_argument("project", help="Project slug")
    p.add_argument("subject", help="User story subject")
    p.add_argument("--description", "-d", help="Description (Markdown supported)")
    p.add_argument("--status", "-s", help="Initial status name")
    p.add_argument("--tags", help="Comma-separated tag names")
    p.add_argument("--assigned-to", "-a", help="Username, email, or full name of assignee")

    p = sub.add_parser("new-issue", help="Create a new issue")
    p.add_argument("project", help="Project slug")
    p.add_argument("subject", help="Issue subject")
    p.add_argument("--description", "-d", help="Description (Markdown supported)")
    p.add_argument("--status", "-s", help="Status name (default: first available)")
    p.add_argument("--priority", help="Priority name (default: first available)")
    p.add_argument("--type", help="Issue type name (default: first available)")
    p.add_argument("--severity", help="Severity name (default: first available)")
    p.add_argument("--tags", help="Comma-separated tag names")
    p.add_argument("--assigned-to", "-a", help="Username, email, or full name of assignee")

    p = sub.add_parser("comment", help="Add a comment to a user story, task, or issue")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="User story / task / issue ref")
    p.add_argument("text", nargs="?", help="Comment text (Markdown supported)")
    p.add_argument("--file", "-f", help="Read comment text from file")
    p.add_argument("--type", "-t", choices=ITEM_KINDS, default="story", help="Item type (default: story)")

    p = sub.add_parser("attach", help="Attach a file (image, document, etc.) to a story, task, or issue")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="User story / task / issue ref")
    p.add_argument("file", help="Path to file to attach")
    p.add_argument("--description", "-d", default="", help="Attachment description")
    p.add_argument("--type", "-t", choices=ITEM_KINDS, default="story", help="Item type (default: story)")

    p = sub.add_parser("attachments", help="List attachments on a story, task, or issue")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="User story / task / issue ref")
    p.add_argument("--type", "-t", choices=ITEM_KINDS, default="story", help="Item type (default: story)")

    p = sub.add_parser("move", help="Update status of a task, user story, or issue")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="Task / user story / issue ref")
    p.add_argument("status", help="Target status name (use '?' to list available statuses)")
    p.add_argument("--type", "-t", choices=ITEM_KINDS, default="story", help="Item type (default: story)")

    p = sub.add_parser("tag", help="Add, remove, set, list, or clear tags on a story, task, or issue")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="User story / task / issue ref")
    p.add_argument("action", choices=["add", "remove", "set", "list", "clear"], help="Tag action")
    p.add_argument("tags", nargs="?", help="Comma-separated tag names (required for add/remove/set)")
    p.add_argument("--type", "-t", choices=ITEM_KINDS, default="story", help="Item type (default: story)")

    p = sub.add_parser("search", help="Search across stories, tasks, issues, epics, and wiki pages in a project")
    p.add_argument("project", help="Project slug")
    p.add_argument("text", help="Search text")

    p = sub.add_parser("edit", help="Edit subject / description / assignee / due-date on a story, task, or issue")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="User story / task / issue ref")
    p.add_argument("--subject", help="New subject")
    p.add_argument("--description", "-d", help="New description (Markdown supported)")
    p.add_argument(
        "--assigned-to", "-a",
        help="Username, email, or full name of assignee; pass 'none' or 'unassigned' to clear",
    )
    p.add_argument(
        "--due-date",
        help="ISO date (YYYY-MM-DD); pass 'none' or 'clear' to remove",
    )
    p.add_argument("--type", "-t", choices=ITEM_KINDS, default="story", help="Item type (default: story)")

    p = sub.add_parser("delete", help="Delete a story, task, or issue (requires --yes)")
    p.add_argument("project", help="Project slug")
    p.add_argument("ref", type=int, help="User story / task / issue ref")
    p.add_argument("--type", "-t", choices=ITEM_KINDS, default="story", help="Item type (default: story)")
    p.add_argument("--yes", action="store_true", help="Confirm deletion (required)")

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
