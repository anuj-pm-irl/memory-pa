from __future__ import annotations

import io
import re
import stat
import uuid
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile, ZipFile, ZipInfo

from ..errors import Conflict, MemoryPAError, UncertainWrite
from ..files import (
    MAX_TREE_BYTES,
    check_limits,
    check_path,
    check_tree,
    digest,
    json_bytes,
    parse_json,
)
from . import Revision

MAX_ARCHIVE_BYTES = MAX_TREE_BYTES + 6 * 1024 * 1024


def _archive(files) -> bytes:
    check_tree(files)
    result = io.BytesIO()
    with ZipFile(result, "w") as archive:
        for path, body in sorted(files.items()):
            archive.writestr(ZipInfo(path), body)
    return result.getvalue()


def _unarchive(raw: bytes) -> dict[str, bytes]:
    files = {}
    total = 0
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            for entry in entries:
                check_path(entry.filename)
                if entry.filename in files or stat.S_IFMT(entry.external_attr >> 16) not in (
                    0,
                    stat.S_IFREG,
                ):
                    raise MemoryPAError("S3 archive entries must be unique regular files.")
                total += entry.file_size
                check_limits(len(entries), entry.file_size, total)
                files[entry.filename] = archive.read(entry)
    except (BadZipFile, NotImplementedError, RuntimeError, EOFError) as exc:
        raise MemoryPAError("Could not read the S3 snapshot archive.") from exc
    return files


def _status(error) -> int:
    return getattr(error, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode", 0)


class S3Storage:
    def __init__(self, url: str, client=None, *, profile: str | None = None):
        target = urlsplit(url)
        prefix = unquote(target.path).strip("/")
        self.bucket = target.netloc
        if target.scheme != "s3" or not re.fullmatch(
            r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.bucket
        ):
            raise MemoryPAError("Use an S3 bucket URL with a workspace prefix.")
        if (
            target.query
            or target.fragment
            or not prefix
            or any(part in {"", ".", ".."} for part in prefix.split("/"))
        ):
            raise MemoryPAError("Use an S3 bucket URL with a workspace prefix.")
        if len(prefix.encode("utf-8")) > 900 or any(ord(character) < 32 for character in prefix):
            raise MemoryPAError(
                "The S3 workspace prefix is too long or contains control characters."
            )
        self.prefix = prefix
        try:
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError as exc:
            raise MemoryPAError("Install the memory-pa[s3] extra to use S3.") from exc

        self._request_errors = (BotoCoreError, ClientError, OSError)
        if client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise MemoryPAError("Install the memory-pa[s3] extra to use S3.") from exc
            try:
                session = boto3.Session(profile_name=profile) if profile else boto3
                client = session.client("s3", config=Config(retries={"total_max_attempts": 1}))
            except (BotoCoreError, ClientError) as exc:
                raise MemoryPAError(
                    "Could not load your AWS credentials or configuration."
                ) from exc
        self.client = client

    def _get(self, name: str, maximum: int) -> tuple[str | None, bytes]:
        response = self.client.get_object(Bucket=self.bucket, Key=f"{self.prefix}/{name}")
        stream = response["Body"]
        try:
            data = stream.read(maximum + 1)
            if len(data) > maximum:
                raise MemoryPAError("An S3 workspace object exceeds the v1 size limit.")
            return response.get("ETag"), data
        finally:
            stream.close()

    def _put(self, name: str, data: bytes, content_type: str, **condition):
        return self.client.put_object(
            Bucket=self.bucket,
            Key=f"{self.prefix}/{name}",
            Body=data,
            ContentType=content_type,
            **condition,
        )

    def _head(self) -> tuple[str | None, bytes]:
        try:
            etag, raw = self._get("HEAD.json", 4096)
        except MemoryPAError:
            raise
        except self._request_errors as exc:
            if (
                _status(exc) == 404
                and getattr(exc, "response", {}).get("Error", {}).get("Code") != "NoSuchBucket"
            ):
                return None, b""
            raise MemoryPAError(
                "Could not read the S3 workspace head. Check access to the bucket and prefix."
            ) from exc
        if not etag:
            raise MemoryPAError("The S3 workspace head is missing an ETag.")
        return etag, raw

    def _verified_archive(self, fingerprint) -> bytes:
        try:
            _, raw = self._get(f"revisions/{fingerprint}.zip", MAX_ARCHIVE_BYTES)
        except MemoryPAError:
            raise
        except self._request_errors as exc:
            raise MemoryPAError("Could not read the S3 workspace archive.") from exc
        if digest(raw) != fingerprint:
            raise MemoryPAError("The S3 archive does not match its SHA-256 digest.")
        return raw

    def read(self) -> Revision:
        token, raw = self._head()
        if token is None:
            return Revision(None, {})
        head = parse_json(raw, "the S3 workspace head")
        if (
            not isinstance(head, dict)
            or set(head) != {"archive", "revision"}
            or not isinstance(head["archive"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", head["archive"])
            or not isinstance(head["revision"], str)
            or not re.fullmatch(r"[a-f0-9]{32}", head["revision"])
        ):
            raise MemoryPAError("Invalid S3 workspace head.")
        return Revision(token, _unarchive(self._verified_archive(head["archive"])))

    def publish(self, expected, files) -> str:
        raw = _archive(files)
        fingerprint = digest(raw)
        try:
            self._put(f"revisions/{fingerprint}.zip", raw, "application/zip", IfNoneMatch="*")
        except self._request_errors as exc:
            if _status(exc) == 412:
                self._verified_archive(fingerprint)
            else:
                raise MemoryPAError(
                    "Could not stage the S3 archive. Preview the note again before retrying."
                ) from exc
        body = json_bytes({"archive": fingerprint, "revision": uuid.uuid4().hex})
        condition = {"IfMatch": expected} if expected is not None else {"IfNoneMatch": "*"}
        status = 0
        try:
            response = self._put("HEAD.json", body, "application/json", **condition)
            if response.get("ETag"):
                return response["ETag"]
        except self._request_errors as exc:
            status = _status(exc)
        try:
            token, stored = self._head()
            if token and body == stored:
                return token
        except MemoryPAError:
            pass
        if status in {409, 412}:
            raise Conflict("The S3 workspace changed. Preview the note again.")
        raise UncertainWrite(
            "Could not confirm the S3 write. Preview again to check for an existing note."
        )
