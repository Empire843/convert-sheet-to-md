import streamlit as st
import os
import shutil
import logging
from pathlib import Path
from dotenv import load_dotenv
import zipfile
import io

# Load environment variables
load_dotenv()

# Import core logic from src
from src.ai_converter import AIConverter
# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
UPLOAD_DIR = "temp_uploads"
OUTPUT_DIR = "temp_outputs"

# Setup directories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

st.set_page_config(
    page_title="Excel/CSV to Markdown Converter (AI Powered)",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Excel/CSV to Markdown Converter")
st.markdown("Chuyển đổi file Excel và CSV sang Markdown giữ nguyên định dạng bảng và nội dung bằng AI.")

# Sidebar Configuration
st.sidebar.header("Cấu hình AI")

# API Key
api_key = st.sidebar.text_input(
    "Gemini API Key",
    type="password",
    value=os.getenv("GEMINI_API_KEY", ""),
    help="Nhập Google Gemini API Key của bạn. Nếu để trống sẽ thử dùng key từ Environment Variable."
)

# Model Selection
model_options = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro"]
selected_model = st.sidebar.selectbox(
    "Chọn Model",
    options=model_options,
    index=0
)

# Custom Model Input
use_custom_model = st.sidebar.checkbox("Nhập tên model khác")
if use_custom_model:
    selected_model = st.sidebar.text_input("Model Name", value=selected_model)

# System Prompt
default_prompt = ""
system_prompt = st.sidebar.text_area(
    "Custom System Prompt (Optional)",
    value=default_prompt,
    height=150,
    help="Thêm hướng dẫn bổ sung cho AI."
)

# Main UI - File Upload
uploaded_files = st.file_uploader(
    "Chọn file Excel hoặc CSV",
    type=['xlsx', 'xls', 'csv'],
    accept_multiple_files=True
)

if uploaded_files:
    st.write(f"Đã chọn {len(uploaded_files)} files.")
    
    if st.button("🚀 Bắt đầu chuyển đổi", type="primary"):
        if not api_key and not os.getenv("GEMINI_API_KEY"):
            st.error("⚠️ Vui lòng nhập API Key!")
            st.stop()
            
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Clear temp dirs
        for folder in [UPLOAD_DIR, OUTPUT_DIR]:
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    logger.error(f'Failed to delete {file_path}. Reason: {e}')

        # Save uploaded files
        saved_paths = []
        for uploaded_file in uploaded_files:
            file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            saved_paths.append(file_path)
        
        # Initialize Converter
        try:
            converter = AIConverter(
                api_key=api_key or os.getenv("GEMINI_API_KEY"),
                provider="gemini",
                model_name=selected_model,
                system_prompt=system_prompt
            )
            
            all_created_files = []
            all_errors = []
            
            total_files = len(saved_paths)
            
            for i, file_path in enumerate(saved_paths):
                status_text.text(f"Đang xử lý: {Path(file_path).name}...")
                
                # Call convert (it returns (files, errors))
                created, errors = converter.convert(file_path, OUTPUT_DIR)
                
                all_created_files.extend(created)
                all_errors.extend(errors)
                
                progress_bar.progress((i + 1) / total_files)
            
            status_text.text("✅ Hoàn tất!")
            
            # Show Errors
            if all_errors:
                st.error(f"Có {len(all_errors)} lỗi xảy ra:")
                for err in all_errors:
                    st.warning(f"📄 **{err['file']}**: {err['error']}")
            
            # Show Success Results
            if all_created_files:
                st.success(f"Đã tạo thành công {len(all_created_files)} files Markdown/Assets.")
                
                # List files
                st.subheader("Kết quả:")
                for file_path in all_created_files:
                    file_name = Path(file_path).name
                    with open(file_path, "rb") as f:
                        btn = st.download_button(
                            label=f"⬇️ Tải {file_name}",
                            data=f,
                            file_name=file_name,
                            mime="text/markdown" if file_name.endswith('.md') else "application/octet-stream"
                        )
                
                # Zip everything
                timestamp = os.path.basename(OUTPUT_DIR) # or current time
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, dirs, files in os.walk(OUTPUT_DIR):
                        for file in files:
                            zf.write(os.path.join(root, file), file)
                
                st.download_button(
                    label="📦 Tải tất cả (.zip)",
                    data=zip_buffer.getvalue(),
                    file_name="markdown_output.zip",
                    mime="application/zip",
                    type="primary"
                )

        except Exception as e:
            st.error(f"Lỗi hệ thống: {str(e)}")

st.markdown("---")
st.caption("Powered by Google Gemini | Developed with Streamlit")
