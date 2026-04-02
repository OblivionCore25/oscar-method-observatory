import json
from pathlib import Path
from ..models.analysis_result import AnalysisResult


class JsonStorage:
    """
    Flat-file JSON storage for analysis results.
    Mirrors OSCAR's existing data/ directory structure pattern.

    Layout:
        data/method_observatory/{project_slug}/
            analysis_meta.json
            methods.json
            classes.json
            modules.json
            calls.json
            imports.json
            inheritance.json
            metrics.json
    """

    def __init__(self, data_directory: Path):
        self.root = data_directory / "method_observatory"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, project_slug: str, result: AnalysisResult) -> None:
        project_dir = self.root / project_slug
        project_dir.mkdir(parents=True, exist_ok=True)

        self._write(project_dir / "analysis_meta.json", result.meta.model_dump(mode="json"))
        self._write(project_dir / "methods.json", [m.model_dump(mode="json") for m in result.methods])
        self._write(project_dir / "classes.json", [c.model_dump(mode="json") for c in result.classes])
        self._write(project_dir / "modules.json", [m.model_dump(mode="json") for m in result.modules])
        self._write(project_dir / "calls.json", [c.model_dump(mode="json") for c in result.calls])
        self._write(project_dir / "imports.json", [i.model_dump(mode="json") for i in result.imports])
        self._write(project_dir / "inheritance.json", [i.model_dump(mode="json") for i in result.inheritance])
        self._write(project_dir / "metrics.json", [m.model_dump(mode="json") for m in result.metrics])

    def load(self, project_slug: str) -> AnalysisResult | None:
        project_dir = self.root / project_slug
        if not project_dir.exists():
            return None
        return AnalysisResult(
            meta=self._read_model(project_dir / "analysis_meta.json", "meta"),
            methods=self._read_list(project_dir / "methods.json"),
            classes=self._read_list(project_dir / "classes.json"),
            modules=self._read_list(project_dir / "modules.json"),
            calls=self._read_list(project_dir / "calls.json"),
            imports=self._read_list(project_dir / "imports.json"),
            inheritance=self._read_list(project_dir / "inheritance.json"),
            metrics=self._read_list(project_dir / "metrics.json"),
        )

    def list_projects(self) -> list[str]:
        return [d.name for d in self.root.iterdir() if d.is_dir()]

    def _write(self, path: Path, data) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _read_list(self, path: Path) -> list:
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _read_model(self, path: Path, key: str):
        # The key parameter is not used in the original document plan either,
        # but the JSON loads the whole dict.
        with open(path, encoding="utf-8") as f:
            return json.load(f)
