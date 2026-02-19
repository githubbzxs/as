from __future__ import annotations

import os
import sys

import paramiko


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/ssh_upload.py <local_path> <remote_path>")
        return 2

    host = os.environ["DEPLOY_HOST"]
    user = os.environ["DEPLOY_USER"]
    password = os.environ["DEPLOY_PASSWORD"]
    port = int(os.environ.get("DEPLOY_PORT", "22"))

    local_path = sys.argv[1]
    remote_path = sys.argv[2]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, password=password, port=port, timeout=20)

    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    client.close()

    print(f"uploaded {local_path} -> {remote_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
