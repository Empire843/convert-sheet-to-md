"""
Module xử lý file CSV
Đọc và parse file CSV thành DataFrame
"""
import pandas as pd
from typing import Optional
import chardet


class CSVProcessor:
    """Class để xử lý file CSV"""
    
    def __init__(self, file_path: str):
        """
        Khởi tạo CSVProcessor
        
        Args:
            file_path: Đường dẫn đến file CSV
        """
        self.file_path = file_path
        self.encoding = self._detect_encoding()
    
    def _detect_encoding(self) -> str:
        """
        Tự động phát hiện encoding của file CSV
        
        Returns:
            Encoding string
        """
        try:
            with open(self.file_path, 'rb') as f:
                raw_data = f.read(10000)  # Đọc 10KB đầu tiên
                result = chardet.detect(raw_data)
                return result['encoding'] or 'utf-8'
        except Exception:
            return 'utf-8'
    
    def read_csv(self) -> pd.DataFrame:
        """
        Đọc file CSV thành DataFrame
        
        Returns:
            DataFrame chứa dữ liệu CSV
            
        Raises:
            Exception: Nếu không thể đọc file
        """
        try:
            # Thử đọc với encoding đã detect
            df = pd.read_csv(self.file_path, encoding=self.encoding)
            return df
        except UnicodeDecodeError:
            # Fallback sang UTF-8 nếu detect sai
            try:
                df = pd.read_csv(self.file_path, encoding='utf-8')
                return df
            except UnicodeDecodeError:
                # Fallback cuối cùng sang Latin-1
                df = pd.read_csv(self.file_path, encoding='latin-1')
                return df
        except Exception as e:
            raise Exception(f"Lỗi khi đọc file CSV: {str(e)}")
    
    def get_data(self) -> pd.DataFrame:
        """
        Lấy dữ liệu từ file CSV
        
        Returns:
            DataFrame chứa dữ liệu
        """
        return self.read_csv()
