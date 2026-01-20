"""
AI-powered converter using Gemini API
Converts Excel/CSV files to Markdown using Google's Gemini AI
"""
import os
import time
import logging
from pathlib import Path
from google import genai
from google.genai import types
from typing import List, Dict

logger = logging.getLogger(__name__)


class AIConverter:
    """
    AI-powered converter using Gemini API
    """
    
    SYSTEM_PROMPT = """You are a document-structure transformation engine.
Your goal is to preserve ALL content while improving semantic clarity.

ABSOLUTE RULES:
- Do NOT remove, summarize, or rewrite content.
- You MAY change layout and structure for readability.
- Content fidelity is mandatory; layout fidelity is optional.

CONTENT HANDLING:
- Preserve all text exactly as written (including Japanese).
- Preserve the original logical order of content.
- Empty cells used only for layout MAY be removed.

LAYOUT TRANSFORMATION RULES:
- Detect layout-based tables (tables with many empty cells or alignment purpose).
  → Convert them into:
    - Headings (##, ###)
    - Bullet lists
    - Paragraphs

- Detect data tables (tables with headers and consistent rows).
  → Convert them into Markdown tables.

STRUCTURE MAPPING:
- Section titles → Markdown headings
- 改修内容 / 要件 / 対応内容 → ### headings
- Descriptive rows → bullet points or paragraphs
- Captions and notes → block text under related section

IMAGES:
- Extract and reference images at the nearest related section.

VALIDATION:
- Ensure every textual element from the source exists in the output.
- No content may disappear due to layout transformation.

OUTPUT:
- Return a JSON object with a single key "files".
- "files" should be a list of objects, each containing:
  - "filename": The suggested filename (must end in .md).
  - "content": The full markdown content.

Example:
{
  "files": [
    {
      "filename": "sheet_name.md",
      "content": "# Title\n\nContent..."
    }
  ]
}

- Valid JSON only. Do not include explanation text outside the JSON.
"""
    
    def __init__(self, api_key: str = None, provider: str = 'gemini', model_name: str = 'gemini-2.5-flash', system_prompt: str = ''):
        """
        Initialize AI Converter
        
        Args:
            api_key: AI Provider API key
            provider: AI Provider (gemini, openai, etc.)
            model_name: Model name to use
            system_prompt: Additional system prompt
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.provider = provider
        self.model_name = model_name
        self.additional_prompt = system_prompt
        
        if not self.api_key:
            raise ValueError("API key is required.")
        
        if self.provider == 'gemini':
            # Configure Gemini Client
            self.client = genai.Client(api_key=self.api_key)
            logger.info(f"AI Converter initialized with Gemini (Model: {self.model_name})")
        else:
            # Placeholder for future providers
            logger.warning(f"Provider {self.provider} not fully supported yet, defaulting logic to Gemini structure if applicable")
        
        # Retry configuration
        self.max_retries = 5
        self.initial_retry_delay = 5  # Increased initial delay
    


    @staticmethod
    def list_models(api_key: str) -> List[str]:
        """
        List available Gemini models
        
        Args:
            api_key: Gemini API Key
            
        Returns:
            List of model names
        """
        try:
            client = genai.Client(api_key=api_key)
            models = []
            # Note: The new SDK might have different list_models structure.
            # Adapting to common pattern or falling back to a known list if direct listing is complex.
            # The v1alpha/beta API allowed listing, the new SDK client.models.list() is the way.
            for m in client.models.list():
                 # Filter by generateContent capability if possible, or just list names
                 # The new SDK model objects might differ. Assuming m.name works.
                name = m.name
                if name.startswith('models/'):
                    name = name.replace('models/', '')
                models.append(name)
            return sorted(models)
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []

    def convert_file(self, file_path: str, output_dir: str) -> tuple[List[str], List[Dict]]:
        """
        Convert a single file using Gemini AI with retry logic
        For Excel, converts each sheet individually to isolate errors.
        
        Args:
            file_path: Path to input file
            output_dir: Directory to save output files
            
        Returns:
            Tuple: (List of created file paths, List of error dicts)
        """
        created_files = []
        errors = []
        
        try:
            logger.info(f"Converting file with AI: {file_path}")
            os.makedirs(output_dir, exist_ok=True)
            
            file_name = Path(file_path).name
            file_extension = Path(file_path).suffix.lower()
            base_name = Path(file_path).stem
            
            # Handler for Excel files (Sheet by Sheet)
            if file_extension in ['.xlsx', '.xls']:
                import pandas as pd
                try:
                    excel_file = pd.ExcelFile(file_path)
                    sheet_names = excel_file.sheet_names
                    
                    for sheet_name in sheet_names:
                        try:
                            # Read sheet content
                            df = pd.read_excel(file_path, sheet_name=sheet_name)
                            # Increase limit to avoid missing content in large files
                            if len(df) > 5000:
                                logger.warning(f"Sheet {sheet_name} has {len(df)} rows, truncating to 5000")
                                df = df.head(5000)
                            
                            content_str = f"### Sheet: {sheet_name}\n"
                            # Convert full dataframe to string without truncation
                            content_str += df.to_string(index=False)
                            
                            # Convert this specific sheet
                            logger.info(f"Processing sheet: {sheet_name}")
                            sheet_files = self._generate_and_save(
                                content_str, 
                                output_dir, 
                                f"{base_name}_{sheet_name}", 
                                is_single_sheet=True
                            )
                            created_files.extend(sheet_files)
                            
                        except Exception as e:
                            error_msg = str(e)
                            logger.error(f"Error converting sheet '{sheet_name}' in {file_name}: {error_msg}")
                            errors.append({
                                'file': f"{file_name} - {sheet_name}",
                                'error': self._friendly_error_message(error_msg)
                            })
                            
                except Exception as e:
                    # Error reading the Excel file itself
                    raise Exception(f"Lỗi khi đọc file Excel: {str(e)}")

            # Handler for CSV files
            elif file_extension == '.csv':
                import pandas as pd
                try:
                    df = pd.read_csv(file_path)
                    if len(df) > 5000:
                         logger.warning(f"CSV has {len(df)} rows, truncating to 5000")
                         df = df.head(5000)
                    
                    content_str = f"CSV file '{file_name}':\n\n"
                    # Convert full dataframe to string without truncation
                    content_str += df.to_string(index=False)
                    
                    sheet_files = self._generate_and_save(
                        content_str, 
                        output_dir, 
                        base_name,
                        is_single_sheet=False
                    )
                    created_files.extend(sheet_files)
                    
                except Exception as e:
                    raise Exception(f"Lỗi khi đọc file CSV: {str(e)}")
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")

        except Exception as e:
            # Fatal error for the whole file
            error_msg = str(e)
            logger.error(f"Fatal error converting {file_path}: {error_msg}")
            errors.append({
                'file': Path(file_path).name,
                'error': self._friendly_error_message(error_msg)
            })

        return created_files, errors
    
    def _friendly_error_message(self, error_msg: str) -> str:
        """Map raw error messages to user-friendly strings"""
        if "API key not valid" in error_msg:
            return "API Key không hợp lệ."
        elif "quota" in error_msg.lower() or "429" in error_msg:
            return "Đã hết hạn ngạch (Quota exceeded) hoặc gửi quá nhanh."
        elif "not found" in error_msg.lower() and "model" in error_msg.lower():
            return f"Model '{self.model_name}' không tồn tại hoặc không được hỗ trợ."
        return error_msg

    def _generate_and_save(self, data_content: str, output_dir: str, base_name: str, is_single_sheet: bool = False) -> List[str]:
        """Helper to call AI and save result (extracted from original convert_file logic)"""
        
        # Adjust prompt for single sheet vs multi-sheet wrapper
        prompt_instruction = self.SYSTEM_PROMPT
        if is_single_sheet:
            prompt_instruction += "\nIMPORTANT: You are converting a SINGLE sheet. Return result for this sheet only."
        
        final_prompt = f"{prompt_instruction}\n"
        if self.additional_prompt:
            final_prompt += f"\nADDITIONAL INSTRUCTIONS:\n{self.additional_prompt}\n"
        
        final_prompt += f"\nHere is the file data:\n\n{data_content}"
        
        # Retry with exponential backoff
        response = None
        last_error = None
        
        import re
        import time 

        for attempt in range(self.max_retries):
            try:
                # Delay handling
                if attempt > 0:
                    # Default exponential backoff
                    delay = self.initial_retry_delay * (2 ** (attempt - 1))
                    logger.info(f"Retry attempt {attempt + 1}/{self.max_retries}. Default wait: {delay}s")
                    time.sleep(delay)
                
                # New SDK Usage with JSON Mode
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=final_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json'
                    )
                )
                break
                
            except Exception as retry_error:
                str_error = str(retry_error)
                last_error = retry_error
                
                if '429' in str_error or 'quota' in str_error.lower():
                    # Smart Rate Limiting: Try to parse "Please retry in X s."
                    # Pattern example: "Please retry in 24.77550335s." or "retry in 30s"
                    wait_match = re.search(r'retry in (\d+(\.\d+)?)s', str_error)
                    if wait_match:
                        wait_time = float(wait_match.group(1))
                        # Add small buffer
                        final_wait = wait_time + 1.5
                        logger.warning(f"Rate limited. API requested wait: {wait_time}s. Sleeping for {final_wait}s...")
                        time.sleep(final_wait)
                        # Don't increment exponential backoff for next loop if we sleep here? 
                        # Actually the loop will continue and do attempt check.
                        # We should make sure we don't double sleep. 
                        # But simplest is just continue, the next loop start will add some exponential sleep too, which is safer.
                        continue
                    
                    if 'rate limit exceeded' in str_error.lower() and attempt == self.max_retries - 1:
                         # Let it propagate
                         pass
                    else:
                        continue # Retry
                
                # If we are here, it might be another error or we are out of retries
                if attempt == self.max_retries - 1:
                     pass
                else:
                     if '429' not in str_error and 'quota' not in str_error.lower():
                         raise retry_error
        
        if response is None:
            raise last_error or Exception("Failed to get response from AI (Unknown Error)")
        
        # Extract text logic for new SDK
        try:
            response_text = response.text
        except:
             # If simple text doesn't work, extract from parts
            parts = []
            if hasattr(response, 'candidates') and response.candidates:
                 for candidate in response.candidates:
                     if hasattr(candidate.content, 'parts'):
                         for part in candidate.content.parts:
                             if hasattr(part, 'text'):
                                 parts.append(part.text)
            response_text = '\n'.join(parts)
            
        return self._parse_and_save_response(response_text, output_dir, base_name)
    
    def _parse_and_save_response(self, response_text: str, output_dir: str, base_name: str) -> List[str]:
        """
        Parse AI response and save Markdown files
        
        Args:
            response_text: Response from Gemini
            output_dir: Output directory
            base_name: Base name for files
            
        Returns:
            List of created files
        """
        created_files = []
        
        try:
            # Try to parse as JSON first
            import json
            import re
            
            data = None
            # 1. Try direct JSON parse (expected with response_mime_type='application/json')
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                pass
            
            if not data:
                # 2. Extract JSON from markdown blocks (fallback)
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        pass

            if not data:
                # 3. Try partial JSON extraction
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        pass

            if not data:
                # Fallback: treat entire response as single markdown file
                return self._save_simple_markdown(response_text, output_dir, base_name)
            
            # Now process the data
            if 'files' in data:
                # Ensure output directory exists
                logger.info(f"Creating output directory: {output_dir}")
                os.makedirs(output_dir, exist_ok=True)
                logger.info(f"Output directory created/verified: {output_dir}")
                
                for file_info in data['files']:
                    filename = file_info.get('filename', 'output.md')
                    content = file_info.get('content', '')
                    
                    if not content:
                         continue

                    logger.info(f"Processing file from AI response: {filename}")
                    
                    # Ensure .md extension
                    if not filename.endswith('.md'):
                        filename += '.md'
                    
                    file_path = os.path.join(output_dir, filename)
                    logger.info(f"Full file path to create: {file_path}")
                    
                    # Verify directory exists before writing
                    file_dir = os.path.dirname(file_path)
                    if not os.path.exists(file_dir):
                        logger.warning(f"Directory does not exist, creating: {file_dir}")
                        os.makedirs(file_dir, exist_ok=True)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    created_files.append(file_path)
                    logger.info(f"Created file: {filename}")
            else:
                logger.warning(f"JSON parsed successfully but 'files' key missing. Keys found: {list(data.keys())}")
                # Fallback: try to save the raw text or the JSON dump as markdown
                return self._save_simple_markdown(response_text, output_dir, base_name)
            
            return created_files
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Could not parse JSON response: {e}. Using simple markdown save.")
            return self._save_simple_markdown(response_text, output_dir, base_name)
    
    def _save_simple_markdown(self, content: str, output_dir: str, base_name: str) -> List[str]:
        """
        Save response as a simple markdown file
        
        Args:
            content: Markdown content
            output_dir: Output directory
            base_name: Base filename
            
        Returns:
            List with single file path
        """
        # Clean up markdown code blocks if present
        import re
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Remove markdown code block wrapper if exists
        content = re.sub(r'^```markdown\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        
        filename = f"{base_name}.md"
        file_path = os.path.join(output_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Created simple markdown file: {filename}")
        return [file_path]
    
    def convert(self, input_path: str, output_dir: str) -> tuple[List[str], List[Dict]]:
        """
        Convert files in a directory or single file
        
        Args:
            input_path: Path to file or directory
            output_dir: Output directory
            
        Returns:
            Tuple containing:
            - List of all created files
            - List of error details [{'file': filename, 'error': msg}]
        """
        all_files = []
        errors = []
        
        if os.path.isfile(input_path):
            # Single file
            files_to_process = [input_path]
        else:
            # Directory
            files_to_process = []
            for ext in ['*.xlsx', '*.xls', '*.csv']:
                files_to_process.extend(Path(input_path).glob(ext))
        
        for file_path in files_to_process:
            # convert_file now handles exceptions internally and returns (files, errors)
            # but we wrap in try/except just in case of unexpected crashes
            try:
                sheet_files, sheet_errors = self.convert_file(str(file_path), output_dir)
                all_files.extend(sheet_files)
                errors.extend(sheet_errors)
            except Exception as e:
                # Fallback for unexpected errors outside convert_file logic
                logger.error(f"Unexpected error in convert loop for {file_path}: {e}")
                errors.append({
                    'file': Path(file_path).name,
                    'error': f"Lỗi không xác định: {str(e)}"
                })
        
        return all_files, errors
