"""Android (design/M9-android.md): what the launcher needs from the device, through pyjnius.

    ANDROID                     True when running as the Android app (python-for-android)
    external_dir() -> Path      the app's own folder a PC can see over USB
                                (Android/data/<package>/files): the data folder, and the discs
    pick_files(title, folder) -> [Path]   the system's file picker, each chosen file copied
                                into folder
    pick_disc(title, folder) -> Path      the system's folder picker: the player picks the
                                folder their disc image is in (one tap), and its .cue and the
                                .bin files it names (or a .zip of them) are copied into folder
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


def _run_picker(intent):
    """Starts a picker activity and waits for it: its result Intent, or None if backed out."""
    import pygame
    from android import activity  # python-for-android

    REQUEST = 4711
    result = {}

    def on_result(request, code, data):
        if request == REQUEST:
            result["code"], result["data"] = code, data

    activity.bind(on_activity_result=on_result)
    try:
        _activity().startActivityForResult(intent, REQUEST)
        while "code" not in result:  # the picker is another activity: keep the window alive
            pygame.event.pump()
            time.sleep(0.05)
    finally:
        activity.unbind(on_activity_result=on_result)
    return result["data"] if result["code"] == -1 else None  # Activity.RESULT_OK


def _copy(uri, target, progress=None):
    """A document into a file; progress(bytes so far) as it goes."""
    resolver = _activity().getContentResolver()
    stream = resolver.openInputStream(uri)
    try:
        with open(target, "wb") as f:
            while True:
                chunk = _read_chunk(stream)
                if not chunk:
                    break
                f.write(chunk)
                if progress:
                    progress(f.tell())
    finally:
        stream.close()
    return target


def pick_files(title, folder):
    """The system's picker (ACTION_OPEN_DOCUMENT, several files): each chosen file is copied
    into folder, under its own name. [] if the player backs out."""
    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    OpenableColumns = autoclass("android.provider.OpenableColumns")
    intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
    intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType("*/*")
    intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)
    intent.putExtra(Intent.EXTRA_TITLE, title)
    data = _run_picker(intent)
    if data is None:
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
        out.append(_copy(uri, folder / Path(name).name))
    return out


def disc_files(names, read_text):
    """Which of a folder's files make the SOTN disc image: a .cue and the files it names (the
    .cue most likely to be SOTN's when there are several), else a lone .bin, else a .zip.
    names: the folder's file names; read_text(name): a .cue's text. [(file, name to save it
    as: the one the .cue uses, as Android's names are case-sensitive)], [] if there's nothing."""
    import patcher
    by_lower = {n.lower(): n for n in names}
    complete = []
    for cue in sorted(n for n in names if n.lower().endswith(".cue")):
        listed = patcher.cue_files(read_text(cue))
        if listed and all(f.lower() in by_lower for f in listed):
            complete.append([(cue, cue)] + [(by_lower[f.lower()], f) for f in listed])
    if complete:
        complete.sort(key=lambda files: not any(k in files[0][0].lower() for k in ("symphony", "sotn", "slus-00067")))
        return complete[0]
    bins = [n for n in names if n.lower().endswith(".bin")]
    if len(bins) == 1:
        return [(bins[0], bins[0])]
    zips = [n for n in names if n.lower().endswith(".zip")]
    return [(z, z) for z in zips[:1]]


def pick_disc(title, folder, run=None):
    """The system's folder picker (ACTION_OPEN_DOCUMENT_TREE): the disc image in the chosen
    folder is copied into folder (a .zip is unpacked). Its .cue (or .bin), or None if the player
    backed out; a folder with no disc image in it gives back the folder's name, for a plain error.
    run(task): runs task(progress) with a progress screen (the copy takes a while)."""
    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    Docs = autoclass("android.provider.DocumentsContract")
    Document = autoclass("android.provider.DocumentsContract$Document")
    intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
    intent.putExtra(Intent.EXTRA_TITLE, title)
    data = _run_picker(intent)
    if data is None or data.getData() is None:
        return None
    tree = data.getData()
    children = Docs.buildChildDocumentsUriUsingTree(tree, Docs.getTreeDocumentId(tree))
    cursor = _activity().getContentResolver().query(
        children, [Document.COLUMN_DOCUMENT_ID, Document.COLUMN_DISPLAY_NAME, Document.COLUMN_SIZE],
        None, None, None)
    uris, sizes = {}, {}
    while cursor is not None and cursor.moveToNext():
        name = cursor.getString(1)
        uris[name] = Docs.buildDocumentUriUsingTree(tree, cursor.getString(0))
        sizes[name] = cursor.getLong(2)
    if cursor is not None:
        cursor.close()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    def read_text(name):
        return _copy(uris[name], folder / name).read_text(errors="replace")
    files = disc_files(list(uris), read_text)
    if not files:
        return folder / "no disc image in that folder.cue"  # the patcher says "Can't find ..."
    big = [(src, dst) for src, dst in files if src.lower().endswith((".bin", ".zip"))]

    def copy_all(progress):
        total, done = sum(sizes[src] for src, _ in big) or 1, 0
        for src, dst in big:
            _copy(uris[src], folder / dst, lambda n: progress(done + n, total))
            done += sizes[src]
        first = folder / files[0][1]
        return unzip_disc(first, folder) if first.suffix.lower() == ".zip" else first
    return (run or (lambda task: task(lambda done, total: None)))(copy_all)


def unzip_disc(zip_path, folder):
    """A .zip of a disc image: its .cue and .bin files, unpacked into folder (the .zip is then
    removed). Its .cue, or its .bin if it has no .cue."""
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        members = [m for m in z.namelist() if m.lower().endswith((".cue", ".bin"))]
        for m in members:
            with z.open(m) as src, open(folder / Path(m).name, "wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
    zip_path.unlink()
    names = [Path(m).name for m in members]
    cues = [n for n in names if n.lower().endswith(".cue")]
    return folder / (cues or names or [zip_path.name])[0]


def _read_chunk(stream, size=1 << 20):
    """Reads up to size bytes from a java.io.InputStream (pyjnius fills a Python bytearray)."""
    buf = bytearray(size)
    n = stream.read(buf, 0, size)
    if n is None or n <= 0:
        return b""
    return bytes(buf[:n])
