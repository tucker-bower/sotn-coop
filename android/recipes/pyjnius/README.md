# android/recipes/pyjnius

Builds pyjnius without build isolation, so it finds python-for-android's Cython.

| File | What it does |
|---|---|
| `__init__.py` | The recipe: the stock one with build isolation off. |
| `genericndkbuild_jnienv_getter.patch` | **Vestigial.** Upstream patch for a bootstrap we don't build. |
| `sdl3_jnienv_getter.patch` | **Vestigial.** Upstream patch for a bootstrap we don't build. |
| `use_cython.patch` | Upstream patch, applied on every build: makes pyjnius build with Cython. |
