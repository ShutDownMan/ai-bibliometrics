"""Pipeline stage: sync manuscript figures and compile NOTES/main.tex to PDF."""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
from pathlib import Path

from .paths import RunPaths, ensure_run_dirs


_LATEX_ENGINES = ["xelatex", "lualatex", "pdflatex"]
_IMG_RE = re.compile(
    r'<img\s+src="data:image/png;base64,([^"]+)"(?:[^>]*alt="([^"]*)")?',
    re.IGNORECASE | re.DOTALL,
)


def _slugify(text: str, maxlen: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:maxlen] or "figure"


def _find_windows_miktex_executable(name: str) -> str | None:
    search_roots: list[Path] = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_name)
        if base:
            search_roots.append(Path(base) / "MiKTeX")

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        search_roots.append(Path(local_appdata) / "Programs" / "MiKTeX")

    explicit_candidates: list[Path] = []
    for root in search_roots:
        explicit_candidates.extend(
            [
                root / "miktex" / "bin" / "x64" / f"{name}.exe",
                root / "miktex" / "bin" / f"{name}.exe",
                root / "executables" / "windows-x64" / name / f"{name}.exe",
            ]
        )

    for candidate in explicit_candidates:
        if candidate.exists():
            return str(candidate)

    for root in search_roots:
        if not root.exists():
            continue
        matches = sorted(root.rglob(f"{name}.exe"))
        if matches:
            return str(matches[0])

    return None


def _find_executable(names: list[str], *, label: str, install_hint: str) -> str:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
        if os.name == "nt":
            resolved = _find_windows_miktex_executable(name)
            if resolved:
                return resolved
    raise RuntimeError(
        f"Nenhum executável compatível foi encontrado para {label}. {install_hint}"
    )


def _sync_report_figures(report_path: Path, images_dir: Path) -> None:
    if not report_path.exists():
        print(
            f"[tex-pdf] Aviso: {report_path.name} não encontrado em {report_path.parent}; "
            "mantendo as figuras já existentes em NOTES/images."
        )
        return

    content = report_path.read_text(encoding="utf-8")
    matches = list(_IMG_RE.finditer(content))
    if not matches:
        print(
            f"[tex-pdf] Aviso: nenhuma figura embutida encontrada em {report_path.name}; "
            "mantendo as figuras já existentes em NOTES/images."
        )
        return

    images_dir.mkdir(parents=True, exist_ok=True)
    for path in images_dir.glob("fig*.png"):
        path.unlink(missing_ok=True)

    for idx, match in enumerate(matches, 1):
        b64_data = match.group(1).strip()
        alt = match.group(2) or ""
        name = f"fig{idx:02d}_{_slugify(alt)}.png" if alt else f"fig{idx:02d}.png"
        out_path = images_dir / name
        out_path.write_bytes(base64.b64decode(b64_data))

    print(f"[tex-pdf] Figuras sincronizadas: {len(matches)} -> {images_dir}")


def _run_command(cmd: list[str], *, cwd: Path, label: str) -> None:
    try:
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "") + "\n" + (exc.stderr or "")
        detail_lines = [line for line in output.splitlines() if line.strip()]
        detail = "\n".join(detail_lines[-25:]) if detail_lines else str(exc)
        raise RuntimeError(
            f"Falha ao executar {label}.\n"
            f"Comando: {' '.join(cmd)}\n"
            f"Diretório: {cwd}\n"
            f"Detalhe:\n{detail}"
        ) from exc


def _compile_manuscript(tex_path: Path) -> Path:
    engine = _find_executable(
        _LATEX_ENGINES,
        label="o motor LaTeX",
        install_hint=(
            "Instale uma distribuição TeX com xelatex, lualatex ou pdflatex no PATH "
            "(por exemplo, MiKTeX ou TeX Live)."
        ),
    )
    biber = _find_executable(
        ["biber"],
        label="o backend bibliográfico",
        install_hint="Instale o Biber e garanta que ele esteja disponível no PATH.",
    )

    pdf_path = tex_path.with_suffix(".pdf")
    pdf_path.unlink(missing_ok=True)

    engine_cmd = [
        engine,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        tex_path.name,
    ]
    cwd = tex_path.parent
    jobname = tex_path.stem

    print(f"[tex-pdf] Motor LaTeX: {engine}")
    print(f"[tex-pdf] Biber: {biber}")

    _run_command(engine_cmd, cwd=cwd, label="1ª passada LaTeX")
    _run_command([biber, jobname], cwd=cwd, label="Biber")
    _run_command(engine_cmd, cwd=cwd, label="2ª passada LaTeX")
    _run_command(engine_cmd, cwd=cwd, label="3ª passada LaTeX")

    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError(
            f"Falha ao gerar {pdf_path.name}: o PDF final não foi criado corretamente."
        )

    return pdf_path


def run(paths: RunPaths) -> None:
    ensure_run_dirs(paths)

    tex_path = paths.manuscript_tex_path
    if not tex_path.exists():
        raise FileNotFoundError(
            f"Manuscrito não encontrado: {tex_path}. "
            "Crie NOTES/main.tex antes de executar o estágio tex-pdf."
        )

    _sync_report_figures(paths.report_light_path, paths.manuscript_images_dir)
    pdf_path = _compile_manuscript(tex_path)
    size_kb = pdf_path.stat().st_size // 1024
    print(f"[tex-pdf] Salvo: {pdf_path} ({size_kb} KB)")