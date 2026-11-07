#!/usr/bin/env python3
"""Publish the committed branch with a synchronized version above the target branch."""

import argparse
import json
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path

PLUGIN = Path("plugins/portfolio-analyser")
FILES = (
    PLUGIN / ".codex-plugin/plugin.json",
    PLUGIN / ".claude-plugin/plugin.json",
    Path(".claude-plugin/marketplace.json"),
)
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", re.ASCII)


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def config(key):
    result = subprocess.run(
        ["git", "config", "--get", key], text=True, capture_output=True, check=False
    )
    if result.returncode not in (0, 1):
        raise SystemExit("Cannot read Git configuration")
    return result.stdout.strip()


def entry(data, path):
    if path == FILES[2]:
        matches = [
            item for item in data["plugins"] if item["name"] == "portfolio-analyser"
        ]
        if len(matches) != 1:
            raise ValueError("Expected one portfolio-analyser marketplace entry")
        return matches[0]
    return data


def versions(commit):
    result = []
    for path in FILES:
        value = entry(json.loads(git("show", f"{commit}:{path}")), path)["version"]
        match = VERSION.fullmatch(value)
        if not match:
            raise ValueError(f"Expected major.minor.patch in {path}")
        result.append(tuple(map(int, match.groups())))
    return result


def consistent(commit):
    values = versions(commit)
    if len(set(values)) != 1:
        raise ValueError(f"Plugin manifests disagree at {commit}")
    return values[0]


def check(base, head):
    current = consistent(head)
    if base and base.strip("0") and base != head and current <= consistent(base):
        raise ValueError(
            "The plugin version must increase. Publish with 'git publish'."
        )


def commit_version(version):
    if git("status", "--porcelain", "--", *FILES):
        raise ValueError(
            "Version files have uncommitted changes. Commit or set them aside first."
        )
    originals = {path: path.read_bytes() for path in FILES}
    updated = {}
    try:
        for path, original in originals.items():
            data = json.loads(original)
            entry(data, path)["version"] = version
            updated[path] = (
                json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            ).encode()
            path.write_bytes(updated[path])
        git(
            "commit",
            "--only",
            "-m",
            f"Release portfolio-analyser {version}",
            "--",
            *FILES,
        )
    except BaseException:
        for path, content in updated.items():
            if path.read_bytes() == content:
                path.write_bytes(originals[path])
        raise


@contextmanager
def publish_lock():
    """Serialize publishers sharing a clone; closing the file releases the OS lock."""
    path = Path(git("rev-parse", "--git-common-dir")) / "portfolio-publish.lock"
    with path.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt

            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def publish(remote, branch):
    current = git("symbolic-ref", "--short", "HEAD")
    remote = remote or config(f"branch.{current}.remote") or "origin"
    target = (
        "refs/heads/" + branch
        if branch
        else config(f"branch.{current}.merge") or "refs/heads/" + current
    )
    if not target.startswith("refs/heads/") or remote.startswith("-"):
        raise ValueError("Expected a named remote and target branch")
    git("check-ref-format", target)
    urls = git("remote", "get-url", "--push", "--all", remote).splitlines()
    if len(urls) != 1:
        raise ValueError("Expected one push URL for the selected remote")
    remote_ref = git("ls-remote", "--refs", "--", urls[0], target)
    head = git("rev-parse", "HEAD")
    base = None
    if remote_ref:
        git("fetch", "--no-tags", "--", urls[0], target)
        base = git("rev-parse", "FETCH_HEAD")
        if base == head:
            print("Already published:", head)
            return
        git("merge-base", "--is-ancestor", base, head)
    local = versions(head)
    previous = consistent(base) if base else None
    higher = {value for value in local if previous is None or value > previous}
    if len(higher) > 1:
        raise ValueError("Conflicting release versions in local manifests")
    version = next(iter(higher)) if higher else (*previous[:2], previous[2] + 1)
    if any(value != version for value in local):
        commit_version(".".join(map(str, version)))
        head = git("rev-parse", "HEAD")
    check(base, head)
    subprocess.run(
        ["git", "push", "--no-follow-tags", "--", remote, f"{head}:{target}"],
        check=True,
    )
    print("Published", ".".join(map(str, version)), head, target)


def setup():
    path = config("core.hooksPath")
    alias = config("alias.publish")
    command = "!python3 scripts/publish.py push"
    if path and path != ".githooks":
        raise ValueError(
            "Existing core.hooksPath needs integration with .githooks/pre-push"
        )
    if alias and alias != command:
        raise ValueError("A different Git publish alias already exists")
    default = Path(git("rev-parse", "--git-common-dir")) / "hooks"
    if (
        not path
        and default.is_dir()
        and any(
            p.is_file() and not p.name.endswith(".sample") and p.stat().st_mode & 0o111
            for p in default.iterdir()
        )
    ):
        raise ValueError(
            "Existing Git hooks need integration before changing core.hooksPath"
        )
    git("config", "--local", "core.hooksPath", ".githooks")
    git("config", "--local", "alias.publish", command)
    print("Repository configured. Use git publish.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("setup")
    push = commands.add_parser("push")
    push.add_argument("remote", nargs="?")
    push.add_argument("branch", nargs="?")
    guard = commands.add_parser("check")
    guard.add_argument("base")
    guard.add_argument("head")
    args = parser.parse_args()
    if args.action == "setup":
        setup()
    elif args.action == "push":
        with publish_lock():
            publish(args.remote, args.branch)
    else:
        check(args.base, args.head)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
