#!/usr/bin/env bash
# M9: the Android toolchain on the dev machine (WSL2 Ubuntu), all under ~/android (design/M9-android.md).
# Safe to re-run. Installs: a JDK, the Android SDK (platform tools, emulator, an x86_64 system image
# for the test emulators), the NDK python-for-android needs, and python-for-android in a venv.
set -euo pipefail
A="${ANDROID_HOME:-$HOME/android}"
mkdir -p "$A"
sudo apt-get install -y -qq openjdk-17-jdk-headless unzip autoconf automake libtool pkg-config zlib1g-dev \
    libncurses-dev cmake libffi-dev libssl-dev lld patch ccache >/dev/null
if [ ! -x "$A/cmdline-tools/latest/bin/sdkmanager" ]; then
    curl -sSLo /tmp/cmdtools.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
    rm -rf "$A/cmdline-tools" && mkdir -p "$A/cmdline-tools"
    unzip -q /tmp/cmdtools.zip -d "$A/cmdline-tools" && mv "$A/cmdline-tools/cmdline-tools" "$A/cmdline-tools/latest"
fi
SDKM="$A/cmdline-tools/latest/bin/sdkmanager --sdk_root=$A"
yes | $SDKM --licenses >/dev/null || true
$SDKM "platform-tools" "emulator" "platforms;android-34" "build-tools;34.0.0" \
      "system-images;android-34;default;x86_64" "ndk;25.2.9519653" >/dev/null
python3 -m venv "$A/p4a-venv"
"$A/p4a-venv/bin/pip" install -q --upgrade pip
"$A/p4a-venv/bin/pip" install -q "python-for-android" cython==0.29.36 setuptools wheel
echo "android toolchain ready in $A"
