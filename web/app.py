"""
Flask Web Application cho Excel/CSV to Markdown Converter
"""
import os
import shutil
import zipfile
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('/app/.env')

# Import converter modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from converter import Converter
from ai_converter import AIConverter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = '/app/uploads'
OUTPUT_FOLDER = '/app/output'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_size(file_path):
    """Get file size in human-readable format"""
    size = os.path.getsize(file_path)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def list_output_files():
    """List all files in output directory"""
    files = []
    output_path = Path(OUTPUT_FOLDER)
    
    for file_path in output_path.rglob('*'):
        if file_path.is_file() and file_path.name != '.gitkeep':
            relative_path = file_path.relative_to(output_path)
            files.append({
                'name': file_path.name,
                'path': str(relative_path),
                'full_path': str(file_path),
                'size': get_file_size(file_path),
                'type': 'image' if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg'] else 'markdown',
                'mtime': file_path.stat().st_mtime  # Add modification time for sorting
            })
    
    # Sort by modification time, newest first
    files.sort(key=lambda x: x['mtime'], reverse=True)
    
    return files


@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_files():
    """Handle file upload"""
    try:
        if 'files[]' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files[]')
        uploaded = []
        errors = []
        
        for file in files:
            if file.filename == '':
                continue
            
            if not allowed_file(file.filename):
                errors.append(f"{file.filename}: Định dạng không được hỗ trợ")
                continue
            
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Save file
            file.save(file_path)
            
            uploaded.append({
                'name': filename,
                'size': get_file_size(file_path),
                'type': filename.rsplit('.', 1)[1].lower()
            })
            
            logger.info(f"File uploaded: {filename}")
        
        response = {
            'success': True,
            'uploaded': uploaded,
            'errors': errors,
            'message': f'Đã upload {len(uploaded)} file thành công'
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/convert', methods=['POST'])
def convert_files():
    """
    Execute conversion (traditional or AI mode)
    """
    try:
        # Get conversion mode from request
        data = request.get_json() or {}
        mode = data.get('mode', 'traditional')  # 'traditional' or 'ai'
        
        # Check if there are files to convert
        upload_files_list = os.listdir(app.config['UPLOAD_FOLDER'])
        upload_files_list = [f for f in upload_files_list if not f.startswith('.')]
        
        if not upload_files_list:
            return jsonify({'error': 'Không có file nào để convert'}), 400
        
        # Clear previous output
        for item in os.listdir(app.config['OUTPUT_FOLDER']):
            item_path = os.path.join(app.config['OUTPUT_FOLDER'], item)
            if item != '.gitkeep':
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
        
        # Run converter based on mode
        if mode == 'ai':
            # AI mode
            ai_config = data.get('ai_config', {})
            use_custom_config = ai_config.get('use_custom_config', False)
            
            api_key = None
            provider = 'gemini'
            default_model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
            model_name = default_model
            system_prompt = ai_config.get('system_prompt', '')
            
            if use_custom_config:
                api_key = ai_config.get('api_key')
                provider = ai_config.get('provider', 'gemini')
                model_name = ai_config.get('model_name', default_model)
                if not model_name: 
                    model_name = default_model
            else:
                # Use env var
                api_key = os.getenv('GEMINI_API_KEY')
            
            if not api_key:
                return jsonify({'error': 'API Key chưa được cấu hình'}), 400
            
            logger.info(f"Using AI conversion mode (Provider: {provider}, Model: {model_name})")
            
            # Initialize converter with config
            ai_converter = AIConverter(
                api_key=api_key,
                provider=provider,
                model_name=model_name,
                system_prompt=system_prompt
            )
            created_files, errors = ai_converter.convert(app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER'])
        else:
            # Traditional mode
            logger.info("Using traditional conversion mode")
            converter = Converter(app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER'])
            converter.convert()
            errors = []
        
        # Get output files
        output_files = list_output_files()
        
        logger.info(f"Conversion completed ({mode} mode): {len(output_files)} files created, {len(errors)} errors")
        
        # Success if at least one file was created OR if we handled request without crashing
        # But if ONLY errors occurred, maybe success=False?
        # Let's keep success=True for the request handling, but frontend checks files/errors.
        # Actually, let's set success=True if files > 0, else False if there are errors and no files.
        is_success = len(output_files) > 0
        
        # Special case: success=True if no error happened (traditional mode usually doesn't return errors list yet)
        if mode != 'ai':
            is_success = True
            
        message = f'Đã chuyển đổi thành công ({"AI" if mode == "ai" else "Traditional"})! Tạo được {len(output_files)} file.'
        if errors:
            message += f' Có {len(errors)} file lỗi.'
        
        return jsonify({
            'success': is_success,
            'message': message,
            'files': output_files,
            'errors': errors,
            'mode': mode
        }), 200
        
    except Exception as e:
        logger.error(f"Conversion error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/files', methods=['GET'])
def get_files():
    """Get list of converted files"""
    try:
        files = list_output_files()
        return jsonify({
            'success': True,
            'files': files
        }), 200
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<path:filepath>', methods=['GET'])
def download_file(filepath):
    """Download a specific file"""
    try:
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], filepath)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File không tồn tại'}), 404
        
        return send_file(file_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete/<path:filepath>', methods=['DELETE'])
def delete_file(filepath):
    """Delete a specific file"""
    try:
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], filepath)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File không tồn tại'}), 404
        
        # Delete the file
        os.remove(file_path)
        
        # If it was in a subdirectory, try to remove empty parent directory
        parent_dir = os.path.dirname(file_path)
        if parent_dir != app.config['OUTPUT_FOLDER']:
            try:
                # Only remove if directory is empty
                if not os.listdir(parent_dir):
                    os.rmdir(parent_dir)
            except:
                pass  # Ignore errors when cleaning up directories
        
        logger.info(f"Deleted file: {filepath}")
        
        return jsonify({
            'success': True,
            'message': 'Đã xóa file thành công'
        }), 200
        
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        return jsonify({'error': str(e)}), 500



@app.route('/api/download-all', methods=['GET'])
def download_all():
    """Download all converted files as ZIP"""
    try:
        output_files = list_output_files()
        
        if not output_files:
            return jsonify({'error': 'Không có file nào để download'}), 404
        
        # Create ZIP file
        zip_path = '/tmp/converted_files.zip'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_info in output_files:
                zipf.write(file_info['full_path'], file_info['path'])
        
        return send_file(zip_path, as_attachment=True, download_name='converted_files.zip')
        
    except Exception as e:
        logger.error(f"Download all error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear', methods=['DELETE'])
def clear_all():
    """Clear all uploads and outputs"""
    try:
        # Clear uploads
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if filename != '.gitkeep':
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                os.remove(file_path)
        
        # Clear outputs
        for item in os.listdir(app.config['OUTPUT_FOLDER']):
            if item != '.gitkeep':
                item_path = os.path.join(app.config['OUTPUT_FOLDER'], item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
        
        logger.info("Cleared all files")
        
        return jsonify({
            'success': True,
            'message': 'Đã xóa tất cả file'
        }), 200
        
    except Exception as e:
        logger.error(f"Clear error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/check-ai', methods=['GET'])
def check_ai_available():
    """Check if Gemini API key is configured"""
    api_key = os.getenv('GEMINI_API_KEY')
    return jsonify({
        'available': bool(api_key),
        'message': 'AI conversion available' if api_key else 'GEMINI_API_KEY chưa được cấu hình'
    }), 200


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
