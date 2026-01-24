import streamlit as st
import os
import zipfile
import io
import shutil
import logging
import time
from dotenv import load_dotenv

# Import consolidated Converter
from src.ai_converter import AIConverter
from src.converter import Converter as TraditionalConverter

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_DIR = "output"

st.set_page_config(
    page_title="Excel to Markdown Converter",
    page_icon="📄",
    layout="wide"
)

def init_session_state():
    """Initialize session state variables"""
    if 'is_processing' not in st.session_state:
        st.session_state.is_processing = False
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
    if 'results' not in st.session_state:
        st.session_state.results = {'created': [], 'errors': []}
    if 'processing_paths' not in st.session_state:
        st.session_state.processing_paths = []

def main():
    init_session_state()
    
    st.title("📄 Excel/CSV to Markdown Converter")
    st.markdown("Chuyển đổi file Excel (nhiều sheet) hoặc CSV sang Markdown format.")

    # Disable sidebar inputs if processing
    input_disabled = st.session_state.is_processing

    # Sidebar Configuration
    st.sidebar.header("Cấu hình")
    
    conversion_mode = st.sidebar.radio(
        "Chọn chế độ chuyển đổi:",
        options=["AI-Powered", "Traditional (Rule-based)"],
        index=0,
        help="AI-Powered: Dùng AI để hiểu và convert nội dung. Traditional: Convert theo rule cứng.",
        disabled=input_disabled
    )
    
    mode_key = "ai" if conversion_mode == "AI-Powered" else "traditional"
    
    api_key = None
    selected_model = None
    system_prompt = ""

    if mode_key == "ai":
        st.sidebar.subheader("Cấu hình AI")
        use_custom_config = st.sidebar.checkbox("Custom Configuration", value=False, disabled=input_disabled)
        
        default_api_key = os.getenv("GEMINI_API_KEY")
        env_model = os.getenv("GEMINI_MODEL")
        default_model = env_model if env_model else "gemini-2.0-flash-exp"

        if use_custom_config:
            api_key = st.sidebar.text_input("Gemini API Key", type="password", value="", disabled=input_disabled)
            if api_key and not input_disabled:
                try:
                    models = AIConverter.list_models(api_key)
                    if models:
                        selected_model = st.sidebar.selectbox("Chọn Model", options=models, index=0, disabled=input_disabled)
                    else:
                        st.sidebar.error("Không tìm thấy model nào.")
                        selected_model = st.sidebar.text_input("Nhập tên Model", value=default_model, disabled=input_disabled)
                except:
                    selected_model = st.sidebar.text_input("Nhập tên Model", value=default_model, disabled=input_disabled)
            else:
                selected_model = st.sidebar.text_input("Nhập tên Model", value=default_model, disabled=input_disabled)

            system_prompt = st.sidebar.text_area("Custom System Prompt", height=100, disabled=input_disabled)
        else:
            api_key = default_api_key
            selected_model = default_model
            st.sidebar.info(f"Using Default Model: {selected_model}")
            if not api_key:
                st.sidebar.warning("⚠️ Chưa cấu hình GEMINI_API_KEY trong .env!")

    else:
        st.sidebar.info("Chế độ Traditional sẽ chuyển đổi dựa trên cấu trúc bảng có sẵn.")

    # Main UI - Always show Uploader to preserve state
    uploaded_files = st.file_uploader(
        "Chọn file Excel hoặc CSV",
        type=['xlsx', 'xls', 'csv'],
        accept_multiple_files=True,
        disabled=input_disabled
    )

    # Logic: If processing, show progress. If not, show Start button.
    if st.session_state.is_processing:
        st.info("🔄 Hệ thống đang xử lý...")
        
        # Validation checks
        if mode_key == "ai" and not api_key:
             st.error("Vui lòng cung cấp API Key để sử dụng chế độ AI.")
             st.session_state.is_processing = False
             st.rerun()
             
        # Progress UI
        process_container = st.container()
        status_text = process_container.empty()
        progress_bar = process_container.progress(0)
        
        # Use saved paths ensuring we don't rely only on re-reading uploaded buffers if unpredictable
        saved_paths = st.session_state.get('processing_paths', [])
        
        all_created = []
        all_errs = []

        try:
            converter = None
            if mode_key == "ai":
                converter = AIConverter(
                    api_key=api_key,
                    model_name=selected_model,
                    system_prompt=system_prompt
                )

            def update_progress(task_name, current_step, total_steps):
                percent = int((current_step / total_steps) * 100) if total_steps > 0 else 0
                progress_bar.progress(percent)
                status_text.text(f"⏳ {task_name} ({current_step}/{total_steps})")

            for idx, file_path in enumerate(saved_paths):
                if not os.path.exists(file_path):
                    continue
                    
                file_name = os.path.basename(file_path)
                status_text.text(f"📂 Đang xử lý file {idx+1}/{len(saved_paths)}: {file_name}")
                
                if mode_key == "ai":
                    created, errors = converter.convert_file(
                        file_path, 
                        OUTPUT_DIR, 
                        progress_callback=update_progress
                    )
                    all_created.extend(created)
                    all_errs.extend(errors)
                else:
                     trad_conv = TraditionalConverter(file_path, OUTPUT_DIR)
                     if file_path.endswith('.csv'):
                         created = trad_conv.convert_csv(file_path)
                     else:
                         created = trad_conv.convert_excel(file_path)
                     all_created.extend(created)
                     progress_bar.progress(100)
            
            st.session_state.results = {'created': all_created, 'errors': all_errs}
            st.session_state.processing_complete = True
            st.session_state.processing_paths = [] 
            
        except Exception as e:
            st.error(f"Lỗi: {e}")
            logger.error(f"Processing Error: {e}")
        finally:
             if os.path.exists(os.path.join(OUTPUT_DIR, "temp_input")):
                shutil.rmtree(os.path.join(OUTPUT_DIR, "temp_input"))
             st.session_state.is_processing = False
             st.rerun()

    else:
        # Not processing state
        if uploaded_files:
            st.write(f"Đã chọn {len(uploaded_files)} files.")
            
            # Start Button logic
            if st.button("🚀 Bắt đầu chuyển đổi", type="primary"):
                # Save input files immediately
                temp_input_dir = os.path.join(OUTPUT_DIR, "temp_input")
                os.makedirs(temp_input_dir, exist_ok=True)
                
                saved_paths = []
                try:
                    for file in uploaded_files:
                        file.seek(0)
                        path = os.path.join(temp_input_dir, file.name)
                        with open(path, "wb") as f:
                            f.write(file.getbuffer())
                        saved_paths.append(path)
                    
                    st.session_state.processing_paths = saved_paths
                    st.session_state.is_processing = True
                    st.session_state.processing_complete = False
                    st.session_state.results = {'created': [], 'errors': []}
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi lưu file: {e}")

    # 3. Result Display
    if st.session_state.processing_complete and not st.session_state.is_processing:
        st.markdown("---")
        st.success("✅ Quá trình xử lý hoàn tất!")
        created_files = st.session_state.results['created']
        errors = st.session_state.results['errors']

        if errors:
            st.error(f"Có {len(errors)} lỗi xảy ra:")
            for err in errors:
                st.warning(f"📄 **{err['file']}**: {err['error']}")
        
        if created_files:
            st.success(f"Đã tạo thành công {len(created_files)} files Markdown.")
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in created_files:
                    if os.path.exists(file_path):
                        arcname = os.path.relpath(file_path, OUTPUT_DIR)
                        zf.write(file_path, arcname)
            
            st.download_button(
                label="📦 Tải tất cả (.zip)",
                data=zip_buffer.getvalue(),
                file_name="markdown_output.zip",
                mime="application/zip",
                type="primary"
            )
        elif not errors:
             st.warning("Không có file nào được tạo ra.")
             
        if st.button("Làm mới (Clear Log)"):
             st.session_state.processing_complete = False
             st.session_state.results = {'created': [], 'errors': []}
             st.rerun()

    st.markdown("---")
    st.caption("Powered by Google Gemini | Stateful v3")

if __name__ == "__main__":
    main()
