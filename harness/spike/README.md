# M0 harness spike (throwaway)

These are proof-of-concept scripts from the M0 design spike. They'll be replaced by the real harness in M0.

- `smoke.py`: boots a disc headless in the SwanStation libretro core and saves a frame.
- `probe.py`: prints game globals (`g_GameState`, `g_Timer`, …) from RAM every 300 frames.
- `shots.py`: captures frames at chosen frame numbers.
- `determ.py`: runs the same boot twice and compares RAM hashes.

Requirements: `libretro.py` (pip), a SwanStation libretro core build, and OpenBIOS built with `FASTBOOT=1` placed as `sys/scph5501.bin`. Paths are hardcoded to the agent workspace.
