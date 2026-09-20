# Hướng dẫn setup dự án cho thành viên mới

Tài liệu này dành cho thành viên bắt đầu từ một máy Windows chưa cài đặt môi trường phát triển. Các lệnh bên dưới sử dụng **Windows PowerShell** và được chạy từ thư mục gốc của repository, trừ khi có ghi chú khác.

Repository: <https://github.com/truongduy199/doan_PBL4.git>

## 1. Thành viên cần cài gì?

Mọi thành viên cần:

- Tài khoản GitHub đã được chủ repository mời làm collaborator nếu repository đang để private.
- GitHub Desktop.
- Visual Studio Code hoặc IDE tương đương.
- Git (được cài kèm GitHub Desktop).

Cài thêm theo phần việc:

| Phần việc | Công cụ cần cài |
| --- | --- |
| Edge Server, AI, camera | Python 3.11 x64 |
| Dashboard | Node.js LTS và npm |
| Firebase | Node.js LTS; Firebase CLI chỉ cần khi chạy emulator hoặc deploy rules |
| ESP32 | Arduino IDE 2.x và board package ESP32 by Espressif Systems |

Khuyến nghị dùng **Python 3.11 x64**. Không nên dùng Python 3.13 cho môi trường InsightFace của dự án nếu chưa kiểm tra tương thích.

## 2. Clone dự án bằng GitHub Desktop

1. Đăng nhập GitHub Desktop bằng tài khoản đã được thêm vào repository.
2. Chọn **File > Clone repository**.
3. Mở tab **URL** và nhập:

   ```text
   https://github.com/truongduy199/doan_PBL4.git
   ```

4. Chọn đường dẫn ngắn, dễ thao tác, ví dụ:

   ```text
   C:\PBL4\doan_PBL4
   ```

5. Nhấn **Clone**.
6. Trong GitHub Desktop, chọn **Repository > Open in Visual Studio Code**.

Không tải dự án bằng nút **Download ZIP**, vì bản ZIP không có lịch sử Git và không thể pull/push đúng quy trình nhóm.

## 3. Kiểm tra thư mục làm việc

Mở PowerShell tại thư mục gốc vừa clone. Kiểm tra:

```powershell
Get-Location
git status
```

Kết quả `git status` ban đầu nên có dạng:

```text
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

Nếu PowerShell đang ở `C:\Users\...` thay vì thư mục dự án, hãy chuyển thư mục trước khi chạy các lệnh tiếp theo:

```powershell
Set-Location "C:\PBL4\doan_PBL4"
```

## 4. Tạo branch cá nhân trước khi sửa code

Không làm việc trực tiếp trên `main`.

Trong GitHub Desktop:

1. Nhấn **Fetch origin**, sau đó **Pull origin** nếu có thay đổi mới.
2. Chọn **Current branch > New branch**.
3. Đặt tên branch theo một trong các mẫu:

   ```text
   feature/ten-thanh-vien-ten-chuc-nang
   fix/ten-thanh-vien-ten-loi
   docs/ten-thanh-vien-noi-dung
   ```

Ví dụ:

```text
feature/an-dashboard-parking-slots
fix/binh-camera-reconnect
```

Mỗi branch chỉ nên xử lý một chức năng hoặc một lỗi để pull request dễ kiểm tra và ít xung đột.

## 5. Setup Edge Server và InsightFace

Chỉ bắt buộc với thành viên làm Python, AI, camera hoặc backend.

### 5.1. Kiểm tra Python

```powershell
py -3.11 --version
```

Kết quả cần là Python 3.11.x. Nếu lệnh không tồn tại, cài Python 3.11 x64 từ trang chính thức của Python và bật tùy chọn thêm Python Launcher khi cài đặt.

### 5.2. Tạo virtual environment

Chạy tại thư mục gốc repository:

```powershell
py -3.11 -m venv .venv
```

Kích hoạt môi trường:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& ".\.venv\Scripts\Activate.ps1"
```

Sau khi kích hoạt, đầu dòng PowerShell thường có `(.venv)`. Kiểm tra đúng Python:

```powershell
python --version
python -c "import sys; print(sys.executable)"
```

Đường dẫn phải trỏ vào:

```text
<thu-muc-du-an>\.venv\Scripts\python.exe
```

`.venv` là môi trường riêng của từng máy và đã được `.gitignore`; không commit hoặc chép thư mục này cho nhau.

### 5.3. Cài dependency Python

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".\edge-server[dev]"
python -m pip check
```

Kiểm tra các thư viện chính:

```powershell
python -c "import cv2, insightface, onnxruntime as ort; print('OpenCV:', cv2.__version__); print('Providers:', ort.get_available_providers())"
```

Máy mới cài theo luồng mặc định thường thấy `CPUExecutionProvider`. Đây là cấu hình hợp lệ và dễ đồng bộ nhất giữa các thành viên.

Nếu InsightFace báo lỗi khi build package, hãy kiểm tra đang dùng Python 3.11 x64. Nếu vẫn lỗi, cài **Microsoft C++ Build Tools** với workload **Desktop development with C++**, mở lại PowerShell rồi chạy lại lệnh cài dependency.

### 5.4. Tải model `buffalo_l`

Model không được lưu trên GitHub vì có file lớn hơn giới hạn thông thường của Git. Mỗi máy chạy AI phải tải model riêng:

```powershell
& ".\.venv\Scripts\insightface-cli.exe" model.download buffalo_l --root ".\edge-server\models\insightface"
```

Kiểm tra model:

```powershell
Get-ChildItem ".\edge-server\models\insightface\models\buffalo_l" -Filter "*.onnx"
```

Thư mục này cần có 5 file `.onnx`. Các file model đã được `.gitignore`; không bật tùy chọn đưa chúng vào commit.

Lưu ý: `edge-server/scripts/download_insightface_models.py` và `verify_model_hashes.py` hiện mới là khung phát triển, chưa thay thế lệnh `insightface-cli` ở trên.

### 5.5. Chạy thử webcam nhận diện khuôn mặt

Luồng CPU tương thích với hầu hết máy:

```powershell
python ".\edge-server\scripts\test_webcam_insightface.py" --camera 0 --provider cpu
```

Nếu không mở được camera mặc định:

```powershell
python ".\edge-server\scripts\test_webcam_insightface.py" --camera 1 --provider cpu
```

Phím điều khiển:

- `SPACE`: quét khi khuôn mặt đầy đủ, nhìn thẳng và vùng nhận diện chuyển xanh.
- `R`: bắt đầu lại.
- `Q` hoặc `Esc`: thoát.

Chương trình thử nghiệm chỉ giữ face template trong RAM, không lưu ảnh webcam hoặc embedding xuống đĩa.

Thiết lập hiện tại đã giới hạn detector ở 320 x 320, inference khoảng 4 FPS và 2 CPU thread. Nếu máy không có GPU NVIDIA, tiếp tục dùng `--provider cpu`.

### 5.6. GPU NVIDIA là tùy chọn

Không cần GPU để phát triển phần lớn chức năng. Thành viên chỉ cài ONNX Runtime GPU khi được phân công chạy benchmark hoặc AI realtime và có GPU NVIDIA phù hợp.

Không cài đồng thời `onnxruntime` và `onnxruntime-gpu` một cách tùy ý vì hai package cùng cung cấp module `onnxruntime`. Trước khi thay đổi môi trường GPU, trao đổi với người phụ trách AI để thống nhất phiên bản CUDA, cuDNN và ONNX Runtime. Khi môi trường GPU đã được cấu hình đúng, chạy:

```powershell
python ".\edge-server\scripts\test_webcam_insightface.py" --camera 0 --provider auto
```

Ứng dụng phải hiển thị `CUDAExecutionProvider`. Nếu không, dùng lại `--provider cpu` thay vì sửa code chung.

### 5.7. Tạo file môi trường Edge Server

```powershell
Copy-Item ".\edge-server\.env.example" ".\edge-server\.env"
```

Chỉ sửa `edge-server/.env` trên máy cá nhân. Không commit file này.

Các giá trị Firebase thật và `EMBEDDING_SECRET_KEY` phải nhận từ người quản lý dự án qua kênh riêng. Không gửi service-account JSON, secret hoặc `.env` lên GitHub, issue, pull request hay nhóm chat công khai.

### 5.8. Khởi tạo SQLite

Script migration dùng đường dẫn tương đối nên cần chạy bên trong `edge-server`:

```powershell
Push-Location ".\edge-server"
python ".\scripts\init_database.py"
Pop-Location
```

Database được tạo tại `edge-server/var/db/parking.sqlite3` và đã được `.gitignore`.

### 5.9. Kiểm tra package Edge Server

```powershell
Push-Location ".\edge-server"
python -m smart_parking.main
Pop-Location
```

Ở giai đoạn hiện tại, `bootstrap_system()` mới là khung kết nối thành phần. Lệnh trên chủ yếu xác nhận package và cấu trúc import hoạt động; chưa khởi chạy toàn bộ camera, Firebase và ESP32.

## 6. Setup Dashboard

Chỉ bắt buộc với thành viên làm React, giao diện hoặc tích hợp Firebase phía web.

### 6.1. Kiểm tra Node.js

```powershell
node --version
npm --version
```

Dùng một bản Node.js LTS còn được hỗ trợ. Nếu nhóm gặp khác biệt giữa các máy, thống nhất cùng một major version trước khi cập nhật `package-lock.json`.

### 6.2. Cài package đúng theo lock file

```powershell
Push-Location ".\dashboard"
npm ci
Pop-Location
```

Dùng `npm ci` cho lần setup đầu tiên. Chỉ dùng `npm install <package>` khi thật sự thêm hoặc nâng cấp dependency và muốn cập nhật `package-lock.json`.

`dashboard/node_modules` đã được `.gitignore`; không commit thư mục này.

### 6.3. Tạo cấu hình Firebase cho Dashboard

```powershell
Copy-Item ".\dashboard\.env.example" ".\dashboard\.env.local"
```

Thay các giá trị mẫu trong `dashboard/.env.local` bằng Firebase Web App config do người quản lý dự án cung cấp. Không sửa `.env.example` thành thông tin thật và không commit `.env.local`.

### 6.4. Chạy Dashboard

```powershell
Push-Location ".\dashboard"
npm run dev
Pop-Location
```

Mở địa chỉ Vite in ra trong terminal, thường là <http://localhost:5173>.

Kiểm tra build trước khi tạo pull request:

```powershell
Push-Location ".\dashboard"
npm run build
Pop-Location
```

## 7. Setup Firebase

### 7.1. Phát triển Dashboard không cần quyền Admin

Dashboard chỉ cần Firebase Web App config trong `dashboard/.env.local`. Không cấp service account cho thành viên chỉ làm giao diện.

### 7.2. Thành viên phụ trách Edge/Firebase Admin

File service account dự kiến đặt tại:

```text
edge-server/configs/firebase-credentials.json
```

File này đã được `.gitignore`. Chỉ người phụ trách backend cần nhận file qua kênh an toàn. Không đổi tên thành file không khớp quy tắc ignore rồi commit.

### 7.3. Firebase Emulator tùy chọn

Thành viên cần kiểm thử rules cục bộ có thể chạy từ thư mục `firebase`:

```powershell
Push-Location ".\firebase"
npx firebase-tools emulators:start --project demo-smart-parking
Pop-Location
```

Lần đầu, `npx` có thể hỏi tải `firebase-tools`; chỉ đồng ý khi package đến từ npm chính thức. Không cần đăng nhập Firebase để dùng project ID bắt đầu bằng `demo-` cho kiểm thử cục bộ.

## 8. Setup ESP32

Chỉ bắt buộc với thành viên phụ trách firmware hoặc kiểm thử phần cứng.

1. Cài Arduino IDE 2.x.
2. Trong Boards Manager, cài **esp32 by Espressif Systems**.
3. Mở file:

   ```text
   firmware/esp32_smart_parking/esp32_smart_parking.ino
   ```

4. Sao chép cấu hình mẫu:

   ```powershell
   Copy-Item ".\firmware\esp32_smart_parking\config.example.h" ".\firmware\esp32_smart_parking\config.h"
   ```

5. Chọn đúng board ESP32, cổng COM và kiểm tra chân trong `pins.h` theo mạch thực tế.
6. Compile trước, sau đó mới upload lên board.

Firmware hiện vẫn có một số hàm phần cứng ở dạng khung. Compile thành công không có nghĩa servo, LCD và buzzer đã hoạt động đầy đủ; cần kiểm thử từng sketch trong `firmware-tests/` trước khi ghép hệ thống.

## 9. Quy trình làm việc hằng ngày bằng GitHub Desktop

### Trước khi bắt đầu

1. Chuyển sang `main`.
2. Nhấn **Fetch origin** rồi **Pull origin**.
3. Chuyển lại branch đang làm.
4. Chọn **Branch > Update from main** nếu `main` có thay đổi mới.

### Khi đang làm

- Chỉ sửa file thuộc nhiệm vụ của branch.
- Commit nhỏ, mô tả rõ nội dung.
- Không dùng một commit cho nhiều chức năng không liên quan.
- Không format hoặc đổi line ending hàng loạt toàn repository.

Ví dụ commit message:

```text
feat(face): validate complete frontal face before capture
fix(camera): retry webcam connection after read failure
docs(setup): add dashboard onboarding steps
```

### Khi hoàn thành

1. Chạy kiểm tra phù hợp với phần đã sửa.
2. Xem lại toàn bộ tab **Changes** trong GitHub Desktop.
3. Đảm bảo không có `.env`, credential, model, database, ảnh camera hoặc file build.
4. Commit vào branch cá nhân.
5. Nhấn **Push origin**.
6. Nhấn **Create Pull Request**.
7. Mô tả chức năng, cách kiểm tra và phần còn hạn chế.
8. Chỉ merge vào `main` sau khi ít nhất một thành viên khác review.

## 10. Những file tuyệt đối không commit

- `.venv/`, `venv/`
- `dashboard/node_modules/`, `dashboard/dist/`
- Mọi file `.env` và `dashboard/.env.local`
- `edge-server/configs/firebase-credentials.json` và mọi service-account JSON
- Model `.onnx`, `.pt`, `.weights` hoặc file model nén
- SQLite database trong `edge-server/var/db/`
- Log, cache, ảnh biển số hoặc ảnh chụp từ camera
- File build Arduino như `.bin`, `.hex`, `.elf`

Nếu một file bí mật đã lỡ xuất hiện trong tab **Changes**, bỏ chọn file đó, báo ngay cho trưởng nhóm và bổ sung `.gitignore` trước khi commit. Nếu bí mật đã được push, xóa file trong commit là chưa đủ; phải thu hồi và tạo lại credential đó.

## 11. Xử lý lỗi thường gặp

### `python.exe is not recognized` hoặc không tìm thấy `.venv`

- Kiểm tra đang đứng ở thư mục gốc bằng `Get-Location`.
- Đảm bảo đã chạy `py -3.11 -m venv .venv`.
- Kích hoạt bằng `& ".\.venv\Scripts\Activate.ps1"`.

Không dùng đường dẫn môi trường Python riêng trên máy của thành viên khác.

### PowerShell không cho chạy `Activate.ps1`

Chỉ nới policy cho cửa sổ PowerShell hiện tại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Không cần thay đổi execution policy toàn máy.

### Không tìm thấy model `buffalo_l`

Chạy lại:

```powershell
& ".\.venv\Scripts\insightface-cli.exe" model.download buffalo_l --root ".\edge-server\models\insightface"
```

### Không mở được webcam

- Đóng Zoom, Teams, trình duyệt hoặc ứng dụng đang giữ camera.
- Cho phép Desktop apps truy cập camera trong Windows Camera privacy settings.
- Thử `--camera 1`.
- Kiểm tra camera trước bằng ứng dụng Camera của Windows.

### CPU cao khi chạy InsightFace

Dùng cấu hình mặc định đã tối ưu:

```powershell
python ".\edge-server\scripts\test_webcam_insightface.py" --provider cpu --det-size 320 --cpu-threads 2 --inference-fps 4
```

### `npm` không được nhận diện

Cài Node.js LTS, đóng và mở lại PowerShell, sau đó kiểm tra `node --version` và `npm --version`.

### Xung đột khi pull hoặc merge

Không chọn tùy tiện **Discard changes**. Trong GitHub Desktop, mở danh sách conflicted files, so sánh phần của hai branch, giữ đúng nội dung cần thiết, chạy lại chương trình rồi mới đánh dấu resolved và commit merge. Nếu xung đột liên quan contract/schema dùng chung, trao đổi với người phụ trách trước khi chọn phiên bản.

## 12. Checklist hoàn tất setup

### Tất cả thành viên

- [ ] Clone repository bằng GitHub Desktop.
- [ ] `git status` sạch trên `main`.
- [ ] Tạo được branch cá nhân.
- [ ] Biết Fetch, Pull, Commit, Push và tạo Pull Request.
- [ ] Đã đọc danh sách file không được commit.

### Thành viên Edge/AI

- [ ] Python 3.11 và `.venv` hoạt động.
- [ ] `pip check` không báo lỗi.
- [ ] Có đủ 5 file ONNX của `buffalo_l`.
- [ ] Webcam chạy được bằng `--provider cpu`.
- [ ] SQLite migration chạy thành công nếu nhiệm vụ cần database.

### Thành viên Dashboard

- [ ] `npm ci` thành công.
- [ ] Có `dashboard/.env.local` trên máy cá nhân.
- [ ] `npm run dev` mở được giao diện.
- [ ] `npm run build` thành công trước khi tạo pull request.

### Thành viên Firmware

- [ ] Arduino IDE nhận đúng ESP32 và cổng COM.
- [ ] Có `config.h` cục bộ.
- [ ] Compile được sketch chính.
- [ ] Đã kiểm tra đúng sơ đồ chân trước khi cấp nguồn cho phần cứng.

