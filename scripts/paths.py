from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = PROJECT_ROOT / "build"
LIMITS_FILE = PROJECT_ROOT / "data" / "limits.json"
PREVIEWS_DIR = BUILD_DIR / "previews"
TYPST_WORKSPACE = BUILD_DIR / "typst-ygo"
TYPST_YGO_SOURCE = PROJECT_ROOT / "vendor" / "typst-ygo"
YGO_ASSETS_SOURCE = PROJECT_ROOT / "vendor" / "ygo-assets" / "assets"
