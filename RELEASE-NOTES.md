KernelSU-Next v3.4.0 module for Galaxy XR (SM-I610, `I610UEU2AZF3`, kernel 5.10.240).

Derived from `sarabpal-dev/KernelSU-Next` v3.4.0 (GPL-3.0). The only change to the module:
the contents of the ELF section `__versions` are zeroed in place (offset 157008, size
8512, 8,472 bytes cleared) — that is what makes this kernel's `check_version()` warn
instead of reject, and the image load with a plain `insmod`. Verified live 2026-10-09:
KernelSU registers and `su -c id` returns uid=0.

Assets:

- `kernelsu-gxr.ko` — the patched module, sha256 `f528ef24fca78fe429df7e7290058febf884e97dc533497549c345c5e8d3e2d6`
- `KernelSU_Next_v3.4.0-android12-5.10_33303-release.apk` — the matching manager,
  byte-identical to the upstream v3.4.0 asset, sha256 `94eb18574318c00c67a8903abf07ccb5cbfedf13701fbbbf8fa26850f91fddf7`
- `patch_kernelsu_module.py` and `SHA256SUMS` — the patcher and all checksums

Reproduce the module from the upstream copy (also in this repository,
`module/kernelsu-android12-5.10-upstream.ko`):

    python3 patch_kernelsu_module.py --upstream kernelsu-android12-5.10-upstream.ko --out kernelsu-gxr.ko

The result must hash to `f528ef24fca78fe429df7e7290058febf884e97dc533497549c345c5e8d3e2d6`.
