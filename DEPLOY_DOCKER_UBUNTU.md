# Deploy Docker trên VPS Ubuntu

## 1) Cài Docker + Compose plugin
```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```
Đăng xuất/đăng nhập lại để nhận quyền `docker`.

## 2) Chuẩn bị source và file env
```bash
git clone <repo-url> auto_rpa_hdsaison
cd auto_rpa_hdsaison
cp backend/.env.example backend/.env
```

Chỉnh `backend/.env` tối thiểu:
- `ALLOWED_ORIGINS=http://<VPS_IP>:8000,https://<domain-cua-ban>`
- `ENCRYPTION_KEY=<fernet-key>`

Sinh key nếu cần:
```bash
python3 - << 'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

## 3) Build & chạy container
```bash
docker-compose build --no-cache
docker-compose up -d
```

Xem log:
```bash
docker-compose logs -f app
```

## 4) Kiểm tra health
```bash
curl http://127.0.0.1:8000/api/health
```

## 5) Cập nhật phiên bản mới
```bash
git pull
docker-compose build
docker-compose up -d
```

## 6) Sao lưu dữ liệu quan trọng
Dữ liệu được mount ra host:
- `./app_data`
- `./downloads_contracts`

Chỉ cần backup 2 thư mục này.
