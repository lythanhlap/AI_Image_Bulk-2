import argparse
import base64
import copy
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI


BASE_URL = "https://openrouter.ai/api/v1"
IMAGE_API_URL = f"{BASE_URL}/images"
ENV_FILE = Path(".env")

REFERER = "https://localhost:3000"
APP_TITLE = "Bulk Image Generator"

DEFAULT_BACKEND = "local_webui"
DEFAULT_OPENROUTER_MODEL = "black-forest-labs/flux.2-klein-4b"


@dataclass
class Config:
    backend: str
    prompts_file: Path
    output_dir: Path
    width: int
    height: int
    output_format: str
    skip_existing: bool
    retries: int
    retry_delay: float
    limit: int | None
    start_index: int
    dry_run: bool

    webui_url: str
    webui_steps: int
    webui_cfg_scale: float
    webui_sampler_name: str
    webui_negative_prompt: str
    webui_seed: int
    webui_model_checkpoint: str
    webui_timeout: int

    comfyui_url: str
    comfyui_workflow: Path
    comfyui_prompt_node_id: str
    comfyui_prompt_field: str
    comfyui_negative_node_id: str
    comfyui_negative_field: str
    comfyui_width_node_id: str
    comfyui_width_field: str
    comfyui_height_node_id: str
    comfyui_height_field: str
    comfyui_seed_node_id: str
    comfyui_seed_field: str
    comfyui_timeout: int

    openrouter_api_key: str
    openrouter_model: str
    openrouter_timeout: int


def configure_console_encoding() -> None:
    """Bật UTF-8 để PowerShell in tiếng Việt ổn định."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def load_env_file(path: Path) -> None:
    """Nạp biến môi trường đơn giản từ file .env."""
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key.startswith("export "):
                key = key.removeprefix("export ").strip()

            os.environ.setdefault(key, value)


def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_int(name: str, default: int) -> int:
    value = env_str(name)
    return int(value) if value else default


def env_float(name: str, default: float) -> float:
    value = env_str(name)
    return float(value) if value else default


def env_bool(name: str, default: bool) -> bool:
    value = env_str(name).lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "y", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tạo ảnh hàng loạt từ prompts.json bằng WebUI, ComfyUI hoặc OpenRouter."
    )
    parser.add_argument(
        "--backend",
        choices=["local_webui", "comfyui", "openrouter"],
        help="Backend tạo ảnh. Mặc định lấy từ GEN_BACKEND trong .env.",
    )
    parser.add_argument("--prompts-file", help="Đường dẫn file prompts JSON.")
    parser.add_argument("--output-dir", help="Thư mục lưu ảnh.")
    parser.add_argument("--limit", type=int, help="Chỉ chạy tối đa N prompt.")
    parser.add_argument(
        "--start-index",
        type=int,
        default=None,
        help="Bắt đầu từ prompt thứ N, tính từ 1.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Tạo lại ảnh dù file đầu ra đã tồn tại.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ kiểm tra danh sách prompt, không gọi API tạo ảnh.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Kiểm tra kết nối backend rồi thoát.",
    )
    parser.add_argument(
        "--list-webui-models",
        action="store_true",
        help="Liệt kê checkpoint từ local WebUI rồi thoát.",
    )
    return parser.parse_args()


def load_config(args: argparse.Namespace) -> Config:
    load_env_file(ENV_FILE)

    backend = args.backend or env_str("GEN_BACKEND", DEFAULT_BACKEND)
    output_format = env_str("OUTPUT_FORMAT", "png").lower()

    return Config(
        backend=backend,
        prompts_file=Path(args.prompts_file or env_str("PROMPTS_FILE", "prompts.json")),
        output_dir=Path(args.output_dir or env_str("OUTPUT_DIR", "video_assets")),
        width=env_int("IMAGE_WIDTH", 1024),
        height=env_int("IMAGE_HEIGHT", 576),
        output_format=output_format,
        skip_existing=not args.force and env_bool("SKIP_EXISTING", True),
        retries=env_int("RETRIES", 2),
        retry_delay=env_float("RETRY_DELAY", 3.0),
        limit=args.limit if args.limit is not None else None,
        start_index=args.start_index or env_int("START_INDEX", 1),
        dry_run=args.dry_run,
        webui_url=env_str("WEBUI_URL", "http://127.0.0.1:7860").rstrip("/"),
        webui_steps=env_int("WEBUI_STEPS", 25),
        webui_cfg_scale=env_float("WEBUI_CFG_SCALE", 6.0),
        webui_sampler_name=env_str("WEBUI_SAMPLER", "DPM++ 2M Karras"),
        webui_negative_prompt=env_str(
            "WEBUI_NEGATIVE_PROMPT",
            "blurry, low quality, distorted, deformed, bad anatomy, watermark, text",
        ),
        webui_seed=env_int("WEBUI_SEED", -1),
        webui_model_checkpoint=env_str("WEBUI_MODEL_CHECKPOINT", ""),
        webui_timeout=env_int("WEBUI_TIMEOUT", 300),
        comfyui_url=env_str("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/"),
        comfyui_workflow=Path(env_str("COMFYUI_WORKFLOW", "workflow_api.json")),
        comfyui_prompt_node_id=env_str("COMFYUI_PROMPT_NODE_ID", ""),
        comfyui_prompt_field=env_str("COMFYUI_PROMPT_FIELD", "text"),
        comfyui_negative_node_id=env_str("COMFYUI_NEGATIVE_NODE_ID", ""),
        comfyui_negative_field=env_str("COMFYUI_NEGATIVE_FIELD", "text"),
        comfyui_width_node_id=env_str("COMFYUI_WIDTH_NODE_ID", ""),
        comfyui_width_field=env_str("COMFYUI_WIDTH_FIELD", "width"),
        comfyui_height_node_id=env_str("COMFYUI_HEIGHT_NODE_ID", ""),
        comfyui_height_field=env_str("COMFYUI_HEIGHT_FIELD", "height"),
        comfyui_seed_node_id=env_str("COMFYUI_SEED_NODE_ID", ""),
        comfyui_seed_field=env_str("COMFYUI_SEED_FIELD", "seed"),
        comfyui_timeout=env_int("COMFYUI_TIMEOUT", 600),
        openrouter_api_key=env_str("OPENROUTER_API_KEY", ""),
        openrouter_model=env_str("OPENROUTER_IMAGE_MODEL", DEFAULT_OPENROUTER_MODEL),
        openrouter_timeout=env_int("OPENROUTER_TIMEOUT", 180),
    )


def load_scenes(path: Path) -> list[dict[str, str]]:
    """Đọc danh sách phân cảnh từ file JSON."""
    with path.open("r", encoding="utf-8") as file:
        scenes = json.load(file)

    if not isinstance(scenes, list):
        raise ValueError("prompts.json phải là một mảng JSON.")

    return scenes


def safe_output_filename(filename: str, extension: str) -> str:
    """Chuẩn hóa tên file để tránh ký tự lỗi trên Windows/Linux."""
    name = Path(filename).stem.strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return f"{name or 'image'}.{extension}"


def save_base64_image(b64_json: str, output_path: Path) -> None:
    """Lưu ảnh base64 thành file."""
    if "," in b64_json:
        b64_json = b64_json.split(",", 1)[1]

    output_path.write_bytes(base64.b64decode(b64_json))


def download_image(image_url: str, output_path: Path) -> None:
    """Tải ảnh từ URL bằng streaming."""
    with requests.get(image_url, stream=True, timeout=120) as response:
        response.raise_for_status()

        with output_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)


def request_json(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    response = requests.request(method, url, **kwargs)
    response.raise_for_status()
    return response.json()


def run_with_retries(label: str, retries: int, retry_delay: float, action: Any) -> None:
    for attempt in range(1, retries + 2):
        try:
            action()
            return
        except Exception as error:
            if attempt > retries:
                raise

            print(f"{label}: lỗi lần {attempt}: {error}")
            print(f"Đợi {retry_delay:.1f}s rồi thử lại...")
            time.sleep(retry_delay)


class LocalWebUIBackend:
    """Backend cho AUTOMATIC1111, Forge hoặc SD.Next API."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def check(self) -> None:
        request_json("GET", f"{self.config.webui_url}/sdapi/v1/options", timeout=20)
        print(f"Đã kết nối WebUI: {self.config.webui_url}")

    def list_models(self) -> None:
        models = request_json("GET", f"{self.config.webui_url}/sdapi/v1/sd-models", timeout=30)
        for model in models:
            print(model.get("title") or model.get("model_name") or model)

    def generate(self, prompt: str, output_path: Path) -> None:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": self.config.webui_negative_prompt,
            "width": self.config.width,
            "height": self.config.height,
            "steps": self.config.webui_steps,
            "cfg_scale": self.config.webui_cfg_scale,
            "sampler_name": self.config.webui_sampler_name,
            "seed": self.config.webui_seed,
            "batch_size": 1,
            "n_iter": 1,
            "save_images": False,
        }

        if self.config.webui_model_checkpoint:
            payload["override_settings"] = {
                "sd_model_checkpoint": self.config.webui_model_checkpoint
            }
            payload["override_settings_restore_afterwards"] = False

        data = request_json(
            "POST",
            f"{self.config.webui_url}/sdapi/v1/txt2img",
            json=payload,
            timeout=self.config.webui_timeout,
        )
        images = data.get("images") or []

        if not images:
            raise ValueError("WebUI không trả về ảnh.")

        save_base64_image(images[0], output_path)


class ComfyUIBackend:
    """Backend cho ComfyUI workflow API, phù hợp Flux."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.client_id = str(uuid.uuid4())

    def check(self) -> None:
        request_json("GET", f"{self.config.comfyui_url}/system_stats", timeout=20)
        if not self.config.comfyui_workflow.exists():
            raise FileNotFoundError(
                f"Không thấy workflow ComfyUI: {self.config.comfyui_workflow}"
            )
        print(f"Đã kết nối ComfyUI: {self.config.comfyui_url}")
        print(f"Workflow: {self.config.comfyui_workflow}")

    def generate(self, prompt: str, output_path: Path) -> None:
        workflow = self.load_workflow()
        self.apply_prompt(workflow, prompt)
        self.apply_dimensions(workflow)
        self.apply_seed(workflow)

        queued = request_json(
            "POST",
            f"{self.config.comfyui_url}/prompt",
            json={"prompt": workflow, "client_id": self.client_id},
            timeout=30,
        )
        prompt_id = queued.get("prompt_id")
        if not prompt_id:
            raise ValueError(f"ComfyUI không trả về prompt_id: {queued}")

        image_meta = self.wait_for_first_image(prompt_id)
        self.download_comfyui_image(image_meta, output_path)

    def load_workflow(self) -> dict[str, Any]:
        with self.config.comfyui_workflow.open("r", encoding="utf-8") as file:
            return copy.deepcopy(json.load(file))

    def apply_prompt(self, workflow: dict[str, Any], prompt: str) -> None:
        if self.config.comfyui_prompt_node_id:
            self.set_node_input(
                workflow,
                self.config.comfyui_prompt_node_id,
                self.config.comfyui_prompt_field,
                prompt,
            )
        else:
            self.replace_placeholder(workflow, "__PROMPT__", prompt)

        negative = self.config.webui_negative_prompt
        if self.config.comfyui_negative_node_id:
            self.set_node_input(
                workflow,
                self.config.comfyui_negative_node_id,
                self.config.comfyui_negative_field,
                negative,
            )
        else:
            self.replace_placeholder(workflow, "__NEGATIVE_PROMPT__", negative)

    def apply_dimensions(self, workflow: dict[str, Any]) -> None:
        if self.config.comfyui_width_node_id:
            self.set_node_input(
                workflow,
                self.config.comfyui_width_node_id,
                self.config.comfyui_width_field,
                self.config.width,
            )
        else:
            self.replace_placeholder(workflow, "__WIDTH__", self.config.width)

        if self.config.comfyui_height_node_id:
            self.set_node_input(
                workflow,
                self.config.comfyui_height_node_id,
                self.config.comfyui_height_field,
                self.config.height,
            )
        else:
            self.replace_placeholder(workflow, "__HEIGHT__", self.config.height)

    def apply_seed(self, workflow: dict[str, Any]) -> None:
        seed = self.config.webui_seed
        if seed < 0:
            seed = int(time.time() * 1000) % 2_147_483_647

        if self.config.comfyui_seed_node_id:
            self.set_node_input(
                workflow,
                self.config.comfyui_seed_node_id,
                self.config.comfyui_seed_field,
                seed,
            )
        else:
            self.replace_placeholder(workflow, "__SEED__", seed)

    def set_node_input(
        self, workflow: dict[str, Any], node_id: str, field_name: str, value: Any
    ) -> None:
        node = workflow.get(node_id)
        if not node:
            raise KeyError(f"Không thấy node ComfyUI ID {node_id}.")

        inputs = node.setdefault("inputs", {})
        inputs[field_name] = value

    def replace_placeholder(self, value: Any, placeholder: str, replacement: Any) -> Any:
        if isinstance(value, dict):
            for key, child in value.items():
                value[key] = self.replace_placeholder(child, placeholder, replacement)
            return value

        if isinstance(value, list):
            for index, child in enumerate(value):
                value[index] = self.replace_placeholder(child, placeholder, replacement)
            return value

        if value == placeholder:
            return replacement

        if isinstance(value, str) and placeholder in value:
            return value.replace(placeholder, str(replacement))

        return value

    def wait_for_first_image(self, prompt_id: str) -> dict[str, str]:
        deadline = time.time() + self.config.comfyui_timeout

        while time.time() < deadline:
            history = request_json(
                "GET",
                f"{self.config.comfyui_url}/history/{prompt_id}",
                timeout=30,
            )
            item = history.get(prompt_id)
            outputs = (item or {}).get("outputs") or {}

            for output in outputs.values():
                images = output.get("images") or []
                if images:
                    return images[0]

            time.sleep(1)

        raise TimeoutError("ComfyUI tạo ảnh quá thời gian chờ.")

    def download_comfyui_image(self, image_meta: dict[str, str], output_path: Path) -> None:
        params = {
            "filename": image_meta.get("filename", ""),
            "subfolder": image_meta.get("subfolder", ""),
            "type": image_meta.get("type", "output"),
        }
        with requests.get(
            f"{self.config.comfyui_url}/view",
            params=params,
            stream=True,
            timeout=120,
        ) as response:
            response.raise_for_status()
            with output_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)


class OpenRouterBackend:
    """Backend cloud qua OpenRouter Image API."""

    def __init__(self, config: Config) -> None:
        self.config = config
        if not config.openrouter_api_key:
            raise RuntimeError("Thiếu OPENROUTER_API_KEY trong .env.")

        # Khởi tạo OpenAI client để giữ cấu hình SDK tương thích OpenRouter.
        self.client = OpenAI(
            base_url=BASE_URL,
            api_key=config.openrouter_api_key,
            default_headers={
                "HTTP-Referer": REFERER,
                "X-Title": APP_TITLE,
            },
        )

    def check(self) -> None:
        response = requests.get(
            f"{BASE_URL}/images/models",
            headers=self.headers(),
            timeout=30,
        )
        response.raise_for_status()
        print("Đã kết nối OpenRouter Image API.")
        print(f"Model: {self.config.openrouter_model}")

    def generate(self, prompt: str, output_path: Path) -> None:
        response = requests.post(
            IMAGE_API_URL,
            headers=self.headers(),
            json={
                "model": self.config.openrouter_model,
                "prompt": prompt,
                "size": f"{self.config.width}x{self.config.height}",
                "aspect_ratio": "16:9",
                "output_format": self.config.output_format,
            },
            timeout=self.config.openrouter_timeout,
        )

        if response.status_code == 402:
            raise RuntimeError("HTTP 402 - OpenRouter không đủ credits.")

        response.raise_for_status()
        data = response.json()
        items = data.get("data") or []

        if not items:
            raise ValueError(f"OpenRouter không trả về ảnh: {data}")

        image = items[0]
        if image.get("url"):
            download_image(image["url"], output_path)
            return

        if image.get("b64_json"):
            save_base64_image(image["b64_json"], output_path)
            return

        raise ValueError(f"OpenRouter không trả về url hoặc b64_json: {data}")

    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": REFERER,
            "X-Title": APP_TITLE,
        }


def create_backend(config: Config) -> Any:
    if config.backend == "local_webui":
        return LocalWebUIBackend(config)

    if config.backend == "comfyui":
        return ComfyUIBackend(config)

    if config.backend == "openrouter":
        return OpenRouterBackend(config)

    raise ValueError(f"Backend không hợp lệ: {config.backend}")


def select_scenes(
    scenes: list[dict[str, str]], start_index: int, limit: int | None
) -> list[tuple[int, dict[str, str]]]:
    start = max(start_index, 1)
    selected = list(enumerate(scenes[start - 1 :], start=start))
    return selected[:limit] if limit else selected


def run_generation(config: Config, backend: Any) -> None:
    scenes = load_scenes(config.prompts_file)
    selected_scenes = select_scenes(scenes, config.start_index, config.limit)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Backend: {config.backend}")
    print(f"Kích thước: {config.width}x{config.height}")
    print(f"Số prompt sẽ xử lý: {len(selected_scenes)}")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for index, scene in selected_scenes:
        filename = scene.get("filename", "")
        prompt = scene.get("prompt", "")

        if not filename or not prompt:
            print(f"[{index}] Bỏ qua: thiếu filename hoặc prompt.")
            skip_count += 1
            continue

        output_path = config.output_dir / safe_output_filename(
            filename, config.output_format
        )

        if config.skip_existing and output_path.exists():
            print(f"[{index}] Đã có, bỏ qua: {output_path.name}")
            skip_count += 1
            continue

        print(f"[{index}] Đang tạo ảnh: {output_path.name}")

        if config.dry_run:
            print(f"[{index}] Dry run: {prompt[:120]}")
            continue

        try:
            run_with_retries(
                f"[{index}] {filename}",
                config.retries,
                config.retry_delay,
                lambda: backend.generate(prompt, output_path),
            )
            print(f"[{index}] Hoàn tất: {output_path}")
            success_count += 1
        except Exception as error:
            print(f"[{index}] Lỗi với '{filename}': {error}")
            fail_count += 1

            if "HTTP 402" in str(error):
                print("Dừng sớm vì lỗi credits sẽ lặp lại với các ảnh tiếp theo.")
                break

    print("\nTổng kết")
    print(f"- Thành công: {success_count}")
    print(f"- Bỏ qua: {skip_count}")
    print(f"- Lỗi: {fail_count}")
    print(f"- Thư mục ảnh: {config.output_dir}")


def main() -> None:
    configure_console_encoding()
    args = parse_args()
    config = load_config(args)
    backend = create_backend(config)

    if args.list_webui_models:
        LocalWebUIBackend(config).list_models()
        return

    if args.check:
        backend.check()
        return

    run_generation(config, backend)


if __name__ == "__main__":
    main()
