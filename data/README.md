# Synapse — data

**Nothing in this directory is committed except configs and this file.**

Raw sensor captures, curated test sets and trained weights live outside git.
`.gitignore` blocks `*.pt`, `*.onnx`, `*.tflite`, `*.csv`, `*.parquet`,
`checkpoints/`, `runs/`, `wandb/` and friends.

## Where the data actually lives

<!-- TODO: fill in once storage is chosen -->
| Artefact | Location | Owner |
|---|---|---|
| Defence payload capture set | _TBD_ | |
| Agriculture payload capture set | _TBD_ | |
| Trained baseline weights | _TBD_ | |

## Options

- **Git LFS** — simplest if total volume stays modest. Note LFS still rewrites large files in the working tree on checkout.
- **External object storage** (S3 / Drive / institute NAS) with a fetch script and a checksum manifest committed here.
- **DVC** — versions data by hash, stores blobs externally. Worth it once the dataset has real iterations.

Whichever is chosen: commit the **manifest and checksums**, never the blobs.
