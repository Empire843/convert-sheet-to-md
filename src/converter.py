"""
Main Converter Script
Điều phối việc chuyển đổi Excel/CSV sang Markdown
"""
import os
import sys
import logging
import argparse
from pathlib import Path
from typing import List

from src.excel_processor import ExcelProcessor
from src.csv_processor import CSVProcessor
from src.markdown_generator import MarkdownGenerator
from src.image_extractor import ImageExtractor

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Converter:
    """Class chính để điều phối quá trình chuyển đổi"""
    
    def __init__(self, input_path: str, output_dir: str = "/app/output"):
        """
        Khởi tạo Converter
        
        Args:
            input_path: Đường dẫn đến file hoặc thư mục đầu vào
            output_dir: Thư mục lưu kết quả
        """
        self.input_path = input_path
        self.output_dir = output_dir
        
        # Tạo thư mục output nếu chưa tồn tại
        os.makedirs(output_dir, exist_ok=True)
    
    def get_input_files(self) -> List[str]:
        """
        Lấy danh sách file cần xử lý
        
        Returns:
            List đường dẫn các file
        """
        supported_extensions = ['.xlsx', '.xls', '.csv']
        files = []
        
        if os.path.isfile(self.input_path):
            # Nếu là file đơn lẻ
            if any(self.input_path.lower().endswith(ext) for ext in supported_extensions):
                files.append(self.input_path)
        elif os.path.isdir(self.input_path):
            # Nếu là thư mục, lấy tất cả file hỗ trợ
            for root, _, filenames in os.walk(self.input_path):
                for filename in filenames:
                    if any(filename.lower().endswith(ext) for ext in supported_extensions):
                        files.append(os.path.join(root, filename))
        
        return files
    
    def convert_excel(self, file_path: str) -> List[str]:
        """
        Chuyển đổi file Excel sang Markdown
        
        Args:
            file_path: Đường dẫn đến file Excel
            
        Returns:
            List các file Markdown đã tạo
        """
        logger.info(f"Bắt đầu xử lý file Excel: {file_path}")
        
        # Lấy tên file gốc (không có extension)
        base_name = Path(file_path).stem
        
        # Khởi tạo processors
        excel_processor = ExcelProcessor(file_path)
        
        # Tạo thư mục con cho file này (để chứa ảnh)
        file_output_dir = os.path.join(self.output_dir, base_name)
        os.makedirs(file_output_dir, exist_ok=True)
        
        # Trích xuất ảnh
        image_extractor = ImageExtractor(file_path, file_output_dir)
        images_by_sheet = image_extractor.extract_all_images()
        
        # Đọc tất cả các sheet
        all_sheets = excel_processor.read_all_sheets()
        
        created_files = []
        
        # Xử lý từng sheet
        for sheet_name, df in all_sheets.items():
            logger.info(f"Đang xử lý sheet: {sheet_name}")
            
            # Tạo nội dung Markdown
            md_content = MarkdownGenerator.dataframe_to_markdown(df, sheet_name)
            
            # Thêm ảnh nếu có
            if sheet_name in images_by_sheet:
                for image_info in images_by_sheet[sheet_name]:
                    md_content = MarkdownGenerator.add_image_reference(
                        md_content,
                        image_info['path'],
                        image_info['alt']
                    )
            
            # Tạo tên file output
            safe_sheet_name = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in sheet_name)
            output_filename = f"{base_name}_{safe_sheet_name}.md"
            output_path = os.path.join(file_output_dir, output_filename)
            
            # Lưu file
            MarkdownGenerator.save_to_file(md_content, output_path)
            created_files.append(output_path)
            
            logger.info(f"Đã tạo file: {output_path}")
        
        return created_files
    
    def convert_csv(self, file_path: str) -> List[str]:
        """
        Chuyển đổi file CSV sang Markdown
        
        Args:
            file_path: Đường dẫn đến file CSV
            
        Returns:
            List các file Markdown đã tạo
        """
        logger.info(f"Bắt đầu xử lý file CSV: {file_path}")
        
        # Lấy tên file gốc
        base_name = Path(file_path).stem
        
        # Đọc CSV
        csv_processor = CSVProcessor(file_path)
        df = csv_processor.get_data()
        
        # Tạo Markdown
        md_content = MarkdownGenerator.dataframe_to_markdown(df, base_name)
        
        # Tạo file output
        output_filename = f"{base_name}.md"
        output_path = os.path.join(self.output_dir, output_filename)
        
        # Lưu file
        MarkdownGenerator.save_to_file(md_content, output_path)
        
        logger.info(f"Đã tạo file: {output_path}")
        
        return [output_path]
    
    def convert(self) -> None:
        """
        Thực hiện chuyển đổi tất cả các file
        """
        files = self.get_input_files()
        
        if not files:
            logger.warning("Không tìm thấy file nào để xử lý!")
            return
        
        logger.info(f"Tìm thấy {len(files)} file cần xử lý")
        
        total_created = 0
        
        for file_path in files:
            try:
                if file_path.lower().endswith('.csv'):
                    created = self.convert_csv(file_path)
                else:
                    created = self.convert_excel(file_path)
                
                total_created += len(created)
                
            except Exception as e:
                logger.error(f"Lỗi khi xử lý file {file_path}: {str(e)}")
                continue
        
        logger.info(f"Hoàn thành! Đã tạo {total_created} file Markdown")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Chuyển đổi Excel/CSV sang Markdown',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  # Chuyển đổi một file
  python converter.py /app/input/data.xlsx
  
  # Chuyển đổi tất cả file trong thư mục
  python converter.py /app/input/
  
  # Chỉ định thư mục output
  python converter.py /app/input/data.xlsx -o /app/output/custom/
        """
    )
    
    parser.add_argument(
        'input',
        help='Đường dẫn đến file hoặc thư mục đầu vào'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='/app/output',
        help='Thư mục lưu kết quả (mặc định: /app/output)'
    )
    
    args = parser.parse_args()
    
    # Kiểm tra input có tồn tại không
    if not os.path.exists(args.input):
        logger.error(f"Đường dẫn không tồn tại: {args.input}")
        sys.exit(1)
    
    # Thực hiện chuyển đổi
    converter = Converter(args.input, args.output)
    converter.convert()


if __name__ == "__main__":
    main()
