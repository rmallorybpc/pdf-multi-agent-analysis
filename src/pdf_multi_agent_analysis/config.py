from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for end-to-end PDF analysis runs."""

    chunk_size_chars: int = 1800
    overlap_chars: int = 200
    output_dir: Path = Path("output")
    max_asset_chars_per_file: int = 4000
    asset_pdf_ocr_fallback: bool = True
    asset_pdf_ocr_max_pages: int = 6
