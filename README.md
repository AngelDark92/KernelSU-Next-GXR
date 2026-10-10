# KernelSU-Next-GXR

KernelSU-Next for the Galaxy XR (SM-I610, `I610UEU2AZF3`, kernel 5.10.240). The upstream
v3.4.0 module with the `__versions` section contents zeroed in place, the matching manager
APK, the patcher, and every hash pinned. Verified live 2026-10-09: `kernelsu` registers
and `su -c id` returns uid=0.

## Contents

| File | sha256 |
|---|---|
| `module/kernelsu-gxr.ko` (468,768 B) | `f528ef24fca78fe429df7e7290058febf884e97dc533497549c345c5e8d3e2d6` |
| `module/kernelsu-android12-5.10-upstream.ko` (468,768 B) | `b6075e6ebff6d1b76b64b322086162f58787d747614edc1a04e92db7c4ae8e21` |
| `manager/KernelSU_Next_v3.4.0-android12-5.10_33303-release.apk` (6,788,732 B) | `94eb18574318c00c67a8903abf07ccb5cbfedf13701fbbbf8fa26850f91fddf7` |
| `tools/patch_kernelsu_module.py` | `a9ba7e11d370423b6972bc573320fc7ad5852a4c3239ea210119637dd138bbe7` |

Derived from `sarabpal-dev/KernelSU-Next` v3.4.0 (GPL-3.0). The patched module differs
from upstream only inside `__versions`; the manager APK is byte-identical to the upstream
release asset.

## Verify

```
python3 tools/verify_bundle.py --reproduce
```

Checks every pin and rebuilds `kernelsu-gxr.ko` from the included upstream copy, byte for
byte. Release text and the full change list: `RELEASE-NOTES.md`.

## Use on the device

The root manager app ships the module as `assets/payload/kernelsu-gxr.ko` and loads it as
the last step of a successful run (`insmod … allow_shell=1`). The app's
`RootEngine.KSU_MODULE_URL` points at this repository's newest release.

## CI

Ported from the GalaxyXR-Driver design (notes: `docs/GitHub-CI-Notes-2026-10-10.md` in the
gxr-kernel project). `ci.yml` verifies every push; `release.yml` runs the same checks and
publishes on a `v*` tag, on `main` when the version moved, or on a dispatch that asked to
publish — everything else is a verify-only dry run. Releases stay drafts until the assets
verify, then flip to published.

## License

GPL-3.0. The module and manager derive from KernelSU-Next; see `LICENSE`.
