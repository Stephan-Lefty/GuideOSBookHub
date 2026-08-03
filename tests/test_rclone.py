import subprocess

import pytest

from core import rclone


class _FakeCompletedProcess:
    def __init__(self, args):
        self.args = args
        self.returncode = 0
        self.stdout = ""
        self.stderr = ""


@pytest.fixture
def captured_run(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return _FakeCompletedProcess(args)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_create_webdav_remote_builds_correct_args(captured_run):
    rclone.create_webdav_remote(
        "mynextcloud", "https://cloud.example.com/remote.php/dav/files/bob/",
        "nextcloud", "bob", "s3cr3t",
    )

    assert captured_run == [[
        "rclone", "--retries", "1", "config", "create", "mynextcloud", "webdav",
        "url", "https://cloud.example.com/remote.php/dav/files/bob/",
        "vendor", "nextcloud", "user", "bob", "pass", "s3cr3t", "--obscure",
    ]]


def test_delete_remote_builds_correct_args(captured_run):
    rclone.delete_remote("mynextcloud")

    assert captured_run == [["rclone", "--retries", "1", "config", "delete", "mynextcloud"]]


@pytest.mark.parametrize("url,vendor,expected", [
    ("https://cloud.example.com", "nextcloud",
     "https://cloud.example.com/remote.php/dav/files/bob/"),
    ("https://cloud.example.com/", "nextcloud",
     "https://cloud.example.com/remote.php/dav/files/bob/"),
    ("https://cloud.example.com", "owncloud", "https://cloud.example.com/remote.php/webdav/"),
    ("https://cloud.example.com/remote.php/dav/files/bob/", "nextcloud",
     "https://cloud.example.com/remote.php/dav/files/bob/"),
    ("https://webdav.example.com/some/path", "other", "https://webdav.example.com/some/path"),
])
def test_normalize_webdav_url(url, vendor, expected):
    assert rclone.normalize_webdav_url(url, vendor, "bob") == expected


def test_create_protondrive_remote_minimal_args(captured_run):
    rclone.create_protondrive_remote("proton", "bob@proton.me", "s3cr3t")

    assert captured_run == [[
        "rclone", "--retries", "1", "config", "create", "proton", "protondrive",
        "username", "bob@proton.me", "pass", "s3cr3t", "--obscure",
    ]]


def test_create_protondrive_remote_with_2fa_and_mailbox_password(captured_run):
    rclone.create_protondrive_remote(
        "proton", "bob@proton.me", "s3cr3t", twofa="123456", mailbox_password="mbpass"
    )

    assert captured_run == [[
        "rclone", "--retries", "1", "config", "create", "proton", "protondrive",
        "username", "bob@proton.me", "pass", "s3cr3t",
        "2fa", "123456", "mailbox-password", "mbpass", "--obscure",
    ]]


def test_create_oauth_remote_builds_correct_args(captured_run):
    rclone.create_oauth_remote("gdrive", "drive", '{"access_token":"x"}')

    assert captured_run == [[
        "rclone", "--retries", "1", "config", "create", "gdrive", "drive",
        "config_token", '{"access_token":"x"}',
    ]]


def test_extract_oauth_token_finds_json_line():
    output = (
        "If your browser doesn't open automatically go to the following link\n"
        "Waiting for code...\n"
        "Paste the following into your remote machine --->\n"
        '{"access_token":"abc","token_type":"Bearer"}\n'
        "<---End paste"
    )
    assert rclone._extract_oauth_token(output) == '{"access_token":"abc","token_type":"Bearer"}'


def test_extract_oauth_token_raises_without_json_line():
    with pytest.raises(rclone.RcloneRemoteError):
        rclone._extract_oauth_token("no token here\njust text")


@pytest.mark.parametrize("remote,path,expected", [
    ("mynextcloud", "GuideOSBookHub/bookmarks.json", "mynextcloud:GuideOSBookHub/bookmarks.json"),
    ("", "/media/usb/GuideOSBookHub/bookmarks.json", "/media/usb/GuideOSBookHub/bookmarks.json"),
])
def test_target_local_vs_remote(remote, path, expected):
    assert rclone._target(remote, path) == expected


def test_is_local_folder_writable_true_for_existing_writable_dir(tmp_path):
    assert rclone.is_local_folder_writable(str(tmp_path)) is True


def test_is_local_folder_writable_false_for_missing_dir(tmp_path):
    assert rclone.is_local_folder_writable(str(tmp_path / "does-not-exist")) is False
