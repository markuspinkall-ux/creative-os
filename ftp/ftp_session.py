"""FTP, explicit FTPS and SFTP operations for Creative FTP."""

import base64
import ftplib
import hashlib
import os
import posixpath
import re
import ssl
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import paramiko


class UnknownHostKey(paramiko.SSHException):
    def __init__(self, host, key):
        super().__init__(f"Unbekannter SSH-Schlüssel für {host}")
        self.host = host
        self.key = key
        self.fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")


class AskHostKey(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        raise UnknownHostKey(hostname, key)


def safe_name(name):
    return bool(name and name not in (".", "..") and not any(c in name for c in "/\r\n\0"))


class Session:
    def __init__(self, profile, password, trusted_keys):
        self.sftp = None
        self.ftp = None
        self.ssh = None
        host, port, user = (profile[key] for key in ("host", "port", "user"))
        try:
            if profile["protocol"] == "SFTP":
                self.ssh = paramiko.SSHClient()
                self.ssh.load_system_host_keys()
                if trusted_keys.exists():
                    self.ssh.load_host_keys(str(trusted_keys))
                self.ssh.set_missing_host_key_policy(AskHostKey())
                self.ssh.connect(host, port, username=user, password=password or None,
                                 key_filename=profile.get("key") or None, timeout=12,
                                 banner_timeout=12, auth_timeout=12, channel_timeout=12)
                self.sftp = self.ssh.open_sftp()
                self.sftp.get_channel().settimeout(12)
            else:
                self.ftp = (ftplib.FTP_TLS(context=ssl.create_default_context())
                            if profile["protocol"] == "FTPS" else ftplib.FTP())
                self.ftp.connect(host, port, timeout=12)
                self.ftp.login(user or "anonymous", password)
                if isinstance(self.ftp, ftplib.FTP_TLS):
                    self.ftp.prot_p()
        except Exception:
            self.close()
            raise

    def close(self):
        if self.ssh:
            self.ssh.close()
        if self.ftp:
            self.ftp.close()

    def home(self):
        return self.sftp.normalize(".") if self.sftp else self.ftp.pwd()

    def list(self, path):
        if self.sftp:
            entries = [(item.filename, stat.S_ISDIR(item.st_mode or 0), item.st_size)
                       for item in self.sftp.listdir_attr(path)]
        else:
            try:
                entries = [(name, facts.get("type") == "dir",
                            int(facts["size"]) if facts.get("size", "").isdigit() else None)
                           for name, facts in self.ftp.mlsd(path)
                           if facts.get("type") not in ("cdir", "pdir")]
            except ftplib.error_perm as error:
                if not str(error).startswith(("500", "501", "502", "504")):
                    raise
                entries = self.legacy_list(path)
        return sorted((entry for entry in entries if safe_name(entry[0])),
                      key=lambda entry: (not entry[1], entry[0].casefold()))

    def legacy_list(self, path):
        lines = []
        self.ftp.retrlines(f"LIST {path}", lines.append)
        entries = []
        for line in lines:
            fields = line.split(None, 8)
            if len(fields) == 9 and re.fullmatch(r"[-dl][rwxstST-]{9}[+.@]?", fields[0]):
                name = fields[8].split(" -> ", 1)[0] if fields[0][0] == "l" else fields[8]
                entries.append((name, fields[0][0] == "d", int(fields[4]) if fields[4].isdigit() else None))
                continue
            dos = re.fullmatch(r"\d{2}-\d{2}-\d{2,4}\s+\d{1,2}:\d{2}(?:AM|PM)\s+(<DIR>|\d+)\s+(.*)", line, re.I)
            if dos:
                size, name = dos.groups()
                entries.append((name, size.upper() == "<DIR>", int(size) if size.isdigit() else None))
        if lines and not entries and any(not line.startswith("total ") for line in lines):
            raise OSError("Der Server liefert ein unbekanntes Verzeichnisformat.")
        return entries

    def mkdir(self, path):
        return self.sftp.mkdir(path) if self.sftp else self.ftp.mkd(path)

    def rename(self, source, target):
        return self.sftp.rename(source, target) if self.sftp else self.ftp.rename(source, target)

    def remove(self, path, directory):
        if self.sftp:
            return self.sftp.rmdir(path) if directory else self.sftp.remove(path)
        return self.ftp.rmd(path) if directory else self.ftp.delete(path)

    def transfer(self, upload, source, target, directory, progress, created, completed):
        transferred = 0

        def copy(src, dst, is_dir, depth):
            nonlocal transferred
            progress(transferred)
            if not is_dir:
                if dst in completed:
                    return
                action = self.upload if upload else self.download
                base = transferred

                def report(size):
                    nonlocal transferred
                    transferred = base + size
                    progress(transferred)

                action(src, dst, report)
                completed.add(dst)
                return
            if depth > 64:
                raise OSError("Zu viele verschachtelte Ordner.")
            if upload and Path(src).is_symlink():
                raise OSError(f"Verknüpfter Ordner wird nicht hochgeladen: {src}")
            if dst not in created:
                if upload:
                    self.mkdir(dst)
                else:
                    Path(dst).mkdir()
                created.add(dst)
            if upload:
                with os.scandir(src) as listing:
                    entries = [(entry.name, entry.is_dir(follow_symlinks=False)) for entry in listing
                               if safe_name(entry.name) and (entry.is_dir(follow_symlinks=False)
                                   or entry.is_file(follow_symlinks=False))]
            else:
                entries = [(name, folder) for name, folder, _ in self.list(src)]
            for name, folder in entries:
                copy(posixpath.join(src, name), posixpath.join(dst, name), folder, depth + 1)

        copy(source, target, directory, 0)

    def download(self, source, target, progress):
        target = Path(target)
        temporary = None
        try:
            with NamedTemporaryFile(dir=target.parent, prefix=".creative-ftp-", delete=False) as output:
                temporary = Path(output.name)
                if self.sftp:
                    self.sftp.getfo(source, output, lambda done, _: progress(done), prefetch=False)
                else:
                    def write(block):
                        output.write(block)
                        progress(output.tell())
                    self.ftp.retrbinary(f"RETR {source}", write, 65536)
            # A destination created during the transfer must remain intact.
            os.link(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def upload(self, source, target, progress):
        folder, name = posixpath.split(target)
        if any(entry[0] == name for entry in self.list(folder)):
            raise FileExistsError(f"Zieldatei existiert bereits: {name}")
        temporary = posixpath.join(folder, f".creative-ftp-{uuid4().hex}")
        try:
            with open(source, "rb", opener=lambda path, flags: os.open(path, flags | os.O_NONBLOCK)) as data:
                info = os.fstat(data.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise OSError(f"Keine reguläre Datei: {source}")
                if self.sftp:
                    self.sftp.putfo(data, temporary, info.st_size,
                                    lambda done, _: progress(done))
                else:
                    self.ftp.storbinary(f"STOR {temporary}", data, 65536, lambda _: progress(data.tell()))
            if any(entry[0] == name for entry in self.list(folder)):
                raise FileExistsError(f"Zieldatei existiert bereits: {name}")
            self.rename(temporary, target)
        except Exception:
            try:
                self.remove(temporary, False)
            except Exception:
                pass
            raise
