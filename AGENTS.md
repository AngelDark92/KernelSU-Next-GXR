# KernelSU-Next-GXR

Personal distribution of KernelSU-Next for the owner's Galaxy XR. The shipped bytes are
pinned; a release is only valid when `tools/verify_bundle.py` reproduces them.

- `module/kernelsu-gxr.ko` is written ONLY by `tools/patch_kernelsu_module.py` from
  `module/kernelsu-android12-5.10-upstream.ko`: the `__versions` section contents zeroed
  in place, and nothing else.
- The manager APK is the byte-identical upstream asset. The module binds to its signature;
  never rebuild, re-sign or rename it.
- Never claim a build, load, or device result that was not executed. Historical evidence
  lives in the gxr-kernel project: `builds/gxr-kernel/ksu-probe-20261009/RECEIPT.md` and
  `builds/gxr-kernel/ksu-release-20261009/`.
- Keep every sha256 in `tools/verify_bundle.py` in sync with the shipped bytes.
- Version truth is `VERSION`; `tools/release_policy.py` is its only writer and
  `tools/verify_release_version.py` checks pushed tags against it. Publish only through
  the `release.yml` gate (draft, upload, verify, then published).
