"""统计指定目录的源码物理行/非空行（含注释），按完整文件内容去重；不判定作者。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

EXTENSIONS = {".py", ".c", ".h", ".cpp", ".hpp", ".java", ".js", ".jsx", ".ts", ".tsx", ".vue", ".html", ".css", ".scss", ".sql", ".go", ".rs", ".kt", ".sh", ".ps1"}
SKIP = {".git", ".venv", "venv", "node_modules", "vendor", "dist", "build", "__pycache__", ".pytest_cache", "outputs", "logs"}


def count_sources(roots: list[Path], extra_exclusions: set[str]) -> dict:
    seen: dict[str, str] = {}
    files, duplicates, unreadable = [], [], []
    for root in roots:
        if not root.is_dir():
            raise ValueError(f"目录不存在：{root}")
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink() or path.suffix.lower() not in EXTENSIONS:
                continue
            if any(part in SKIP | extra_exclusions for part in path.relative_to(root).parts):
                continue
            if path.name.endswith((".min.js", ".min.css")):
                continue
            try:
                content = path.read_bytes()
                # 不以 errors=ignore 吞掉不可识别内容；报告无法解码的文件。
                try:
                    text = content.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = content.decode("gb18030")
            except (OSError, UnicodeDecodeError):
                unreadable.append(str(path))
                continue
            digest = hashlib.sha256(content).hexdigest()
            if digest in seen:
                duplicates.append({"path": str(path), "same_as": seen[digest]})
                continue
            seen[digest] = str(path)
            lines = text.splitlines()
            files.append({"path": str(path), "physical_lines": len(lines),
                          "nonblank_lines_including_comments": sum(bool(line.strip()) for line in lines)})
    return {"metric": "源码物理行与非空行；均含注释；不区分本人、他人或AI编写，须人工确认范围",
            "physical_lines": sum(f["physical_lines"] for f in files),
            "nonblank_lines_including_comments": sum(f["nonblank_lines_including_comments"] for f in files),
            "file_count": len(files), "files": files, "duplicates_excluded": duplicates,
            "unreadable_files": unreadable, "excluded_directory_names": sorted(SKIP | extra_exclusions)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", type=Path, nargs="+")
    parser.add_argument("--exclude", action="append", default=[], help="附加排除的目录名，可重复")
    parser.add_argument("--output", type=Path, help="可选 JSON 文件路径")
    args = parser.parse_args()
    try:
        result = count_sources(args.roots, set(args.exclude))
    except ValueError as exc:
        parser.error(str(exc))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in {"files", "duplicates_excluded"}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
