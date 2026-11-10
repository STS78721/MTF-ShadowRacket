# Contributing

## Where to start

- Issues labelled [good first issue](https://github.com/STS78721/MTF-ShadowRacket/issues?q=is%3Aopen+label%3A%22good+first+issue%22) need no code: testing on your GPU and reporting observations.
- Issues labelled [help wanted](https://github.com/STS78721/MTF-ShadowRacket/issues?q=is%3Aopen+label%3A%22help+wanted%22) each name the files to start from.
- Say in the issue that you are working on it, before you start, so two people do not do the same job.
- Questions go to [Discussions](https://github.com/STS78721/MTF-ShadowRacket/discussions).
- [docs/architecture.md](docs/architecture.md) explains how the pieces fit and [docs/bananza-shaders.md](docs/bananza-shaders.md) the shader work.

## The one hard rule

Nothing that came out of the game goes into the repository: no game files, keys, extracted data, recompiled C, compiled binaries, shaders, shader caches, fonts, audio or movies. Not in commits, not in issues, not in pull requests. Only information about the game goes in: addresses, hashes, patch code we wrote, shader and bind-state identifiers.

Two checks enforce this:

- CI runs `tools/check_content.py` on every push and pull request.
- The same check runs before each local commit once you enable the hook:

  ```sh
  git config core.hooksPath .githooks
  ```

A failing check is never bypassed with `--no-verify`. If it flags a file by mistake, change the check in a separate pull request and say why.

Links to game files, keys or firmware in issues or pull requests get the issue closed and the content removed.

## Code from other projects

MTF Recomp is GPL-3.0-or-later as a whole, so code under MIT, BSD, ISC, zlib, Apache-2.0 and GPL-3.0-compatible licences may be copied. Each copy keeps its original header and gets a row in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) with the upstream commit. Files that came from TotK Recomp keep their MIT terms.

## Reporting bugs

Use the issue tracker. Include the commit you built (`git rev-parse --short HEAD`), your GPU, driver and Windows version, the log (`logs/mtf.log` next to `mtf.exe`), and the steps to reproduce. Describe what you see instead of attaching copyrighted game assets.

## Pull requests

- One topic per pull request.
- Describe the problem, then what changed.
- Say how you tested it: which commit, which scene, how long, which GPU.
- A change to the lifter (`recomp/`) or the CPU headers passes the differential tests in [docs/building.md](docs/building.md).
- Commit messages are plain sentences, without `feat:` or other prefixes.
- AI-assisted code is welcome. You are responsible for having read and run it.

## Code and docs

- Code, comments, commit messages and documentation are in English.
- Generated code is never edited by hand: change the generator.
