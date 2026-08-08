from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class RunPaths:
    root: Path
    run_dir: Path

    @property
    def manuscript_dir(self) -> Path:
        return self.root / "NOTES"

    @property
    def manuscript_tex_path(self) -> Path:
        return self.manuscript_dir / "main.tex"

    @property
    def manuscript_pdf_path(self) -> Path:
        return self.manuscript_dir / "main.pdf"

    @property
    def manuscript_images_dir(self) -> Path:
        return self.manuscript_dir / "images"

    @property
    def corpus_fetch_path(self) -> Path:
        return self.run_dir / "corpus.csv"

    @property
    def corpus_clean_path(self) -> Path:
        return self.run_dir / "corpus_clean.csv"

    @property
    def corpus_clustered_path(self) -> Path:
        return self.run_dir / "corpus_clustered.csv"

    @property
    def screening_decisions_path(self) -> Path:
        return self.run_dir / "screening_decisions.csv"

    @property
    def corpus_paper_path(self) -> Path:
        return self.indicators_dir / "corpus_paper.csv"

    @property
    def screening_audit_path(self) -> Path:
        return self.indicators_dir / "screening_audit.json"

    @property
    def fetch_log_path(self) -> Path:
        return self.run_dir / "fetch_log.json"

    @property
    def embeddings_path(self) -> Path:
        return self.run_dir / "embeddings_bgem3.npy"

    @property
    def embedding_index_path(self) -> Path:
        return self.run_dir / "embeddings_bgem3_index.csv"

    @property
    def embedding_meta_path(self) -> Path:
        return self.run_dir / "embeddings_bgem3_meta.json"

    @property
    def indicators_dir(self) -> Path:
        return self.run_dir / "indicators"

    @property
    def fetch_raw_candidates_path(self) -> Path:
        return self.indicators_dir / "fetch_raw_candidates.csv"

    @property
    def global_embed_cache_dir(self) -> Path:
        return self.root / "embeddings_cache"

    @property
    def notes_dir(self) -> Path:
        return self.run_dir / "NOTES"

    @property
    def figures_dir(self) -> Path:
        return self.run_dir / "figures"

    @property
    def report_dark_path(self) -> Path:
        return self.notes_dir / "report.md"

    @property
    def report_light_path(self) -> Path:
        return self.notes_dir / "report_light.md"

    @property
    def report_pdf_path(self) -> Path:
        return self.notes_dir / "report.pdf"

    @property
    def report_light_pdf_path(self) -> Path:
        return self.notes_dir / "report_light.pdf"

    @property
    def report_text_path(self) -> Path:
        return self.notes_dir / "report_text.md"

    @property
    def report_summary_path(self) -> Path:
        return self.indicators_dir / "report_summary.json"

    @property
    def embedding_exclusions_path(self) -> Path:
        return self.indicators_dir / "embedding_exclusions.csv"


def build_run_paths(run_dir: str | Path | None = None) -> RunPaths:
    if run_dir is None:
        resolved = ROOT
    else:
        resolved = Path(run_dir)
        if not resolved.is_absolute():
            resolved = ROOT / resolved
    return RunPaths(root=ROOT, run_dir=resolved.resolve())


def ensure_run_dirs(paths: RunPaths) -> None:
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    paths.indicators_dir.mkdir(parents=True, exist_ok=True)
    paths.notes_dir.mkdir(parents=True, exist_ok=True)
    paths.figures_dir.mkdir(parents=True, exist_ok=True)