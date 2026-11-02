# scripts

Setup, build, generator and release tools.

| File | What it does |
|---|---|
| `android_setup.sh` | Installs the Android toolchain. |
| `bootstrap.sh` | Sets up a dev machine. |
| `build_disc.sh` | Builds the co-op disc and enforces its layout rules. |
| `build_release.sh` | Builds the Windows installer. |
| `check_disc_layout.py` | Checks every retail file stays at its sector. |
| `check_dra_symbols.py` | Checks every DRA symbol stays at its retail address. |
| `doctor.py` | Checks this machine has everything needed. |
| `export_test_castles.py` | Exports the test castles the app ships. |
| `gen_flag_gated.py` | Generates `module/flag_gated.c` and `docs/flag-gated-entities.md`. |
| `gen_overlay_table.py` | Generates `module/overlay_table.c`. |
| `install_launcher.sh` | **Vestigial.** Installed developer presets on Windows; the real installer replaced it. |
| `make_debug_starts.py` | Makes the harness's debug, boss and scene starts. |
| `mingw-w64.cmake` | CMake toolchain for the Windows SwanStation build. |
| `rebuild_fixtures.sh` | Rebuilds the disc, Maria and every savestate after a module change. |
| `report_key.py` | Puts the key for F9's Send button in a build. |
| `redux_check.sh` | Runs the module check in PCSX-Redux. |
| `read_report.py` | **Manual.** Prints who was where in an unpacked F9 report, from its saved memory. |
| `release.py` | Builds both apps and a draft GitHub release. |
