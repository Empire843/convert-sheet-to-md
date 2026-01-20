# Excel/CSV to Markdown Converter

Hệ thống chuyển đổi file Excel (.xlsx, .xls) và CSV sang định dạng Markdown với **2 modes hoạt động**: CLI và Web Interface.

## 🎯 Tính năng

### Core Features
- ✅ Hỗ trợ đa định dạng: `.xlsx`, `.xls`, `.csv`
- ✅ Xử lý tất cả sheets trong Excel
- ✅ Mỗi sheet → 1 file Markdown riêng
- ✅ Trích xuất và lưu ảnh/biểu đồ
- ✅ Tự động phát hiện encoding cho CSV
- ✅ Giữ nguyên cấu trúc dữ liệu

### Web Interface Features
- 🚀 Upload file qua drag-and-drop
- 🚀 Giao diện hiện đại với gradient design
- 🚀 Real-time conversion progress
- 🚀 Download từng file hoặc tất cả (ZIP)
- 🚀 Toast notifications
- 🚀 Responsive design

## 📁 Cấu trúc

```
excel2md-converter/
├── src/                    # Core converter modules
│   ├── converter.py
│   ├── excel_processor.py
│   ├── csv_processor.py
│   ├── markdown_generator.py
│   └── image_extractor.py
├── web/                    # Web application
│   ├── app.py             # Flask server
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/main.js
│   └── templates/
│       └── index.html
├── input/                  # CLI mode input
├── uploads/                # Web mode uploads
├── output/                 # Converted files
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 🚀 Quick Start

### Option 1: Web Interface (Recommended)

```bash
# Build and start web server
docker compose up -d

# Access web UI
# Open browser: http://localhost:5000
```

**Workflow:**
1. Drag & drop files hoặc click "Chọn file"
2. Click "🚀 Thực hiện chuyển đổi"
3. Download files từ danh sách kết quả
4. Click "📦 Tải tất cả (ZIP)" để download hết

### Option 2: Command Line Interface

```bash
# Chuyển đổi tất cả files trong input/
docker run --rm \
  -v "$(pwd)/input:/app/input" \
  -v "$(pwd)/output:/app/output" \
  excel2md-converter \
  python src/converter.py /app/input/

# Chuyển đổi 1 file cụ thể
docker run --rm \
  -v "$(pwd)/input:/app/input" \
  -v "$(pwd)/output:/app/output" \
  excel2md-converter \
  python src/converter.py /app/input/your-file.xlsx
```

## 📊 Ví dụ

### Input: Excel file với 3 sheets

```
data.xlsx
  ├── Sheet1 (dữ liệu + ảnh)
  ├── Sheet2 (dữ liệu)
  └── Sheet3 (dữ liệu)
```

### Output

```
output/data/
  ├── data_Sheet1.md
  ├── data_Sheet2.md
  ├── data_Sheet3.md
  └── Sheet1_image_1.png
```

### Markdown Format

```markdown
# Sheet1

| Cột 1 | Cột 2 | Cột 3 |
| --- | --- | --- |
| Giá trị 1 | Giá trị 2 | Giá trị 3 |

![Image 1 from Sheet1](./Sheet1_image_1.png)
```

## 🌐 Web API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main UI |
| `/api/upload` | POST | Upload files |
| `/api/convert` | POST | Execute conversion |
| `/api/files` | GET | List converted files |
| `/api/download/<path>` | GET | Download file |
| `/api/download-all` | GET | Download all as ZIP |
| `/api/clear` | DELETE | Clear workspace |
| `/health` | GET | Health check |

## 🛠️ Development

### Requirements
- Docker
- Docker Compose

### Local Setup (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run web server
python web/app.py
```

### Build Docker Image

```bash
docker compose build
```

### View Logs

```bash
docker logs excel2md-web -f
```

### Stop Server

```bash
docker compose down
```

## 📝 Configuration

### Port
Default: `5000`

Thay đổi trong `docker-compose.yml`:
```yaml
ports:
  - "8080:5000"  # External:Internal
```

### Max File Size
Default: `50MB`

Thay đổi trong `web/app.py`:
```python
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
```

## 🎨 Screenshots

### Web Interface

![Web UI](docs/web-interface.png)

_Upload area với drag-and-drop, control buttons, và results section_

## 🔧 Troubleshooting

### Container không start
```bash
# Kiểm tra logs
docker logs excel2md-web

# Restart container
docker compose restart
```

### Port 5000 đã được sử dụng
```bash
# Thay đổi port trong docker-compose.yml
ports:
  - "5001:5000"
```

### Permission errors
```bash
# Đảm bảo folders có quyền ghi
chmod -R 755 uploads/ output/
```

## 📦 Dependencies

```
pandas==2.1.4       # Data processing
openpyxl==3.1.2     # Excel .xlsx
xlrd==2.0.1         # Excel .xls
Pillow==10.2.0      # Image processing
chardet==5.2.0      # Encoding detection
Flask==3.0.0        # Web server
Flask-CORS==4.0.0   # CORS support
```

## 📜 License

MIT License

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.

## 💡 Tips

- **Web Mode**: Best cho end-users, dễ sử dụng
- **CLI Mode**: Best cho automation, batch processing
- **Large Files**: Sử dụng CLI mode cho files > 50MB
- **Multiple Files**: Web mode hỗ trợ multi-upload

## 📧 Support

Create an issue on GitHub nếu gặp vấn đề.

---

Made with ❤️ using Flask + Docker
# convert-sheet-to-md
