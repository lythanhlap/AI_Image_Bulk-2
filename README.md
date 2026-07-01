# Bulk Image Generator

Tạo ảnh hàng loạt từ `prompts.json`, lưu vào `video_assets/`. Repo này chạy được theo 3 cách:

- `local_webui`: dùng AUTOMATIC1111, Forge hoặc SD.Next API. Dễ nhất cho SDXL và nhiều máy thuê GPU.
- `comfyui`: dùng ComfyUI workflow API. Phù hợp Flux nếu bạn đã có workflow.
- `openrouter`: fallback cloud qua OpenRouter Image API.

## 1. Clone Và Cài Đặt

```powershell
git clone <repo-cua-ban>
cd <repo-cua-ban>
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Trên Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Chạy Local WebUI

Khuyến nghị cho máy thuê: chạy AUTOMATIC1111 hoặc Forge với API.

Ví dụ Windows:

```powershell
set COMMANDLINE_ARGS=--api --listen
webui-user.bat
```

Ví dụ Linux:

```bash
./webui.sh --api --listen
```

Trong `.env` để:

```env
GEN_BACKEND=local_webui
WEBUI_URL=http://127.0.0.1:7860
IMAGE_WIDTH=1024
IMAGE_HEIGHT=576
```

Kiểm tra kết nối:

```bash
python bulk_image_generator.py --check
```

Chạy thử 1 ảnh:

```bash
python bulk_image_generator.py --limit 1
```

Chạy toàn bộ:

```bash
python bulk_image_generator.py
```

## 3. Chạy ComfyUI Cho Flux

Trong ComfyUI, bật server bình thường rồi export workflow dạng API JSON. Trong node prompt, đặt text là:

```text
__PROMPT__
```

Nếu workflow có negative prompt, có thể đặt:

```text
__NEGATIVE_PROMPT__
```

Nếu muốn script tự thay kích thước hoặc seed bằng placeholder:

```text
__WIDTH__
__HEIGHT__
__SEED__
```

Đặt file workflow cạnh script, ví dụ `workflow_api.json`, rồi cấu hình `.env`:

```env
GEN_BACKEND=comfyui
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_WORKFLOW=workflow_api.json
```

Chạy:

```bash
python bulk_image_generator.py --limit 1
python bulk_image_generator.py
```

## 4. Dùng OpenRouter Fallback

Trong `.env`:

```env
GEN_BACKEND=openrouter
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_IMAGE_MODEL=black-forest-labs/flux.2-klein-4b
```

Chạy:

```bash
python bulk_image_generator.py
```

## 5. Định Dạng prompts.json

```json
[
  {
    "filename": "sc_01_morning_alarm",
    "prompt": "Close up of a modern alarm clock ringing, cinematic lighting."
  }
]
```

`filename` sẽ được lưu thành `.png` trong `video_assets/`.

## 6. Lệnh Hữu Ích

```bash
# Chỉ kiểm tra prompt, không tạo ảnh
python bulk_image_generator.py --dry-run

# Bắt đầu từ scene số 20
python bulk_image_generator.py --start-index 20

# Chạy 5 ảnh từ scene số 20
python bulk_image_generator.py --start-index 20 --limit 5

# Tạo lại ảnh dù file đã tồn tại
python bulk_image_generator.py --force

# Liệt kê checkpoint local WebUI
python bulk_image_generator.py --list-webui-models
```

## 7. Gợi Ý Máy Thuê

Với 2 lựa chọn 8GB và 16GB VRAM, nên chọn 16GB. SDXL chạy ổn hơn, Flux qua ComfyUI cũng dễ thở hơn. Thuê thử 1 giờ trước, tải model và chạy `--limit 1` để kiểm tra tốc độ trước khi chạy toàn bộ.
