import json
import secrets
import string
import subprocess
import time
from pathlib import Path

import ldb
from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB


BASE_DN = "DC=netopslab,DC=test"
CONFIG_PATH = Path("/config/ad_baseline.json")
MIGRATION_MARKER = Path("/etc/samba/.netops-baseline-v5")


def run(*arguments):
    subprocess.run(["samba-tool", *arguments], check=True)


def exists(*arguments):
    return subprocess.run(
        ["samba-tool", *arguments],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def ou_exists(distinguished_name):
    result = subprocess.run(
        ["samba-tool", "ou", "list"],
        capture_output=True,
        check=True,
        text=True,
    )
    relative_name = distinguished_name.removesuffix(f",{BASE_DN}")
    return relative_name.lower() in {
        line.strip().lower() for line in result.stdout.splitlines()
    }


def temporary_password():
    alphabet = string.ascii_letters + string.digits + "!@#%"
    return "N0!" + "".join(secrets.choice(alphabet) for _ in range(21))


def set_user_attribute(username, attribute, value):
    load_parameters = LoadParm()
    load_parameters.load("/etc/samba/smb.conf")
    database = SamDB(
        url="/var/lib/samba/private/sam.ldb",
        session_info=system_session(),
        lp=load_parameters,
    )
    result = database.search(
        base=BASE_DN,
        expression=f"(sAMAccountName={username})",
        attrs=[attribute],
    )
    if not result:
        raise RuntimeError(f"Unable to find managed user {username}")
    message = ldb.Message()
    message.dn = result[0].dn
    message[attribute] = ldb.MessageElement(
        str(value), ldb.FLAG_MOD_REPLACE, attribute
    )
    database.modify(message)


def provision():
    baseline = json.loads(CONFIG_PATH.read_text())
    if MIGRATION_MARKER.exists():
        return

    if not ou_exists(f"OU=NetOpsLab,{BASE_DN}"):
        run("ou", "create", f"OU=NetOpsLab,{BASE_DN}")
    for name in ("Users", "Workstations", "Laptops", "Servers", "Groups", "Admins"):
        distinguished_name = f"OU={name},OU=NetOpsLab,{BASE_DN}"
        if not ou_exists(distinguished_name):
            run("ou", "create", distinguished_name)

    for group in baseline["groups"]:
        if not exists("group", "show", group["name"]):
            run(
                "group", "add", group["name"],
                "--groupou=OU=Groups,OU=NetOpsLab",
                f"--description={group['description']}",
            )

    for user in baseline["users"]:
        is_new = not exists("user", "show", user["username"])
        if is_new:
            user_ou = user.get("ou", "Users")
            run(
                "user", "create", user["username"], temporary_password(),
                f"--userou=OU={user_ou},OU=NetOpsLab",
                f"--given-name={user['given_name']}",
                f"--surname={user['surname']}",
            )
        for group in baseline["groups"]:
            members = subprocess.run(
                ["samba-tool", "group", "listmembers", group["name"]],
                capture_output=True,
                check=True,
                text=True,
            ).stdout.splitlines()
            is_member = user["username"].lower() in {
                member.strip().lower() for member in members
            }
            should_be_member = group["name"] in user["groups"]
            if should_be_member and not is_member:
                run("group", "addmembers", group["name"], user["username"])
            elif is_member and not should_be_member:
                run("group", "removemembers", group["name"], user["username"])
        if is_new and user.get("disabled"):
            run("user", "disable", user["username"])

    for username in baseline.get("deprecated_users", []):
        if exists("user", "show", username):
            run("user", "delete", username)

    for group in baseline.get("deprecated_groups", []):
        if exists("group", "show", group):
            run("group", "delete", group)

    for number in range(1, 10):
        computer = f"WS{number:02d}"
        if not exists("computer", "show", computer):
            run(
                "computer", "create", computer,
                "--computerou=OU=Workstations,OU=NetOpsLab",
            )

    for number in range(1, 7):
        computer = f"LTP{number:02d}"
        if not exists("computer", "show", computer):
            run("computer", "create", computer, "--computerou=OU=Laptops,OU=NetOpsLab")
        else:
            run("computer", "move", computer, f"OU=Laptops,OU=NetOpsLab,{BASE_DN}")

    if not exists("computer", "show", "FILE01"):
        run("computer", "create", "FILE01", "--computerou=OU=Servers,OU=NetOpsLab")

    domain_admin_members = subprocess.run(
        ["samba-tool", "group", "listmembers", "Domain Admins"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.splitlines()
    if "it-admins" not in {member.strip().lower() for member in domain_admin_members}:
        run("group", "addmembers", "Domain Admins", "IT-Admins")

    run("user", "setexpiry", "svc_monitor", "--noexpiry")
    run(
        "user", "setpassword", "sam.patel",
        f"--newpassword={temporary_password()}",
        "--must-change-at-next-login",
    )
    windows_now = int((time.time() + 11644473600) * 10_000_000)
    set_user_attribute("alex.kim", "lockoutTime", windows_now)

    run("domain", "passwordsettings", "set", "--complexity=on")
    run("domain", "passwordsettings", "set", "--min-pwd-length=10")
    run("domain", "passwordsettings", "set", "--history-length=24")
    run("domain", "passwordsettings", "set", "--min-pwd-age=1")
    run("domain", "passwordsettings", "set", "--max-pwd-age=42")
    run("domain", "passwordsettings", "set", "--account-lockout-threshold=3")
    run("domain", "passwordsettings", "set", "--account-lockout-duration=15")
    run("domain", "passwordsettings", "set", "--reset-account-lockout-after=30")
    MIGRATION_MARKER.touch()


if __name__ == "__main__":
    provision()
