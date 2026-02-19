from __future__ import annotations

import os
import sys

import paramiko


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/ssh_exec.py \"<command>\"")
        return 2

    host = os.environ["DEPLOY_HOST"]
    user = os.environ["DEPLOY_USER"]
    password = os.environ["DEPLOY_PASSWORD"]
    port = int(os.environ.get("DEPLOY_PORT", "22"))

    command = sys.argv[1]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, password=password, port=port, timeout=20)

    stdin, stdout, stderr = client.exec_command(command, timeout=1800)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    code = stdout.channel.recv_exit_status()

    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)

    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
