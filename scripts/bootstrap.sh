#!/usr/bin/env bash
# Sets up a dev/agent machine for SOTN Co-op (Ubuntu or WSL2). Idempotent: re-run any time.
# Usage: scripts/bootstrap.sh [step...]   (default: all steps)
# Steps: apt python swanstation openbios decomp, and for releases: swanstation_win swanstation_android
# Afterwards run: scripts/doctor.py
set -euo pipefail

COOP="$(cd "$(dirname "$0")/.." && pwd)"
ENV_DIR="$COOP/.env"          # git-ignored: everything built or downloaded lives here
mkdir -p "$ENV_DIR/src" "$ENV_DIR/bin" "$ENV_DIR/sys"

if [ -f "$COOP/../../sotn.sh" ] && [ ! -f "$ENV_DIR/src/sotn-decomp/sotn.sh" ]; then
    ROOT="$(cd "$COOP/../.." && pwd)"
else
    ROOT="$ENV_DIR/src/sotn-decomp"
fi

# Pinned so builds and harness results are reproducible. Bump deliberately, then re-run lockstep.
SOTN_DECOMP_REPO=https://github.com/Xeeynamo/sotn-decomp
SOTN_DECOMP_REV=d12b397f3611e71906187214d499c005de951290
SWANSTATION_REPO=https://github.com/libretro/swanstation
SWANSTATION_REV=e436e9b85374def58d211df7f78880f0f4a917b4
PCSXREDUX_REPO=https://github.com/grumpycoders/pcsx-redux
PCSXREDUX_REV=e58d0892c8e824bd7d5da847290f6811331215e5

log() { printf '\n== %s\n' "$*"; }

checkout() { # checkout <repo> <rev> <dir>
    local repo=$1 rev=$2 dir=$3
    if [ ! -d "$dir/.git" ]; then
        git init -q "$dir"
        git -C "$dir" remote add origin "$repo"
    fi
    if [ "$(git -C "$dir" rev-parse HEAD 2>/dev/null)" != "$rev" ]; then
        git -C "$dir" fetch -q --depth 1 origin "$rev"
        git -C "$dir" checkout -q FETCH_HEAD
        git -C "$dir" submodule update -q --init --recursive --depth 1
    fi
}

ensure_decomp_src() {
    if [ "$ROOT" = "$ENV_DIR/src/sotn-decomp" ]; then
        log "sotn-decomp @ ${SOTN_DECOMP_REV:0:10} (+ patches/sotn-decomp.patch)"
        checkout "$SOTN_DECOMP_REPO" "$SOTN_DECOMP_REV" "$ROOT"
        if git -C "$ROOT" apply --check "$COOP/patches/sotn-decomp.patch" 2>/dev/null; then
            git -C "$ROOT" apply "$COOP/patches/sotn-decomp.patch"
        fi
        mkdir -p "$ROOT/mods"
        ln -sfn "$COOP" "$ROOT/mods/co-op"
        if [ -d "$COOP/disks" ] && [ ! -e "$ROOT/disks" ]; then
            ln -sfn "$COOP/disks" "$ROOT/disks"
        fi
    fi
}

step_apt() {
    ensure_decomp_src
    log "apt packages (upstream list + co-op extras)"
    # Ubuntu 26.04 dropped gcc-mipsel-linux-gnu. Take only that from 24.04 (what upstream's Docker
    # image uses), via a low-priority pin so nothing else is ever pulled from noble.
    if ! apt-cache show gcc-mipsel-linux-gnu 2>/dev/null | grep -q '^Version'; then
        sudo tee /etc/apt/sources.list.d/noble-cross.sources >/dev/null <<'EOF'
# co-op: MIPS cross toolchain only (see scripts/bootstrap.sh)
Types: deb
URIs: http://archive.ubuntu.com/ubuntu
Suites: noble noble-updates
Components: main universe
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
        printf 'Package: *\nPin: release n=noble\nPin-Priority: 50\n\nPackage: *\nPin: release n=noble-updates\nPin-Priority: 50\n' |
            sudo tee /etc/apt/preferences.d/noble-cross >/dev/null
    fi
    sudo apt-get update -q
    command -v mipsel-linux-gnu-gcc >/dev/null || sudo apt-get install -y -q -t noble-updates gcc-mipsel-linux-gnu
    # shellcheck disable=SC2046
    sudo apt-get install -y -q $(grep -v '^gcc-mipsel-linux-gnu$' "$ROOT/tools/requirements-debian.txt") \
        golang-go build-essential cmake pkg-config gh python3-dev
    rustup toolchain list | grep -q "^stable" || rustup default stable
}

step_python() {
    ensure_decomp_src
    log "python venv (decomp tools + harness)"
    # The decomp's Makefile expects .venv at the decomp root.
    [ -d "$ROOT/.venv" ] || python3 -m venv "$ROOT/.venv"
    "$ROOT/.venv/bin/pip" install -q -r "$ROOT/tools/requirements-python.txt" -r "$COOP/harness/requirements.txt"
}

step_swanstation() {
    log "SwanStation libretro core @ ${SWANSTATION_REV:0:10} (+ patches/swanstation.patch: VRAM's second bank)"
    local src="$ENV_DIR/src/swanstation"
    checkout "$SWANSTATION_REPO" "$SWANSTATION_REV" "$src"
    if git -C "$src" apply --check "$COOP/patches/swanstation.patch" 2>/dev/null; then
        git -C "$src" apply "$COOP/patches/swanstation.patch"
    fi
    cmake -S "$src" -B "$src/build" -G Ninja -DCMAKE_BUILD_TYPE=Release >/dev/null
    cmake --build "$src/build"
    cp "$(find "$src/build" -name swanstation_libretro.so | head -1)" "$ENV_DIR/bin/"
}

# The release cores, from the same patched source (M13: the PC and Android must run our VRAM
# bank, and the same core everywhere keeps savestates and the harness alike): the Windows DLL
# (MinGW, no runtime DLLs needed) and the Android .so for each arch.
step_swanstation_win() {
    log "SwanStation for Windows (MinGW)"
    local src="$ENV_DIR/src/swanstation"
    command -v x86_64-w64-mingw32-g++-posix >/dev/null || sudo apt-get install -y -q g++-mingw-w64-x86-64-posix
    cmake -S "$src" -B "$src/build-win" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_TOOLCHAIN_FILE="$COOP/scripts/mingw-w64.cmake" \
        -DCMAKE_SHARED_LINKER_FLAGS="-static-libgcc -static-libstdc++ -static -s" >/dev/null
    cmake --build "$src/build-win"
    cp "$src/build-win/swanstation_libretro.dll" "$ENV_DIR/bin/"
}

step_swanstation_android() {
    local A="${ANDROID_HOME:-$HOME/android}" src="$ENV_DIR/src/swanstation" ndk abi
    ndk="$(ls -d "$A"/ndk/* | sort -V | tail -1)"
    for abi in arm64-v8a x86_64; do
        log "SwanStation for Android ($abi, NDK $(basename "$ndk"))"
        cmake -S "$src" -B "$src/build-android-$abi" -G Ninja -DCMAKE_BUILD_TYPE=Release \
            -DCMAKE_TOOLCHAIN_FILE="$ndk/build/cmake/android.toolchain.cmake" \
            -DANDROID_ABI=$abi -DANDROID_PLATFORM=android-24 >/dev/null
        cmake --build "$src/build-android-$abi"
        mkdir -p "$A/cores/$abi"
        "$ndk"/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip -o "$A/cores/$abi/swanstation_libretro_android.so" \
            "$src/build-android-$abi/swanstation_libretro_android.so"
    done
}

step_openbios() {
    log "OpenBIOS (PCSX-Redux) @ ${PCSXREDUX_REV:0:10}, fast-boot"
    local src="$ENV_DIR/src/pcsx-redux"
    checkout "$PCSXREDUX_REPO" "$PCSXREDUX_REV" "$src"
    # The Linux-target binutils name the ELF format "tradlittlemips", not bare-metal "littlemips".
    make -C "$src/src/mips/openbios" -j"$(nproc)" PREFIX=mipsel-linux-gnu FORMAT=elf32-tradlittlemips FASTBOOT=true
    # SwanStation looks the BIOS up by file name; OpenBIOS stands in for the NTSC-U image.
    cp "$src/src/mips/openbios/openbios.bin" "$ENV_DIR/sys/scph5501.bin"
}

step_decomp() {
    ensure_decomp_src
    log "decomp tools + matching US build (needs disks/sotn.us.cue)"
    # sotn_str is otherwise only built by `make update-dependencies`, which also git-cleans bin/.
    cargo build -q --release --manifest-path "$ROOT/tools/sotn_str/Cargo.toml"
    # shellcheck disable=SC1091
    (cd "$ROOT" && . .venv/bin/activate && export VERSION=us &&
        { [ -d disks/us ] || make extract_disk; } && make -j"$(nproc)" build)
}

steps=("$@")
[ ${#steps[@]} -gt 0 ] || steps=(apt python swanstation openbios decomp)
for s in "${steps[@]}"; do "step_$s"; done
log "done. Next: $COOP/scripts/doctor.py"
