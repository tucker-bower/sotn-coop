# installer

The Windows installer's definition.

| File | What it does |
|---|---|
| `sotn-coop.iss` | Inno Setup script, run by `scripts/build_release.sh`: asks where, keeps the player's `data\` on update and (unless they say) on uninstall. |
