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
    
    BATCH_SYSTEM_PROMPT = """You are a document-structure transformation engine.
Your goal is to preserve ALL content while improving semantic clarity.

You are processing MULTIPLE SHEETS in a SINGLE BATCH.

ABSOLUTE RULES:
- Do NOT remove, summarize, or rewrite content.
- You MAY change layout and structure for readability.
- Content fidelity is mandatory; layout fidelity is optional.
- Each sheet is clearly marked with "=== SHEET: sheet_name ==="
- You MUST create a SEPARATE FILE for EACH SHEET
- Do NOT mix content between different sheets
- Preserve the sheet name in the output filename

CONTENT HANDLING:
- Preserve all text exactly as written (including Japanese).
- Preserve the original logical order of content within each sheet.
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
- Ensure every textual element from EVERY sheet exists in the output.
- No content may disappear due to layout transformation.
- Each sheet must have its own markdown file in the output.

OUTPUT FORMAT (CRITICAL):
- Return a JSON object with a single key "files".
- "files" MUST be a list with ONE OBJECT PER SHEET.
- Each object must contain:
  - "filename": The sheet name with .md extension (e.g., "SheetName.md")
  - "content": The full markdown content for that sheet only

Example for 3 sheets:
{
  "files": [
    {
      "filename": "Sheet1.md",
      "content": "# Sheet1 Title\n\nSheet1 content..."
    },
    {
      "filename": "Sheet2.md",
      "content": "# Sheet2 Title\n\nSheet2 content..."
    },
    {
      "filename": "Sheet3.md",
      "content": "# Sheet3 Title\n\nSheet3 content..."
    }
  ]
}

- Valid JSON only. Do not include explanation text outside the JSON.
- The number of files in your response MUST match the number of sheets in the input.
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
        self.initial_retry_delay = 10  # Increased to 10s for better rate limit handling
        
        # Batch processing configuration
        self.max_tokens_per_batch = 800000  # Gemini 2.0 Flash max context (leave 20% buffer)
        self.avg_chars_per_token = 4  # Rough estimation for mixed content
        self.min_batch_size = 1
        self.max_batch_size = 20  # Maximum sheets per batch
        self.batch_delay = 10  # Seconds between batches
    


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
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate number of tokens in text
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        # Simple estimation: chars / avg_chars_per_token
        return len(text) // self.avg_chars_per_token
    
    def _calculate_batch_size(self, sheets_data: List[tuple]) -> List[List[int]]:
        """
        Calculate optimal batch groupings for sheets based on content size
        
        Args:
            sheets_data: List of (sheet_name, dataframe) tuples
            
        Returns:
            List of batches, where each batch is a list of sheet indices
        """
        batches = []
        current_batch = []
        current_tokens = 0
        
        # Estimate system prompt tokens
        system_prompt_tokens = self._estimate_tokens(self.BATCH_SYSTEM_PROMPT)
        if self.additional_prompt:
            system_prompt_tokens += self._estimate_tokens(self.additional_prompt)
        
        for idx, (sheet_name, df) in enumerate(sheets_data):
            # Estimate tokens for this sheet
            sheet_str = f"=== SHEET: {sheet_name} ===\\n"
            sheet_str += df.to_string(index=False)
            sheet_tokens = self._estimate_tokens(sheet_str)
            
            # Check if adding this sheet exceeds limits
            potential_total = system_prompt_tokens + current_tokens + sheet_tokens
            
            if potential_total > self.max_tokens_per_batch and current_batch:
                # Current batch is full, start new batch
                batches.append(current_batch)
                current_batch = [idx]
                current_tokens = sheet_tokens
            elif len(current_batch) >= self.max_batch_size:
                # Reached max sheets per batch
                batches.append(current_batch)
                current_batch = [idx]
                current_tokens = sheet_tokens
            else:
                # Add to current batch
                current_batch.append(idx)
                current_tokens += sheet_tokens
        
        # Add remaining batch
        if current_batch:
            batches.append(current_batch)
        
        logger.info(f"Calculated {len(batches)} batches for {len(sheets_data)} sheets")
        for i, batch in enumerate(batches):
            logger.info(f"  Batch {i+1}: {len(batch)} sheets (indices: {batch})")
        
        return batches
    
    def _merge_sheets_for_batch(self, sheets_data: List[tuple], batch_indices: List[int]) -> str:
        """
        Merge multiple sheets into a single content string for batch processing
        
        Args:
            sheets_data: List of all (sheet_name, dataframe) tuples
            batch_indices: Indices of sheets to include in this batch
            
        Returns:
            Combined content string with clear sheet separators
        """
        combined = f"Processing {len(batch_indices)} sheets in this batch.\\n\\n"
        
        for idx in batch_indices:
            sheet_name, df = sheets_data[idx]
            
            # Truncate large sheets
            if len(df) > 5000:
                logger.warning(f"Sheet '{sheet_name}' has {len(df)} rows, truncating to 5000")
                df = df.head(5000)
            
            # Add clear separator and sheet marker
            combined += f"{'='*80}\\n"
            combined += f"=== SHEET: {sheet_name} ===\\n"
            combined += f"{'='*80}\\n\\n"
            
            # Add sheet content
            combined += df.to_string(index=False)
            combined += "\\n\\n"
        
        combined += f"{'='*80}\\n"
        combined += f"END OF BATCH - Total sheets: {len(batch_indices)}\\n"
        combined += f"{'='*80}\\n"
        
        return combined


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
            
            # Handler for Excel files (Batch Processing)
            if file_extension in ['.xlsx', '.xls']:
                import pandas as pd
                try:
                    excel_file = pd.ExcelFile(file_path)
                    sheet_names = excel_file.sheet_names
                    logger.info(f"Excel file has {len(sheet_names)} sheets: {sheet_names}")
                    
                    # Read all sheets into memory
                    sheets_data = []
                    for sheet_name in sheet_names:
                        df = pd.read_excel(file_path, sheet_name=sheet_name)
                        sheets_data.append((sheet_name, df))
                    
                    # Calculate optimal batches
                    batches = self._calculate_batch_size(sheets_data)
                    
                    # Process each batch
                    for batch_idx, batch_indices in enumerate(batches):
                        try:
                            # Add delay between batches (skip for first batch)
                            if batch_idx > 0:
                                logger.info(f"Waiting {self.batch_delay}s before processing next batch...")
                                time.sleep(self.batch_delay)
                            
                            # Get sheet names for this batch
                            batch_sheet_names = [sheets_data[i][0] for i in batch_indices]
                            logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} with {len(batch_indices)} sheets: {batch_sheet_names}")
                            
                            # Merge sheets for batch processing
                            batch_content = self._merge_sheets_for_batch(sheets_data, batch_indices)
                            
                            # Process batch
                            batch_files = self._generate_and_save_batch(
                                batch_content,
                                output_dir,
                                base_name,
                                batch_sheet_names,
                                batch_indices
                            )
                            created_files.extend(batch_files)
                            logger.info(f"Batch {batch_idx + 1} completed successfully. Created {len(batch_files)} files.")
                            
                        except Exception as batch_error:
                            error_msg = str(batch_error)
                            logger.error(f"Batch {batch_idx + 1} failed: {error_msg}")
                            
                            # FALLBACK: Process sheets in this batch individually
                            logger.info(f"Falling back to individual sheet processing for batch {batch_idx + 1}")
                            
                            for sheet_idx in batch_indices:
                                sheet_name, df = sheets_data[sheet_idx]
                                try:
                                    # Add delay between individual sheets in fallback mode
                                    if sheet_idx != batch_indices[0]:
                                        time.sleep(5)
                                    
                                    logger.info(f"Processing sheet individually: {sheet_name}")
                                    
                                    # Truncate if needed
                                    if len(df) > 5000:
                                        logger.warning(f"Sheet {sheet_name} has {len(df)} rows, truncating to 5000")
                                        df = df.head(5000)
                                    
                                    content_str = f"### Sheet: {sheet_name}\\n"
                                    content_str += df.to_string(index=False)
                                    
                                    sheet_files = self._generate_and_save(
                                        content_str,
                                        output_dir,
                                        f"{base_name}_{sheet_name}",
                                        is_single_sheet=True
                                    )
                                    created_files.extend(sheet_files)
                                    logger.info(f"Individual sheet '{sheet_name}' processed successfully")
                                    
                                except Exception as sheet_error:
                                    sheet_error_msg = str(sheet_error)
                                    logger.error(f"Error converting sheet '{sheet_name}': {sheet_error_msg}")
                                    errors.append({
                                        'file': f"{file_name} - {sheet_name}",
                                        'error': self._friendly_error_message(sheet_error_msg)
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

    def _generate_and_save_batch(
        self, 
        batch_content: str, 
        output_dir: str, 
        base_name: str,
        sheet_names: List[str],
        batch_indices: List[int]
    ) -> List[str]:
        """
        Generate and save batch of sheets using Gemini AI
        
        Args:
            batch_content: Combined content from multiple sheets
            output_dir: Output directory
            base_name: Base filename
            sheet_names: List of sheet names in this batch
            batch_indices: Indices of sheets in this batch
            
        Returns:
            List of created file paths
        """
        # Construct prompt with batch system prompt
        final_prompt = f"{self.BATCH_SYSTEM_PROMPT}\n"
        if self.additional_prompt:
            final_prompt += f"\nADDITIONAL INSTRUCTIONS:\n{self.additional_prompt}\n"
        
        final_prompt += f"\nHere is the batch data containing {len(sheet_names)} sheets:\n\n{batch_content}"
        
        # Retry with exponential backoff
        response = None
        last_error = None
        
        import re
        import time
        
        for attempt in range(self.max_retries):
            try:
                # Delay handling
                if attempt > 0:
                    delay = self.initial_retry_delay * (2 ** (attempt - 1))
                    logger.info(f"Retry attempt {attempt + 1}/{self.max_retries}. Wait: {delay}s")
                    time.sleep(delay)
                
                # Call Gemini API with JSON mode
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
                    # Smart Rate Limiting
                    wait_match = re.search(r'retry in (\d+(\.\d+)?)s', str_error)
                    if wait_match:
                        wait_time = float(wait_match.group(1))
                        final_wait = wait_time + 1.5
                        logger.warning(f"Rate limited. Sleeping for {final_wait}s...")
                        time.sleep(final_wait)
                        continue
                    
                    if 'rate limit exceeded' in str_error.lower() and attempt == self.max_retries - 1:
                        pass
                    else:
                        continue
                
                if attempt == self.max_retries - 1:
                    pass
                else:
                    if '429' not in str_error and 'quota' not in str_error.lower():
                        raise retry_error
        
        if response is None:
            raise last_error or Exception("Failed to get response from AI (Unknown Error)")
        
        # Extract response text
        try:
            response_text = response.text
        except:
            parts = []
            if hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'text'):
                                parts.append(part.text)
            response_text = '\n'.join(parts)
        
        # Parse and save the batch response
        return self._parse_and_save_batch_response(
            response_text, 
            output_dir, 
            base_name, 
            sheet_names,
            batch_indices
        )
    
    def _parse_and_save_batch_response(
        self, 
        response_text: str, 
        output_dir: str, 
        base_name: str,
        expected_sheet_names: List[str],
        batch_indices: List[int]
    ) -> List[str]:
        """
        Parse batch AI response and save individual markdown files for each sheet
        
        Args:
            response_text: Response from Gemini
            output_dir: Output directory
            base_name: Base filename
            expected_sheet_names: Expected sheet names in response
            batch_indices: Indices of sheets in this batch
            
        Returns:
            List of created file paths
        """
        created_files = []
        
        try:
            import json
            import re
            
            data = None
            # Try direct JSON parse
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                pass
            
            if not data:
                # Extract JSON from markdown blocks
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        pass
            
            if not data:
                # Try partial JSON extraction
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        pass
            
            if not data or 'files' not in data:
                # Fallback: save as single file
                logger.warning("Could not parse batch response as JSON. Saving as single file.")
                return self._save_simple_markdown(response_text, output_dir, f"{base_name}_batch_{batch_indices[0]}")
            
            # Process files from batch response
            os.makedirs(output_dir, exist_ok=True)
            
            files_data = data['files']
            logger.info(f"Batch response contains {len(files_data)} files (expected {len(expected_sheet_names)})")
            
            # Validate we got the right number of files
            if len(files_data) != len(expected_sheet_names):
                logger.warning(f"Mismatch: expected {len(expected_sheet_names)} files, got {len(files_data)}")
            
            for idx, file_info in enumerate(files_data):
                filename = file_info.get('filename', f'sheet_{idx}.md')
                content = file_info.get('content', '')
                
                if not content:
                    logger.warning(f"Empty content for file: {filename}")
                    continue
                
                # Ensure .md extension
                if not filename.endswith('.md'):
                    filename += '.md'
                
                # Prepend base_name if not already there
                if not filename.startswith(base_name):
                    filename = f"{base_name}_{filename}"
                
                file_path = os.path.join(output_dir, filename)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                created_files.append(file_path)
                logger.info(f"Created file from batch: {filename}")
            
            return created_files
            
        except Exception as e:
            logger.error(f"Error parsing batch response: {e}")
            # Fallback to simple save
            return self._save_simple_markdown(response_text, output_dir, f"{base_name}_batch_{batch_indices[0]}")

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
