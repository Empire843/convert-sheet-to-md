"""
AI-powered converter using Gemini API
Converts Excel/CSV files to Markdown using Google's Gemini AI
"""
import os
import time
import logging
import json
import re
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class AIConverter:
    """
    AI-powered converter coordinator (Monolithic Version).
    Handles AI interaction, batching (optional), and file saving.
    """
    
    SYSTEM_PROMPT = """You are a document-structure transformation engine.
Your goal is to preserve ALL content while improving semantic clarity.

ABSOLUTE RULES:
1. **DO NOT** output the raw "Unnamed: X" headers. Remove them.
2. **DO NOT** output the content as a giant Markdown table unless it is strictly a data table.
3. **DO** detect the semantic structure:
   - If a row looks like a header (e.g., "Màn hình ..."), make it a Header (##, ###).
   - If cells are key-value pairs, represent them as such (Bold Key: Value).
   - If there is a long text description, write it as a paragraph.

CONTENT FIDELITY:
- Preserve all Japanese and Vietnamese text exactly.
- Keep the logical flow.

OUTPUT FORMAT (JSON):
Return a JSON object with a single key "files".
{
  "files": [
    {
      "filename": "sheet_name.md",
      "content": "## Section Title\\n\\nContent description in paragraph form...\\n\\n### Subsection\\n- Item 1\\n- Item 2"
    }
  ]
}
"""

    def __init__(self, api_key: str = None, provider: str = 'gemini', model_name: str = 'gemini-1.5-flash', system_prompt: str = ''):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.additional_prompt = system_prompt
        
        # Priority: Env Var > Argument > Default
        env_model = os.getenv('GEMINI_MODEL')
        # Default to experimental model if not specified, as it works better currently with new API
        default_model = 'gemini-2.0-flash-exp'
        self.model_name = env_model if env_model else (model_name if model_name else default_model)
        
        if not self.api_key:
            raise ValueError("API key is required.")
            
        try:
             self.client = genai.Client(api_key=self.api_key)
             logger.info(f"AI Converter initialized with Gemini (Model: {self.model_name})")
        except Exception as e:
             logger.error(f"Failed to initialize Gemini client: {e}")
             raise e
             
        # Retry configuration
        self.max_retries = 5
        self.initial_retry_delay = 15

    @staticmethod
    def list_models(api_key: str) -> List[str]:
        """List available Gemini models"""
        try:
            client = genai.Client(api_key=api_key)
            models = []
            for m in client.models.list():
                name = m.name
                if name.startswith('models/'):
                    name = name.replace('models/', '')
                models.append(name)
            return sorted(models)
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []


    def convert_file(self, file_path: str, output_dir: str, progress_callback=None) -> Tuple[List[str], List[Dict]]:
        """
        Convert a single file using Gemini AI
        Args:
            file_path: Input path
            output_dir: Output path
            progress_callback: Callable(current_task_str, current_step_int, total_steps_int)
        """
        created_files = []
        errors = []
        
        try:
            logger.info(f"Converting file with AI: {file_path}")
            os.makedirs(output_dir, exist_ok=True)
            
            file_name = Path(file_path).name
            file_extension = Path(file_path).suffix.lower()
            base_name = Path(file_path).stem
            
            if file_extension in ['.xlsx', '.xls']:
                created, errs = self._process_excel(file_path, output_dir, base_name, file_name, progress_callback)
                created_files.extend(created)
                errors.extend(errs)
            elif file_extension == '.csv':
                if progress_callback: progress_callback("Processing CSV...", 0, 1)
                created, errs = self._process_csv(file_path, output_dir, base_name, file_name)
                if progress_callback: progress_callback("Completed CSV", 1, 1)
                created_files.extend(created)
                errors.extend(errs)
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Fatal error converting {file_path}: {error_msg}")
            errors.append({
                'file': Path(file_path).name,
                'error': self._friendly_error_message(error_msg)
            })

        return created_files, errors

    def _process_excel(self, file_path: str, output_dir: str, base_name: str, file_name: str, progress_callback=None) -> Tuple[List[str], List[Dict]]:
        created_files = []
        errors = []
        
        try:
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            logger.info(f"Excel file has {len(sheet_names)} sheets: {sheet_names}")
            
            # Force Individual Processing for better quality
            logger.info("🚀 Processing sheets individually...")
            
            for i, sheet_name in enumerate(sheet_names):
                try:
                    if progress_callback:
                        progress_callback(f"Sheet: {sheet_name}", i, len(sheet_names))
                        
                    logger.info(f"Processing sheet {i+1}/{len(sheet_names)}: {sheet_name}")
                    if i > 0:
                        time.sleep(2) # Small buffer

                        
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    
                    # Pre-processing
                    df.dropna(how='all', axis=0, inplace=True)
                    df.dropna(how='all', axis=1, inplace=True)
                    
                    if len(df) > 3000:
                         logger.warning(f"Sheet {sheet_name} is large ({len(df)} rows). Truncating to 3000 rows.")
                         df = df.head(3000)
                    
                    content_str = df.to_string(index=False, na_rep='')
                    
                    prompt = self.SYSTEM_PROMPT
                    if self.additional_prompt:
                        prompt += f"\nADDITIONAL INSTRUCTIONS:\n{self.additional_prompt}\n"
                    prompt += f"\n=== DATA FOR SHEET: {sheet_name} ===\n\n{content_str}"
                    
                    # Generate
                    response_text = self._generate_content(prompt)
                    
                    # Save
                    safe_sheet_name = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in sheet_name)
                    fallback_name = f"{base_name}_{safe_sheet_name}"
                    
                    files = self._parse_and_save_response(
                        response_text, output_dir, fallback_name, [sheet_name]
                    )
                    created_files.extend(files)
                    
                except Exception as sheet_err:
                    logger.error(f"Error processing sheet {sheet_name}: {sheet_err}")
                    errors.append({
                        'file': f"{file_name} - {sheet_name}",
                        'error': str(sheet_err)
                    })
                    
        except Exception as e:
            raise Exception(f"Lỗi khi đọc file Excel: {str(e)}")
            
        return created_files, errors

    def _process_csv(self, file_path: str, output_dir: str, base_name: str, file_name: str) -> Tuple[List[str], List[Dict]]:
        try:
            df = pd.read_csv(file_path)
            if len(df) > 5000:
                logger.warning(f"CSV has {len(df)} rows, truncating to 5000")
                df = df.head(5000)
            
            content_str = f"CSV file '{file_name}':\n\n{df.to_string(index=False)}"
            
            prompt = self.SYSTEM_PROMPT
            if self.additional_prompt:
                prompt += f"\nADDITIONAL INSTRUCTIONS:\n{self.additional_prompt}\n"
            prompt += f"\nHere is the file data:\n\n{content_str}"
            
            response_text = self._generate_content(prompt)
            
            files = self._parse_and_save_response(
                response_text, output_dir, base_name, [base_name]
            )
            return files, []
            
        except Exception as e:
             raise Exception(f"Lỗi khi đọc file CSV: {str(e)}")

    def _generate_content(self, prompt: str) -> str:
        """Call Gemini API with retry logic"""
        total_api_calls = 0
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    delay = self.initial_retry_delay * (2 ** (attempt - 1))
                    logger.warning(f"⚠️  RETRY attempt {attempt + 1}/{self.max_retries}. Default wait: {delay}s")
                    time.sleep(delay)
                
                total_api_calls += 1
                logger.info(f"🌐 Sending API request to Gemini ({self.model_name})...")
                
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json'
                    )
                )
                
                logger.info(f"✅ API CALL SUCCESS on attempt {attempt + 1}.")
                return self._extract_text(response)
                
            except Exception as retry_error:
                str_error = str(retry_error)
                last_error = retry_error
                logger.error(f"❌ API CALL FAILED on attempt {attempt + 1}: {str_error[:200]}...")
                
                if '429' in str_error or 'quota' in str_error.lower():
                    wait_match = re.search(r'retry in (\d+(\.\d+)?)s', str_error)
                    if wait_match:
                        time.sleep(float(wait_match.group(1)) + 1.5)
                        continue
        
        raise last_error or Exception("Failed to get response from AI")

    def _extract_text(self, response) -> str:
        try:
            return response.text
        except:
            # Fallback for candidates structure
            if hasattr(response, 'candidates') and response.candidates:
                parts = []
                for candidate in response.candidates:
                    if hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                              if hasattr(part, 'text'): parts.append(part.text)
                return '\n'.join(parts)
            return ""

    def _parse_and_save_response(self, response_text: str, output_dir: str, base_name: str, expected_names: List[str]) -> List[str]:
        created_files = []
        try:
            data = None
            # Try parse JSON
            try:
                data = json.loads(response_text)
            except:
                # Try finding JSON block
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    try: data = json.loads(json_match.group(1))
                    except: pass
                if not data:
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        try: data = json.loads(json_match.group(0))
                        except: pass
            
            if not data or 'files' not in data:
                logger.warning("❌ JSON PARSE FAILED. Saving raw response.")
                return self._save_simple_markdown(response_text, output_dir, f"{base_name}_fallback")
            
            for file_info in data['files']:
                filename = file_info.get('filename', 'output.md')
                content = file_info.get('content', '')
                
                if not filename.endswith('.md'): filename += '.md'
                if not filename.startswith(base_name): filename = f"{base_name}_{filename}"
                
                file_path = os.path.join(output_dir, filename)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                created_files.append(file_path)
                logger.info(f"Created file: {filename}")
                
            return created_files

        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return self._save_simple_markdown(response_text, output_dir, f"{base_name}_fallback")

    def _save_simple_markdown(self, content: str, output_dir: str, base_name: str) -> List[str]:
        path = os.path.join(output_dir, f"{base_name}.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return [path]

    def _friendly_error_message(self, error_msg: str) -> str:
        if "API key" in error_msg: return "API Key lỗi/thiếu."
        if "429" in error_msg or "quota" in error_msg.lower(): return "Quá giới hạn (Quota Exceeded)."
        if "404" in error_msg: return f"Model không tồn tại ({self.model_name})."
        return error_msg
