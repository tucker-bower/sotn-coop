# android

The Android app: its entry point, build and device tools.

| File | What it does |
|---|---|
| `build.sh` | Stages the app and builds and signs the APK with python-for-android. |
| `device.py` | **Manual.** Installs the APK, copies the disc and switches signing keys on a USB device. |
| `main.py` | The app's entry point: sets up the device, then starts the launcher. |
| `recipes/` | Our python-for-android recipes. |
| `test_key_switch.py` | **Manual.** Checks a debug install's data survives the switch to the release key, on an emulator. |
| `test_pair.py` | **Manual.** Plays two Android emulators together; currently fails from the emulators' test setup. |
