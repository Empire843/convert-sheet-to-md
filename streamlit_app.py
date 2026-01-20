import streamlit as st
import os
import shutil
import logging
from pathlib import Path
from dotenv import load_dotenv
import zipfile
import io
import sys

# Load environment variables
load_dotenv()

# Add src to python path to resolve internal imports in src module
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import core logic from src (now accessible directly)
from ai_converter import AIConverter
from converter import Converter as TraditionalConverter

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
    page_title="Excel/CSV to Markdown Converter",
    page_icon="🤖",
    layout="wide"
)

st.title("📄 Excel/CSV to Markdown Converter")
st.markdown("Chuyển đổi file Excel và CSV sang Markdown.")

# Sidebar Configuration
st.sidebar.header("Cấu hình")

# Mode Selection
conversion_mode = st.sidebar.radio(
    "Chế độ chuyển đổi",
    options=["AI-Powered", "Traditional (Rule-based)"],
    index=0,
    help="AI-Powered: Dùng AI để hiểu và convert nội dung (chậm hơn, tốn phí). Traditional: Convert theo rule cứng (nhanh, miễn phí)."
)

mode_key = "ai" if conversion_mode == "AI-Powered" else "traditional"

# AI Configuration (Only show in AI Mode)
if mode_key == "ai":
    st.sidebar.subheader("Cấu hình AI")
    
    # Custom Configuration Toggle
    use_custom_config = st.sidebar.checkbox("Custom Configuration", value=False, help="Bật để tự nhập API Key và chọn Model khác.")
    
    if use_custom_config:
        # API Key
        api_key = st.sidebar.text_input(
            "Gemini API Key",
            type="password",
            value="",
            help="Nhập Google Gemini API Key của bạn."
        )

        # Model Selection
        model_options = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro"]
        
        # Determine default index
        default_model_index = 0
        env_model = os.getenv("GEMINI_MODEL")
        if env_model in model_options:
            default_model_index = model_options.index(env_model)
            
        selected_model = st.sidebar.selectbox(
            "Chọn Model",
            options=model_options,
            index=default_model_index
        )

        # Custom Model Input
        use_custom_model_name = st.sidebar.checkbox("Nhập tên model khác")
        if use_custom_model_name:
            selected_model = st.sidebar.text_input("Model Name", value=selected_model)

        # System Prompt
        default_prompt = ""
        system_prompt = st.sidebar.text_area(
            "Custom System Prompt (Optional)",
            value=default_prompt,
            height=150,
            help="Thêm hướng dẫn bổ sung cho AI."
        )
    else:
        # Defaults
        api_key = os.getenv("GEMINI_API_KEY")
        selected_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        system_prompt = ""
        
        # Display info about current defaults
        st.sidebar.info(f"Using Default Model: {selected_model}")
        if not api_key:
             st.sidebar.warning("⚠️ Chưa cấu hình API Key mặc định (Environment Variable)!")

else:
    # Traditional Mode Config (Visual placeholder if needed)
    st.sidebar.info("Chế độ Traditional sẽ chuyển đổi file dựa trên cấu trúc bảng có sẵn.")

# Main UI - File Upload
uploaded_files = st.file_uploader(
    "Chọn file Excel hoặc CSV",
    type=['xlsx', 'xls', 'csv'],
    accept_multiple_files=True
)

if uploaded_files:
    st.write(f"Đã chọn {len(uploaded_files)} files.")
    
    if st.button("🚀 Bắt đầu chuyển đổi", type="primary"):
        # Validate API Key for AI Mode
        final_api_key = api_key if (mode_key == "ai" and use_custom_config) else os.getenv("GEMINI_API_KEY")
        
        if mode_key == "ai" and not final_api_key:
            st.error("⚠️ Vui lòng nhập API Key hoặc cấu hình Environment Variable!")
            st.stop()
            
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Clear temp dirs
        for folder in [UPLOAD_DIR, OUTPUT_DIR]:
            if os.path.exists(folder):
                shutil.rmtree(folder)
            os.makedirs(folder, exist_ok=True)

        # Save uploaded files
        saved_paths = []
        for uploaded_file in uploaded_files:
            file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            saved_paths.append(file_path)
        
        all_created_files = []
        all_errors = []
        
        try:
            if mode_key == "ai":
                # AI CONVERSION LOGIC
                converter = AIConverter(
                    api_key=final_api_key,
                    provider="gemini",
                    model_name=selected_model,
                    system_prompt=system_prompt
                )
                
                total_files = len(saved_paths)
                for i, file_path in enumerate(saved_paths):
                    status_text.text(f"Đang xử lý (AI): {Path(file_path).name}...")
                    created, errors = converter.convert(file_path, OUTPUT_DIR)
                    all_created_files.extend(created)
                    all_errors.extend(errors)
                    progress_bar.progress((i + 1) / total_files)
                    
            else:
                # TRADITIONAL CONVERSION LOGIC
                status_text.text("Đang xử lý (Traditional)...")
                converter = TraditionalConverter(UPLOAD_DIR, OUTPUT_DIR)
                converter.convert()
                
                # Gather results manually since convert() doesn't return list in the same format
                # We iterate OUTPUT_DIR recursively
                for root, dirs, files in os.walk(OUTPUT_DIR):
                    for file in files:
                        all_created_files.append(os.path.join(root, file))
                
                progress_bar.progress(100)

            status_text.text("✅ Hoàn tất!")
            
            # Show Errors (AI Mode mainly)
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
                    # Only show download button for main files to avoid clutter (e.g. images)
                    # Or show all? Let's show .md files prominently
                    if file_name.endswith('.md'):
                        with open(file_path, "rb") as f:
                            st.download_button(
                                label=f"⬇️ Tải {file_name}",
                                data=f,
                                file_name=file_name,
                                mime="text/markdown",
                                key=file_path # Unique key
                            )
                
                # Zip everything
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, dirs, files in os.walk(OUTPUT_DIR):
                        for file in files:
                            zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), OUTPUT_DIR))
                
                st.download_button(
                    label="📦 Tải tất cả (.zip)",
                    data=zip_buffer.getvalue(),
                    file_name="markdown_output.zip",
                    mime="application/zip",
                    type="primary"
                )
            elif not all_errors:
                st.warning("Không có file nào được tạo ra. Vui lòng kiểm tra lại file đầu vào.")

        except Exception as e:
            st.error(f"Lỗi hệ thống: {str(e)}")
            logger.exception("Conversion failed")

st.markdown("---")
st.caption("Powered by Google Gemini | Developed with Streamlit")
