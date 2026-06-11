#!/usr/bin/env python3
"""
user_environment_config.py — one-time per-user setup on the GCP VM.

Run once after your first SSH login to:
  1. Fix ownership of /data and /opt/civic-pubtator so you can write without sudo.
  2. Configure your git identity for commits.
  3. Set up an SSH key for GitHub push access.

Usage:
    python3 /opt/civic-pubtator/src/cloud/user_environment_config.py
"""

import os
import pwd
import subprocess
import sys

REPO_DIR = '/opt/civic-pubtator'
DATA_DIR = '/data'


def run(cmd, check=True, **kwargs):
    result = subprocess.run(cmd, **kwargs)
    if check and result.returncode != 0:
        print(f"ERROR: command failed: {cmd}")
        sys.exit(result.returncode)
    return result


def section(title):
    print(f"\n{'─' * 64}")
    print(f"  {title}")
    print(f"{'─' * 64}")


def prompt(msg, default=None):
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"  {msg}{suffix}: ").strip()
        if val:
            return val
        if default is not None:
            return default
        print("  (required — please enter a value)")


def current_user():
    return pwd.getpwuid(os.getuid()).pw_name


# ── Step 1: Fix ownership ─────────────────────────────────────────────────────

def fix_ownership():
    section("Step 1: Fix directory ownership")
    user = current_user()
    dirs = [d for d in [DATA_DIR, REPO_DIR] if os.path.exists(d)]
    if not dirs:
        print("  Nothing to fix — neither /data nor /opt/civic-pubtator exists.")
        return
    print(f"  Changing ownership of the following to {user}:")
    for d in dirs:
        print(f"    {d}")
    print("  (sudo will prompt for your password if required)\n")
    for d in dirs:
        run(["sudo", "chown", "-R", f"{user}:{user}", d])
        print(f"  OK  {d}")


# ── Step 2: Git identity ──────────────────────────────────────────────────────

def _git_global_get(key):
    r = subprocess.run(["git", "config", "--global", key],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def configure_git():
    section("Step 2: Configure git identity")

    name  = prompt("Git user.name",  default=_git_global_get("user.name"))
    email = prompt("Git user.email", default=_git_global_get("user.email"))

    run(["git", "config", "--global", "user.name",  name])
    run(["git", "config", "--global", "user.email", email])
    # GCS sync and startup chown/chmod calls change file modes frequently;
    # ignore those changes so they never show up as unstaged diffs.
    run(["git", "config", "--global", "core.fileMode", "false"])
    print(f"\n  OK  ~/.gitconfig updated")

    if os.path.isdir(os.path.join(REPO_DIR, ".git")):
        run(["git", "-C", REPO_DIR, "config", "user.name",  name])
        run(["git", "-C", REPO_DIR, "config", "user.email", email])
        # Linux git clone overrides the global setting in the local config —
        # set it explicitly here too so it can't be re-enabled accidentally.
        run(["git", "-C", REPO_DIR, "config", "core.fileMode", "false"])
        print(f"  OK  {REPO_DIR}/.git/config updated")


# ── Step 3: SSH key for GitHub ────────────────────────────────────────────────

def _switch_remote_to_ssh():
    r = subprocess.run(
        ["git", "-C", REPO_DIR, "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    url = r.stdout.strip()
    if url.startswith("https://github.com/"):
        ssh_url = "git@github.com:" + url[len("https://github.com/"):]
        run(["git", "-C", REPO_DIR, "remote", "set-url", "origin", ssh_url])
        print(f"  OK  Remote switched to SSH: {ssh_url}")
    elif url.startswith("git@github.com"):
        print(f"  OK  Remote already uses SSH: {url}")
    else:
        print(f"  NOTE: Remote URL is {url!r} — not switching automatically.")


def setup_github_ssh():
    section("Step 3: Set up SSH key for GitHub push access")

    ssh_dir  = os.path.expanduser("~/.ssh")
    key_path = os.path.join(ssh_dir, "id_ed25519")
    pub_path = key_path + ".pub"
    os.makedirs(ssh_dir, mode=0o700, exist_ok=True)

    if os.path.isfile(key_path):
        print(f"  SSH key already exists: {key_path}")
    else:
        email = _git_global_get("user.email") or f"{current_user()}@civic-pubtator-vm"
        print(f"  Generating new ed25519 key ({email}) ...")
        run(["ssh-keygen", "-t", "ed25519", "-C", email, "-f", key_path, "-N", ""])
        print(f"  OK  Key written to {key_path}")

    with open(pub_path) as fh:
        pub_key = fh.read().strip()

    # Ensure github.com is in known_hosts so ssh -T doesn't prompt
    r = subprocess.run(["ssh-keygen", "-F", "github.com"], capture_output=True)
    if r.returncode != 0:
        known_hosts = os.path.join(ssh_dir, "known_hosts")
        subprocess.run(
            f"ssh-keyscan -t ed25519 github.com >> {known_hosts}",
            shell=True, check=False,
        )
        print("  OK  github.com added to ~/.ssh/known_hosts")

    print(f"""
  ┌──────────────────────────────────────────────────────────────┐
  │  Add this public key to your GitHub account:                 │
  │  https://github.com/settings/ssh/new                        │
  └──────────────────────────────────────────────────────────────┘

{pub_key}
""")
    input("  Press Enter after you have added the key to GitHub ... ")

    # Switch the remote to SSH now — before the connection test — so that
    # a failed test doesn't leave the remote pointing at HTTPS.
    _switch_remote_to_ssh()

    r = subprocess.run(
        ["ssh", "-T", "git@github.com"],
        capture_output=True, text=True,
    )
    # GitHub always returns exit code 1 for `ssh -T`, but prints "Hi <user>!"
    combined = (r.stdout + r.stderr).strip()
    if "successfully authenticated" in combined:
        print(f"  OK  {combined}")
    else:
        print(f"  WARNING: GitHub connection test gave an unexpected response:")
        print(f"    {combined}")
        print("  If the key was just added it may take a moment — retry with:")
        print("    ssh -T git@github.com")


# ── Step 4: Claude Code ───────────────────────────────────────────────────────

def install_claude_code():
    section("Step 4: Install Claude Code")

    local_bin = os.path.expanduser("~/.local/bin")
    claude_bin = os.path.join(local_bin, "claude")

    if os.path.isfile(claude_bin):
        r = subprocess.run([claude_bin, "--version"], capture_output=True, text=True)
        print(f"  Claude Code already installed: {r.stdout.strip() or claude_bin}")
    else:
        print("  Installing Claude Code via official install script ...")
        run("curl -fsSL https://claude.ai/install.sh | bash", shell=True)
        print(f"  OK  installed to {claude_bin}")

    # Ensure ~/.local/bin is on PATH in ~/.bashrc
    bashrc = os.path.expanduser("~/.bashrc")
    path_line = 'export PATH="$HOME/.local/bin:$PATH"'
    already_set = False
    if os.path.isfile(bashrc):
        with open(bashrc) as fh:
            already_set = any(".local/bin" in line for line in fh)
    if not already_set:
        with open(bashrc, "a") as fh:
            fh.write(f"\n{path_line}\n")
        print(f"  OK  added ~/.local/bin to PATH in ~/.bashrc")
    else:
        print(f"  OK  ~/.local/bin already in PATH in ~/.bashrc")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("=" * 64)
    print("  civic-pubtator VM — user environment setup")
    print("=" * 64)

    fix_ownership()
    configure_git()
    setup_github_ssh()
    install_claude_code()

    print(f"""
{'=' * 64}
  Setup complete.

  Quick-start commands:
    cd {REPO_DIR}
    git pull                    # sync latest code
    git add <file> && git commit -m "..." && git push

  Data sync:
    bash {REPO_DIR}/src/cloud/sync_pub_data.sh down [PMID]
    bash {REPO_DIR}/src/cloud/sync_tool_data.sh down

  Claude Code:
    source ~/.bashrc   # pick up updated PATH (or start a new session)
    claude --help
{'=' * 64}
""")


if __name__ == "__main__":
    main()
