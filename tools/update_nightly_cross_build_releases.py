# /// script
# dependencies = ["requests"]
# ///

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import requests

REPO = "pyodide/pyodide-build-environment-nightly"
BASE_URL = "https://github.com/{repo}/releases/download/{version}/{filename}"
RELEASE_FILENAME = "xbuildenv.tar.bz2"
DEBUG_FILENAME = "xbuildenv-debug.tar.bz2"

METADATA_FILE = Path(__file__).parents[1] / "nightly-cross-build-environments.json"
EMPTY_METADATA = '{"releases": {}}'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        "Update the nightly cross-build environments metadata file"
    )
    parser.add_argument("version", help="The nightly version tag (say, 20260520)")
    return parser.parse_args()


# If you want to test this locally, you can set a short-lived token
# with GITHUB_TOKEN=$(gh auth token --scopes repo) to avoid hitting the rate limit.
def _github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_archive(url: str) -> bytes | None:
    resp = requests.get(url)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content


def get_published_at(version: str) -> str:
    url = f"https://api.github.com/repos/{REPO}/releases/tags/{version}"
    resp = requests.get(url, headers=_github_headers())
    resp.raise_for_status()
    return resp.json()["published_at"]


def parse_env_var(content: str, var_name: str) -> str:
    for line in content.splitlines():
        if line.startswith(f"export {var_name}"):
            return line.split("=")[1].strip()
    return ""


@contextmanager
def extract_archive(archive: bytes) -> Generator[Path]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        archive_path = tmp_dir_path / "xbuildenv.tar.bz2"
        archive_path.write_bytes(archive)
        shutil.unpack_archive(str(archive_path), extract_dir=tmp_dir)
        yield tmp_dir_path


def _version_sort_key(tag: str) -> tuple[int, str]:
    date_part = int(tag[:8]) if len(tag) >= 8 and tag[:8].isdigit() else 0
    return (date_part, tag)


def add_version(
    raw_metadata: str,
    version: str,
    url: str,
    sha256: str,
    debug_url: str | None,
    debug_sha256: str | None,
    python_version: str,
    emscripten_version: str,
    published_at: str | None,
) -> str:
    metadata = json.loads(raw_metadata)
    metadata["releases"][version] = {
        "version": version,
        "url": url,
        "sha256": sha256,
        "debug_url": debug_url,
        "debug_sha256": debug_sha256,
        "python_version": python_version,
        "emscripten_version": emscripten_version,
        "published_at": published_at,
    }
    metadata["releases"] = dict(
        sorted(
            metadata["releases"].items(),
            key=lambda x: _version_sort_key(x[0]),
            reverse=True,
        )
    )
    return json.dumps(metadata, indent=2)


def main() -> None:
    args = parse_args()
    version = args.version

    release_url = BASE_URL.format(repo=REPO, version=version, filename=RELEASE_FILENAME)
    debug_url = BASE_URL.format(repo=REPO, version=version, filename=DEBUG_FILENAME)

    print(f"Downloading release tarball for {version} ...")
    release_content = get_archive(release_url)
    if release_content is None:
        sys.exit(f"Release tarball not found: {release_url}")
    release_sha256 = hashlib.sha256(release_content).hexdigest()

    with extract_archive(release_content) as extracted:
        makefile_path = extracted / "xbuildenv" / "pyodide-root" / "Makefile.envs"
        makefile_content = makefile_path.read_text()
        python_version = parse_env_var(makefile_content, "PYVERSION")
        emscripten_version = parse_env_var(
            makefile_content, "PYODIDE_EMSCRIPTEN_VERSION"
        )

    print(f"Downloading debug tarball for {version} ...")
    debug_content = get_archive(debug_url)
    if debug_content is not None:
        debug_sha256 = hashlib.sha256(debug_content).hexdigest()
        print(f"  debug build found (sha256={debug_sha256[:12]}...)")
    else:
        debug_url = None
        debug_sha256 = None
        print("  no debug build for this version")

    published_at = get_published_at(version)

    raw = METADATA_FILE.read_text() if METADATA_FILE.exists() else EMPTY_METADATA
    new_metadata = add_version(
        raw,
        version,
        release_url,
        release_sha256,
        debug_url,
        debug_sha256,
        python_version,
        emscripten_version,
        published_at,
    )
    METADATA_FILE.write_text(new_metadata + "\n")
    print(
        f"Updated metadata for {version}: "
        f"python={python_version} emscripten={emscripten_version} "
        f"published_at={published_at} debug={'yes' if debug_sha256 else 'no'}"
    )


if __name__ == "__main__":
    main()
