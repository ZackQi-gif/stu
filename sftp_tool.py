"""Simple unified SFTP upload/download utility.

This module provides a CLI that can upload or download single files or entire
folders via SFTP. Connection settings can be passed on the command line or
through a JSON configuration file.
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:
    import paramiko
except ImportError as exc:  # pragma: no cover - dependency error is user facing
    raise SystemExit(
        "paramiko is required to run this tool. Install it with 'pip install paramiko'."
    ) from exc


@dataclass
class ConnectionConfig:
    """Configuration values required to establish an SFTP connection."""

    host: str
    port: int = 22
    username: Optional[str] = None
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None
    known_hosts: Optional[str] = None
    timeout: Optional[float] = 10.0

    @classmethod
    def from_mapping(cls, mapping: dict[str, object]) -> "ConnectionConfig":
        return cls(
            host=str(mapping["host"]),
            port=int(mapping.get("port", 22)),
            username=_optional_str(mapping.get("username")),
            password=_optional_str(mapping.get("password")),
            private_key=_optional_str(mapping.get("private_key")),
            passphrase=_optional_str(mapping.get("passphrase")),
            known_hosts=_optional_str(mapping.get("known_hosts")),
            timeout=float(mapping.get("timeout", 10.0)) if mapping.get("timeout") is not None else None,
        )


def _optional_str(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _join_remote(*parts: str) -> str:
    """Join path fragments using POSIX separators suitable for SFTP."""

    cleaned = [part for part in parts if part not in (None, "")]
    if not cleaned:
        return ""
    return posixpath.join(*cleaned).replace("\\", "/")


class SFTPClient:
    """Small wrapper around paramiko's SFTP functionality."""

    def __init__(self, config: ConnectionConfig):
        self._config = config
        self._ssh: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None

    def __enter__(self) -> "SFTPClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def sftp(self) -> paramiko.SFTPClient:
        if self._sftp is None:
            raise RuntimeError("SFTP client is not connected")
        return self._sftp

    def connect(self) -> None:
        if self._ssh is not None:
            return
        self._ssh = paramiko.SSHClient()
        if self._config.known_hosts:
            self._ssh.load_host_keys(self._config.known_hosts)
        else:
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        pkey = None
        if self._config.private_key:
            key_path = os.path.expanduser(self._config.private_key)
            try:
                pkey = paramiko.RSAKey.from_private_key_file(key_path, password=self._config.passphrase)
            except paramiko.PasswordRequiredException:
                raise SystemExit("Private key requires a passphrase. Supply --passphrase or set it in the config file.")
            except FileNotFoundError:
                raise SystemExit(f"Private key not found: {key_path}") from None

        try:
            self._ssh.connect(
                self._config.host,
                port=self._config.port,
                username=self._config.username,
                password=self._config.password,
                pkey=pkey,
                timeout=self._config.timeout,
            )
        except paramiko.SSHException as exc:
            raise SystemExit(f"Unable to connect to {self._config.host}:{self._config.port} - {exc}") from exc

        self._sftp = self._ssh.open_sftp()

    def close(self) -> None:
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None
        if self._ssh is not None:
            self._ssh.close()
            self._ssh = None

    # Upload helpers ------------------------------------------------------------------
    def upload(self, local_path: str, remote_path: str) -> None:
        local_path = os.path.expanduser(local_path)
        if not os.path.exists(local_path):
            raise SystemExit(f"Local path does not exist: {local_path}")

        if os.path.isdir(local_path):
            self._upload_directory(local_path, remote_path)
        else:
            remote_dir = posixpath.dirname(remote_path)
            if remote_dir:
                self._ensure_remote_dir(remote_dir)
            print(f"Uploading file {local_path} -> {remote_path}")
            self.sftp.put(local_path, remote_path)

    def _upload_directory(self, local_dir: str, remote_dir: str) -> None:
        local_dir = os.path.abspath(local_dir)
        print(f"Uploading directory {local_dir} -> {remote_dir}")
        for root, dirs, files in os.walk(local_dir):
            rel_root = os.path.relpath(root, local_dir)
            rel_root = "" if rel_root == "." else rel_root
            remote_root = _join_remote(remote_dir, rel_root)
            self._ensure_remote_dir(remote_root)
            for filename in files:
                local_file = os.path.join(root, filename)
                remote_file = _join_remote(remote_root, filename)
                print(f"  - {local_file} -> {remote_file}")
                self.sftp.put(local_file, remote_file)

    # Download helpers ----------------------------------------------------------------
    def download(self, remote_path: str, local_path: str) -> None:
        if self._is_remote_dir(remote_path):
            self._download_directory(remote_path, local_path)
        else:
            local_parent = Path(local_path).expanduser().resolve().parent
            local_parent.mkdir(parents=True, exist_ok=True)
            print(f"Downloading file {remote_path} -> {local_path}")
            self.sftp.get(remote_path, local_path)

    def _download_directory(self, remote_dir: str, local_dir: str) -> None:
        local_dir_path = Path(local_dir).expanduser().resolve()
        print(f"Downloading directory {remote_dir} -> {local_dir_path}")
        local_dir_path.mkdir(parents=True, exist_ok=True)
        for entry in self.sftp.listdir_attr(remote_dir):
            remote_child = _join_remote(remote_dir, entry.filename)
            local_child = local_dir_path / entry.filename
            if stat.S_ISDIR(entry.st_mode):
                self._download_directory(remote_child, str(local_child))
            else:
                local_child.parent.mkdir(parents=True, exist_ok=True)
                print(f"  - {remote_child} -> {local_child}")
                self.sftp.get(remote_child, str(local_child))

    # Utility -------------------------------------------------------------------------
    def _ensure_remote_dir(self, remote_dir: str) -> None:
        if remote_dir in ("", "."):
            return
        parts: list[str] = []
        path = remote_dir
        while path not in ("", "/"):
            parts.append(path)
            path = posixpath.dirname(path)
        for directory in reversed(parts):
            try:
                self.sftp.stat(directory)
            except FileNotFoundError:
                print(f"Creating remote directory {directory}")
                self.sftp.mkdir(directory)

    def _is_remote_dir(self, remote_path: str) -> bool:
        try:
            info = self.sftp.stat(remote_path)
        except FileNotFoundError:
            raise SystemExit(f"Remote path does not exist: {remote_path}") from None
        return stat.S_ISDIR(info.st_mode)


# CLI -------------------------------------------------------------------------------

def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified SFTP upload/download tool")
    parser.add_argument("action", choices=["upload", "download"], help="Action to perform")
    parser.add_argument("local_path", help="Local path for upload/download")
    parser.add_argument("remote_path", help="Remote path for upload/download")

    parser.add_argument("--host", help="SFTP server host")
    parser.add_argument("--port", type=int, default=22, help="SFTP server port (default: 22)")
    parser.add_argument("--username", help="SFTP username")
    parser.add_argument("--password", help="SFTP password")
    parser.add_argument("--private-key", help="Path to a private key file for authentication")
    parser.add_argument("--passphrase", help="Passphrase for the private key, if required")
    parser.add_argument("--known-hosts", help="Path to known hosts file for host key verification")
    parser.add_argument("--timeout", type=float, default=10.0, help="Connection timeout in seconds")
    parser.add_argument("--config", help="Path to JSON configuration file with connection settings")

    args = parser.parse_args(argv)

    config = {}
    if args.config:
        config_path = Path(args.config).expanduser()
        if not config_path.exists():
            parser.error(f"Config file not found: {config_path}")
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            parser.error(f"Failed to parse JSON config: {exc}")

    merged = {
        "host": args.host or config.get("host"),
        "port": args.port if args.host or "port" not in config else config.get("port", args.port),
        "username": args.username or config.get("username"),
        "password": args.password or config.get("password"),
        "private_key": args.private_key or config.get("private_key"),
        "passphrase": args.passphrase or config.get("passphrase"),
        "known_hosts": args.known_hosts or config.get("known_hosts"),
        "timeout": args.timeout if args.host or "timeout" not in config else config.get("timeout", args.timeout),
    }

    missing = [key for key in ("host", "username") if not merged.get(key)]
    if missing:
        parser.error(f"Missing required connection options: {', '.join(missing)}")

    args.connection_config = ConnectionConfig.from_mapping(merged)
    return args


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)

    with SFTPClient(args.connection_config) as client:
        if args.action == "upload":
            client.upload(args.local_path, args.remote_path)
        else:
            client.download(args.remote_path, args.local_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
