"""命令行首次真实调用。失败不会自动重试，以免重复扣费。"""
import argparse
from pathlib import Path
from dotenv import load_dotenv
from pydantic import ValidationError
from generator import GenerationService, GenerationProblem
from schemas import GenerateRequest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt", help="需要生成的场景")
    group.add_argument("--prompt-file", type=Path, help="UTF-8 文本提示词文件")
    parser.add_argument("--experiment", default="v1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--minimal", action="store_true", help="只提交 model 和 prompt，用于参数兼容性排查")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent / ".env")
    try:
        prompt = args.prompt_file.read_text(encoding="utf-8-sig") if args.prompt_file else args.prompt
        if prompt.startswith("请把本文件内容替换"):
            print("my_prompt.txt 还是占位内容，请先填写自己的场景；尚未发起推理。")
            return 1
        item = GenerateRequest(prompt=prompt, seed=args.seed, experiment=args.experiment,
                               parameter_mode="minimal" if args.minimal else "explicit")
        result = GenerationService().generate(item)
    except (ValidationError, OSError):
        print("输入无效或提示词文件不可读；检查参数、文件路径和编码。")
        return 1
    except GenerationProblem as exc:
        print(exc.detail["message"])
        return 1
    print(f"真实调用流程完成；图像与记录保存在 outputs/{result['local_request_id']}.*")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
