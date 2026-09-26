# Camera-ready manuscript

`main.pdf` is the final seven-page paper. `main.tex`, the generated validation
inputs, IEEEtran files, page artwork, and vector figures build that PDF.

To rebuild, run pdfLaTeX twice from this directory:

```text
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

The individually browsable analysis data, protocols, and reproduction scripts
are in [`../supplement/`](../supplement/README.md). The source and PDF are also
listed on the [publication landing page](../README.md).
