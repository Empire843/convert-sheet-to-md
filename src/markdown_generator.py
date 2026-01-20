"""
Module xử lý Markdown
Chuyển đổi DataFrame sang định dạng Markdown table
"""
import pandas as pd
from typing import List, Optional


class MarkdownGenerator:
    """Class để tạo nội dung Markdown từ dữ liệu"""
    
    @staticmethod
    def escape_markdown_chars(text: str) -> str:
        """
        Escape các ký tự đặc biệt trong Markdown
        
        Args:
            text: Chuỗi cần escape
            
        Returns:
            Chuỗi đã được escape
        """
        if not isinstance(text, str):
            return str(text)
        
        # Escape pipe character trong table
        text = text.replace('|', '\\|')
        # Escape newline
        text = text.replace('\n', '<br>')
        return text
    
    @staticmethod
    def dataframe_to_markdown(df: pd.DataFrame, sheet_name: Optional[str] = None) -> str:
        """
        Chuyển DataFrame sang Markdown table
        
        Args:
            df: DataFrame cần chuyển đổi
            sheet_name: Tên sheet (dùng làm tiêu đề)
            
        Returns:
            Chuỗi Markdown
        """
        lines = []
        
        # Thêm tiêu đề nếu có
        if sheet_name:
            lines.append(f"# {sheet_name}\n")
        
        # Nếu DataFrame rỗng
        if df.empty:
            lines.append("_Sheet này không có dữ liệu_\n")
            return '\n'.join(lines)
        
        # Xử lý header
        headers = [MarkdownGenerator.escape_markdown_chars(str(col)) for col in df.columns]
        lines.append('| ' + ' | '.join(headers) + ' |')
        
        # Thêm separator
        lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        
        # Thêm data rows
        for _, row in df.iterrows():
            row_data = [MarkdownGenerator.escape_markdown_chars(str(val)) for val in row]
            lines.append('| ' + ' | '.join(row_data) + ' |')
        
        return '\n'.join(lines)
    
    @staticmethod
    def add_image_reference(markdown_content: str, image_path: str, alt_text: str = "Image") -> str:
        """
        Thêm link ảnh vào Markdown
        
        Args:
            markdown_content: Nội dung Markdown hiện tại
            image_path: Đường dẫn đến file ảnh
            alt_text: Text thay thế cho ảnh
            
        Returns:
            Nội dung Markdown đã thêm link ảnh
        """
        image_md = f"\n\n![{alt_text}]({image_path})\n"
        return markdown_content + image_md
    
    @staticmethod
    def save_to_file(content: str, output_path: str) -> None:
        """
        Lưu nội dung Markdown vào file
        
        Args:
            content: Nội dung Markdown
            output_path: Đường dẫn file đầu ra
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
