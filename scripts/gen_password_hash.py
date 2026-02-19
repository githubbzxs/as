from __future__ import annotations

import getpass

from passlib.context import CryptContext


def main() -> None:
    ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    password = getpass.getpass("请输入明文密码: ")
    print(ctx.hash(password))


if __name__ == "__main__":
    main()
