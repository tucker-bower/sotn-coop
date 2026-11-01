# android/recipes/android/src/android

Python-for-android's bridge to Android, of which we use only `activity`.

| File | What it does |
|---|---|
| `__init__.py` | Package entry: loads `_android`. |
| `_android.pyx` | Core Android services, in Cython. |
| `_android_billing.pyx` | **Vestigial.** Upstream copy; nothing in our app uses it: in-app billing. |
| `_android_billing_jni.c` | **Vestigial.** Upstream copy; nothing in our app uses it: in-app billing's JNI layer. |
| `_android_jni.c` | The JNI layer under `_android.pyx`. |
| `_android_sound.pyx` | **Vestigial.** Upstream copy; nothing in our app uses it: the sound API under `mixer.py`. |
| `_android_sound_jni.c` | **Vestigial.** Upstream copy; nothing in our app uses it: the sound API's JNI layer. |
| `_ctypes_library_finder.py` | Finds native libraries for the Python runtime's `ctypes`. |
| `activity.py` | Android activity callbacks; `launcher/platform_android.py` uses it for file pickers. |
| `billing.py` | **Vestigial.** Upstream copy; nothing in our app uses it: billing wrapper. |
| `broadcast.py` | **Vestigial.** Upstream copy; nothing in our app uses it: broadcast receivers. |
| `display_cutout.py` | **Vestigial.** Upstream copy; nothing in our app uses it: screen cutout sizes. |
| `loadingscreen.py` | **Vestigial.** Upstream copy; nothing in our app uses it: hides the loading screen. |
| `mixer.py` | **Vestigial.** Upstream copy; nothing in our app uses it: a pygame-style mixer. |
| `permissions.py` | **Vestigial.** Upstream copy; nothing in our app uses it: runtime permissions. |
| `runnable.py` | **Vestigial.** Upstream copy; nothing in our app uses it: runs Python on the UI thread. |
| `storage.py` | **Vestigial.** Upstream copy; nothing in our app uses it: storage paths. |
| `touch.py` | **Vestigial.** Upstream copy; nothing in our app uses it: touch interception. |
