# Hướng Dẫn Chạy Trên Máy Thuê GPU

File này dành cho trường hợp máy thuê mới cài VS Code và Git, đã clone source code xong.

## 1. Mở PowerShell Trong Thư Mục Source

Vào thư mục repo đã clone, ví dụ:

```powershell
cd "C:\duong-dan-toi-repo-cua-ban"
```

Nếu đang mở bằng VS Code thì có thể bấm:

```text
Terminal > New Terminal
```

## 2. Kiểm Tra GPU

Chạy:

```powershell
nvidia-smi
```

Nếu thấy card NVIDIA và VRAM, ví dụ RTX 5060 Ti 16GB, là ổn.

## 3. Cài Môi Trường Python Cho Script

Trong thư mục repo:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Sau đó mở file `.env` và để cấu hình chính như sau:

```env
GEN_BACKEND=local_webui
WEBUI_URL=http://127.0.0.1:7860
PROMPTS_FILE=prompts.json
OUTPUT_DIR=video_assets
IMAGE_WIDTH=1024
IMAGE_HEIGHT=576
OUTPUT_FORMAT=png
SKIP_EXISTING=true
```

## 4. Cài Stable Diffusion WebUI Forge

Script `bulk_image_generator.py` không tự chạy model AI. Nó cần một WebUI local đang mở API ở port `7860`.

Khuyến nghị dùng Forge vì dễ chạy và tiết kiệm VRAM hơn AUTOMATIC1111.

Clone Forge ở thư mục khác, ví dụ ổ C:

```powershell
cd C:\
git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git
cd stable-diffusion-webui-forge
```

Chạy Forge với API:

```powershell
set COMMANDLINE_ARGS=--api --listen
.\webui-user.bat
```

Lần đầu chạy sẽ mất thời gian vì Forge tự tải và cài nhiều package.

Khi thấy dòng tương tự bên dưới là Forge đã chạy:

```text
Running on local URL: http://127.0.0.1:7860
```

Giữ cửa sổ PowerShell này mở. Đừng tắt nó khi đang tạo ảnh.

## 5. Tải Model

Bạn cần tải model SDXL hoặc checkpoint phù hợp rồi đặt vào thư mục:

```text
C:\stable-diffusion-webui-forge\models\Stable-diffusion
```

Để test nhanh, nên dùng một model SDXL trước. Sau khi tải xong, mở trình duyệt:

```text
http://127.0.0.1:7860
```

Chọn model trong giao diện WebUI.

## 6. Kiểm Tra Script Kết Nối Được WebUI

Mở PowerShell khác, quay lại thư mục repo:

```powershell
cd "C:\duong-dan-toi-repo-cua-ban"
.\.venv\Scripts\activate
python bulk_image_generator.py --check
```

Nếu hiện:

```text
Đã kết nối WebUI: http://127.0.0.1:7860
```

là ổn.

## 7. Chạy Thử 1 Ảnh

Trước khi chạy toàn bộ, test 1 ảnh:

```powershell
python bulk_image_generator.py --dry-run --limit 1
python bulk_image_generator.py --limit 1
```

Ảnh sẽ được lưu vào:

```text
video_assets
```

Nếu ảnh đầu tiên tạo thành công, chạy toàn bộ:

```powershell
python bulk_image_generator.py
```

## 8. Chạy Tiếp Nếu Bị Gián Đoạn

Script mặc định bỏ qua ảnh đã tồn tại vì trong `.env` có:

```env
SKIP_EXISTING=true
```

Nếu bị tắt giữa chừng, chỉ cần chạy lại:

```powershell
python bulk_image_generator.py
```

Nó sẽ tự bỏ qua các ảnh đã tạo.

Muốn bắt đầu từ scene số 20:

```powershell
python bulk_image_generator.py --start-index 20
```

Muốn chạy 5 ảnh từ scene số 20:

```powershell
python bulk_image_generator.py --start-index 20 --limit 5
```

Muốn tạo lại cả ảnh đã tồn tại:

```powershell
python bulk_image_generator.py --force
```

## 9. Lỗi Thường Gặp

### Lỗi Không Kết Nối Được WebUI

Nếu `python bulk_image_generator.py --check` báo lỗi kết nối, kiểm tra:

- Forge/WebUI đã chạy chưa.
- Có bật `--api` chưa.
- URL trong `.env` có đúng là `http://127.0.0.1:7860` không.

### Lỗi Thiếu VRAM

Nếu bị CUDA out of memory:

- Giảm kích thước ảnh xuống `768x432` để test.
- Giảm `WEBUI_STEPS`, ví dụ `20`.
- Dùng model nhẹ hơn.
- Chạy từng ảnh một như script hiện tại, không bật batch lớn trong WebUI.

### Lỗi Không Có Python

Kiểm tra:

```powershell
python --version
```

Nếu không có Python, cài Python 3.10 hoặc 3.11, nhớ tick `Add python.exe to PATH`.

## 10. Cấu Hình Gợi Ý

Trong `.env`, cấu hình ổn để chạy SDXL 16:9:

```env
GEN_BACKEND=local_webui
WEBUI_URL=http://127.0.0.1:7860
IMAGE_WIDTH=1024
IMAGE_HEIGHT=576
WEBUI_STEPS=25
WEBUI_CFG_SCALE=6
WEBUI_SAMPLER=DPM++ 2M Karras
WEBUI_SEED=-1
SKIP_EXISTING=true
```

Nếu máy yếu hoặc lỗi VRAM, đổi:

```env
IMAGE_WIDTH=768
IMAGE_HEIGHT=432
WEBUI_STEPS=20
```

## 11. Quy Trình Ngắn Gọn Mỗi Lần Thuê Máy

```powershell
# 1. Chạy Forge ở một cửa sổ PowerShell
cd C:\stable-diffusion-webui-forge
set COMMANDLINE_ARGS=--api --listen
.\webui-user.bat
```

```powershell
# 2. Chạy script ở cửa sổ PowerShell khác
cd "C:\duong-dan-toi-repo-cua-ban"
.\.venv\Scripts\activate
python bulk_image_generator.py --check
python bulk_image_generator.py --limit 1
python bulk_image_generator.py
```

