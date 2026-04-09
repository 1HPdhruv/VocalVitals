import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"



def run_cmd(cmd: list[str], cwd: Path | None = None):
    print("[download] running:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def unzip_all(zip_path: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)


def download_kaggle_dataset(dataset: str, target_subdir: str):
    target_dir = DATA_DIR / target_subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    zip_name = dataset.split("/")[-1] + ".zip"
    zip_path = target_dir / zip_name

    kaggle_exe = Path(sys.executable).parent / "kaggle.exe"
    cmd = [
        str(kaggle_exe if kaggle_exe.exists() else "kaggle"),
        "datasets",
        "download",
        "-d",
        dataset,
        "-p",
        str(target_dir),
        "--force",
    ]
    run_cmd(cmd)

    if not zip_path.exists():
        zips = list(target_dir.glob("*.zip"))
        if not zips:
            raise FileNotFoundError(f"No zip downloaded for {dataset}")
        zip_path = zips[0]

    unzip_all(zip_path, target_dir)


def download_zenodo(target_subdir: str = "zenodo"):
    url = os.getenv("ZENODO_RESPIRATORY_URL", "")
    if not url:
        print("[download] Skipping Zenodo download: set ZENODO_RESPIRATORY_URL env var.")
        return

    target_dir = DATA_DIR / target_subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    archive_path = target_dir / "zenodo_dataset.zip"

    print("[download] downloading zenodo archive")
    urlretrieve(url, archive_path)
    unzip_all(archive_path, target_dir)


def ensure_dirs():
    for name in ["cough", "respiratory", "esc50", "speech", "zenodo"]:
        (DATA_DIR / name).mkdir(parents=True, exist_ok=True)


def main():
    ensure_dirs()

    # Kaggle datasets requested by user
    download_kaggle_dataset("andrewmvd/covid19-cough-audio-classification", "cough")
    download_kaggle_dataset("vbookshelf/respiratory-sound-database", "respiratory")

    # ESC-50 (optional, name can vary; override with env if needed)
    esc50_dataset = os.getenv("KAGGLE_ESC50_DATASET", "deepshah16/song-and-speech-separation")
    try:
        download_kaggle_dataset(esc50_dataset, "esc50")
    except Exception as exc:
        print(f"[download] ESC-50 download failed with dataset '{esc50_dataset}': {exc}")
        print("[download] Set KAGGLE_ESC50_DATASET to a valid Kaggle ESC-50 mirror and rerun.")

    download_zenodo("zenodo")
    print("[download] complete")


if __name__ == "__main__":
    main()
