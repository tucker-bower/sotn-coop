"""Android (design/M9-android.md): what the launcher needs from the device, through pyjnius.

    ANDROID                     True when running as the Android app (python-for-android)
    external_dir() -> Path      the app's own folder a PC can see over USB
                                (Android/data/<package>/files): the data folder, and the discs
    pick_files(title) -> [Path] the system's file picker (several files at once: a .cue and its
                                .bin files), each copied into the app's folder
"""

import os
import sys
import time
from pathlib import Path

ANDROID = sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ


def _activity():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonActivity").mActivity


def external_dir():
    return Path(_activity().getExternalFilesDir(None).getAbsolutePath())


def cache_dir():
    return Path(_activity().getCacheDir().getAbsolutePath())


def abi():
    from jnius import autoclass
    return autoclass("android.os.Build").SUPPORTED_ABIS[0]


def pick_files(title, folder):
    """The system's picker (ACTION_OPEN_DOCUMENT, several files): each chosen file is copied
    into folder, under its own name. [] if the player backs out."""
    import pygame
    from android import activity  # python-for-android
    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    OpenableColumns = autoclass("android.provider.OpenableColumns")
    REQUEST = 4711
    result = {}

    def on_result(request, code, data):
        if request == REQUEST:
            result["code"], result["data"] = code, data

    activity.bind(on_activity_result=on_result)
    try:
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType("*/*")
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)
        intent.putExtra(Intent.EXTRA_TITLE, title)
        _activity().startActivityForResult(intent, REQUEST)
        while "code" not in result:  # the picker is another activity: keep the window alive
            pygame.event.pump()
            time.sleep(0.05)
    finally:
        activity.unbind(on_activity_result=on_result)
    data = result.get("data")
    if result["code"] != -1 or data is None:  # Activity.RESULT_OK
        return []
    uris = []
    clip = data.getClipData()
    if clip is not None:
        uris = [clip.getItemAt(i).getUri() for i in range(clip.getItemCount())]
    elif data.getData() is not None:
        uris = [data.getData()]
    resolver = _activity().getContentResolver()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for uri in uris:
        name = "file"
        cursor = resolver.query(uri, None, None, None, None)
        if cursor is not None and cursor.moveToFirst():
            name = cursor.getString(cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)) or name
            cursor.close()
        stream = resolver.openInputStream(uri)
        target = folder / Path(name).name
        with open(target, "wb") as f:
            while True:
                chunk = _read_chunk(stream)
                if not chunk:
                    break
                f.write(chunk)
        stream.close()
        out.append(target)
    return out


def _read_chunk(stream, size=1 << 20):
    """Reads up to size bytes from a java.io.InputStream (pyjnius fills a Python bytearray)."""
    buf = bytearray(size)
    n = stream.read(buf, 0, size)
    if n is None or n <= 0:
        return b""
    return bytes(buf[:n])
