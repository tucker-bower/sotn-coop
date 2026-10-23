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


def pick_files(title, folder, run=None):
    """The system's picker (ACTION_OPEN_DOCUMENT, several files): each chosen file is copied
    into folder, under its own name. [] if the player backs out. run(task): runs task(progress)
    with a progress screen (a disc image takes a while)."""
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
    chosen = []  # (uri, name, size)
    for uri in uris:
        name, size = "file", 0
        cursor = resolver.query(uri, None, None, None, None)
        if cursor is not None and cursor.moveToFirst():
            name = cursor.getString(cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)) or name
            size = cursor.getLong(cursor.getColumnIndex(OpenableColumns.SIZE))
            cursor.close()
        chosen.append((uri, Path(name).name, size))

    def copy_all(progress):
        total, done, out = sum(c[2] for c in chosen) or 1, 0, []
        for uri, name, size in chosen:
            out.append(_copy(uri, folder / name, lambda n: progress(done + n, total)))
            done += size
        return out
    return (run or (lambda task: task(lambda done, total: None)))(copy_all)


def disc_files(paths, read_text):
    """Which of a folder's files make the SOTN disc image, searching the folders inside it too
    (players put rips in a folder of their own, or unzip into one): a .cue and the files it
    names, next to it or else anywhere (a SOTN-named rip first, then the one nearest the top);
    else a lone .bin;
    else a .zip. paths: every file's path in the folder ("a/b/x.cue"); read_text(path): a .cue's
    text. [(path, name to save it as: the one the .cue uses, as Android's names are
    case-sensitive)], [] if there's nothing."""
    import patcher
    by_lower = {p.lower(): p for p in paths}
    by_name = {}  # a file's name, anywhere: a .cue and its .bin files that ended up in different folders
    for p in paths:
        by_name.setdefault(p.rsplit("/", 1)[-1].lower(), []).append(p)

    def find(here, f):
        f = f.replace("\\", "/")
        anywhere = by_name.get(f.rsplit("/", 1)[-1].lower(), [])
        return by_lower.get((here + f).lower()) or (anywhere[0] if len(anywhere) == 1 else None)

    def sotn_first(*names):  # SOTN's name in the path or the files it names, then nearest the top
        return (not any(k in " ".join(names).lower() for k in ("symphony", "sotn", "castlevania", "slus-00067", "slus_000.67")),
                names[0].count("/"), names[0])
    complete = []
    for cue in (p for p in paths if p.lower().endswith(".cue")):
        here = cue.rsplit("/", 1)[0] + "/" if "/" in cue else ""
        listed = patcher.cue_files(read_text(cue))
        found = [find(here, f) for f in listed]
        if listed and all(found):
            complete.append([(cue, cue.rsplit("/", 1)[-1])] + [(src, Path(f.replace("\\", "/")).name) for src, f in zip(found, listed)])
    if complete:
        return min(complete, key=lambda files: sotn_first(*(src for src, _ in files)))
    bins = [p for p in paths if p.lower().endswith(".bin") and not p.lower().endswith(("bios.bin", "scph1001.bin"))]
    if len(bins) == 1:
        return [(bins[0], bins[0].rsplit("/", 1)[-1])]
    zips = sorted((p for p in paths if p.lower().endswith(".zip")), key=sotn_first)
    return [(zips[0], zips[0].rsplit("/", 1)[-1])] if zips else []


NO_DISC = ("No Symphony of the Night disc image in that folder, or in the folders inside it.\n"
           "Pick the folder you copied your .cue and .bin files (or their .zip) into.")


def pick_disc(title, folder, run=None):
    """The system's folder picker (ACTION_OPEN_DOCUMENT_TREE): the disc image in the chosen
    folder, or in a folder inside it, is copied into folder (a .zip is unpacked). Its .cue (or
    .bin), or None if the player backed out; patcher.DiscError if there's no disc image there.
    run(task): runs task(progress) with a progress screen (the copy takes a while)."""
    import patcher
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
    resolver = _activity().getContentResolver()
    columns = [Document.COLUMN_DOCUMENT_ID, Document.COLUMN_DISPLAY_NAME, Document.COLUMN_SIZE,
               Document.COLUMN_MIME_TYPE]
    uris, sizes = {}, {}
    todo = [(Docs.getTreeDocumentId(tree), "")]
    while todo and len(uris) < 5000:  # breadth first, 4 folders deep at most
        doc, prefix = todo.pop(0)
        cursor = resolver.query(Docs.buildChildDocumentsUriUsingTree(tree, doc), columns, None, None, None)
        while cursor is not None and cursor.moveToNext():
            child, name = cursor.getString(0), prefix + cursor.getString(1)
            if cursor.getString(3) == Document.MIME_TYPE_DIR:
                if name.count("/") < 4:
                    todo.append((child, name + "/"))
            else:
                uris[name] = Docs.buildDocumentUriUsingTree(tree, child)
                sizes[name] = cursor.getLong(2)
        if cursor is not None:
            cursor.close()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    def read_text(path):
        return _copy(uris[path], folder / path.rsplit("/", 1)[-1]).read_text(errors="replace")
    files = disc_files(list(uris), read_text)
    if not files:
        raise patcher.DiscError(NO_DISC)
    big = [(src, dst) for src, dst in files if src.lower().endswith((".bin", ".zip"))]

    def copy_all(progress):
        total, done = sum(sizes[src] for src, _ in big) or 1, 0
        for src, dst in big:
            _copy(uris[src], folder / dst, lambda n: progress(done + n, total))
            done += sizes[src]
        first = folder / files[0][1]
        return unzip_disc(first, folder) if first.suffix.lower() == ".zip" else first
    return (run or (lambda task: task(lambda done, total: None)))(copy_all)


def pick_disc_files(title, folder, run=None):
    """The disc's files picked one by one (for files that aren't in a folder of their own, as in
    Download itself, which Android won't give an app): copied into folder, then as pick_disc."""
    import patcher
    got = pick_files(title, folder, run)
    if not got:
        return None
    files = disc_files([p.name for p in got], lambda name: (Path(folder) / name).read_text(errors="replace"))
    if not files:
        raise patcher.DiscError("Those files aren't a Symphony of the Night disc image.\n"
                                "Pick its .cue and .bin files together (press and hold to pick several), or its .zip.")
    first = Path(folder) / files[0][0]
    return unzip_disc(first, Path(folder)) if first.suffix.lower() == ".zip" else first


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
