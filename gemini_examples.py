"""
VÍ DỤ TÍCH HỢP GEMINI API VÀO ỨNG DỤNG
======================================

File này chứa các ví dụ về cách sử dụng Gemini API
cho các tác vụ khác nhau trong ứng dụng RPA.

Sử dụng: Copy các hàm này vào app_ui.py và tùy chỉnh theo nhu cầu.
"""

import google.generativeai as genai
from typing import Optional, Dict, List
import pandas as pd
from PIL import Image
import json


class GeminiHelper:
    """
    Class helper để làm việc với Gemini API
    """
    
    def __init__(self, api_key: str):
        """
        Khởi tạo Gemini Helper
        
        Args:
            api_key: Gemini API Key
        """
        genai.configure(api_key=api_key)
        self.text_model = genai.GenerativeModel('gemini-pro')
        self.vision_model = genai.GenerativeModel('gemini-pro-vision')
    
    def test_connection(self) -> bool:
        """
        Test kết nối với Gemini API
        
        Returns:
            True nếu kết nối thành công, False nếu thất bại
        """
        try:
            response = self.text_model.generate_content("Xin chào")
            return bool(response and response.text)
        except Exception as e:
            print(f"Lỗi kết nối: {e}")
            return False
    
    # ==========================================
    # 1. CHAT VÀ HỎI ĐÁP CƠ BẢN
    # ==========================================
    
    def chat(self, message: str) -> Optional[str]:
        """
        Chat đơn giản với Gemini
        
        Args:
            message: Tin nhắn cần gửi
            
        Returns:
            Phản hồi từ Gemini hoặc None nếu lỗi
        """
        try:
            response = self.text_model.generate_content(message)
            return response.text
        except Exception as e:
            print(f"Lỗi chat: {e}")
            return None
    
    def chat_with_context(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        Chat với ngữ cảnh (conversation history)
        
        Args:
            messages: Danh sách tin nhắn [{"role": "user", "content": "..."}, ...]
            
        Returns:
            Phản hồi từ Gemini
        """
        try:
            # Tạo chat session
            chat = self.text_model.start_chat(history=[])
            
            # Gửi từng tin nhắn
            for msg in messages:
                if msg["role"] == "user":
                    response = chat.send_message(msg["content"])
            
            return response.text if response else None
        except Exception as e:
            print(f"Lỗi chat với context: {e}")
            return None
    
    # ==========================================
    # 2. XỬ LÝ VÀ PHÂN TÍCH DỮ LIỆU EXCEL
    # ==========================================
    
    def analyze_excel_data(self, excel_path: str, max_rows: int = 20) -> Optional[str]:
        """
        Phân tích dữ liệu từ file Excel
        
        Args:
            excel_path: Đường dẫn file Excel
            max_rows: Số dòng tối đa để phân tích
            
        Returns:
            Kết quả phân tích từ Gemini
        """
        try:
            # Đọc Excel
            df = pd.read_excel(excel_path)
            
            # Tạo summary
            summary = f"""
            Thông tin file Excel:
            - Số dòng: {len(df)}
            - Số cột: {len(df.columns)}
            - Tên các cột: {', '.join(df.columns.tolist())}
            
            Dữ liệu mẫu ({max_rows} dòng đầu):
            {df.head(max_rows).to_string()}
            
            Thống kê cơ bản:
            {df.describe().to_string()}
            """
            
            prompt = f"""
            Phân tích dữ liệu Excel sau và đưa ra nhận xét:
            
            {summary}
            
            Hãy cung cấp:
            1. Tóm tắt nội dung dữ liệu
            2. Các vấn đề tiềm ẩn (nếu có)
            3. Đề xuất cải thiện
            """
            
            response = self.text_model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Lỗi phân tích Excel: {e}")
            return None
    
    def validate_excel_data(self, excel_path: str, rules: Dict[str, str]) -> Optional[str]:
        """
        Kiểm tra tính hợp lệ của dữ liệu Excel theo quy tắc
        
        Args:
            excel_path: Đường dẫn file Excel
            rules: Dictionary chứa quy tắc kiểm tra
                   Ví dụ: {"cccd": "12 chữ số", "phone": "10 chữ số"}
            
        Returns:
            Kết quả kiểm tra từ Gemini
        """
        try:
            df = pd.read_excel(excel_path)
            
            # Lấy mẫu dữ liệu
            sample_data = df.head(10).to_dict('records')
            
            prompt = f"""
            Kiểm tra dữ liệu sau theo các quy tắc:
            
            Quy tắc:
            {json.dumps(rules, ensure_ascii=False, indent=2)}
            
            Dữ liệu mẫu:
            {json.dumps(sample_data, ensure_ascii=False, indent=2)}
            
            Hãy:
            1. Kiểm tra từng bản ghi có tuân thủ quy tắc không
            2. Liệt kê các lỗi tìm thấy
            3. Đưa ra đề xuất sửa lỗi
            """
            
            response = self.text_model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Lỗi validate Excel: {e}")
            return None
    
    def generate_excel_summary(self, excel_path: str) -> Optional[str]:
        """
        Tạo báo cáo tóm tắt từ file Excel
        
        Args:
            excel_path: Đường dẫn file Excel
            
        Returns:
            Báo cáo tóm tắt
        """
        try:
            df = pd.read_excel(excel_path)
            
            prompt = f"""
            Tạo báo cáo tóm tắt cho dữ liệu sau:
            
            Tổng số bản ghi: {len(df)}
            Các cột: {', '.join(df.columns.tolist())}
            
            Dữ liệu mẫu:
            {df.head(5).to_string()}
            
            Hãy viết một báo cáo ngắn gọn, dễ hiểu về:
            1. Nội dung chính của dữ liệu
            2. Các con số quan trọng
            3. Xu hướng (nếu có)
            """
            
            response = self.text_model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Lỗi tạo summary: {e}")
            return None
    
    # ==========================================
    # 3. XỬ LÝ VĂN BẢN VÀ HỢP ĐỒNG
    # ==========================================
    
    def extract_contract_info(self, contract_text: str) -> Optional[Dict]:
        """
        Trích xuất thông tin từ văn bản hợp đồng
        
        Args:
            contract_text: Nội dung hợp đồng (text)
            
        Returns:
            Dictionary chứa thông tin đã trích xuất
        """
        try:
            prompt = f"""
            Trích xuất thông tin từ hợp đồng sau:
            
            {contract_text}
            
            Hãy trích xuất và trả về JSON với các trường:
            - contract_id: Số hợp đồng
            - customer_name: Tên khách hàng
            - cccd: Số CCCD
            - phone: Số điện thoại
            - address: Địa chỉ
            - amount: Số tiền
            - date: Ngày ký
            
            Chỉ trả về JSON, không giải thích thêm.
            """
            
            response = self.text_model.generate_content(prompt)
            
            # Parse JSON từ response
            result = json.loads(response.text)
            return result
            
        except Exception as e:
            print(f"Lỗi trích xuất hợp đồng: {e}")
            return None
    
    def validate_contract(self, contract_data: Dict) -> Optional[str]:
        """
        Kiểm tra tính hợp lệ của thông tin hợp đồng
        
        Args:
            contract_data: Dictionary chứa thông tin hợp đồng
            
        Returns:
            Kết quả kiểm tra
        """
        try:
            prompt = f"""
            Kiểm tra thông tin hợp đồng sau:
            
            {json.dumps(contract_data, ensure_ascii=False, indent=2)}
            
            Hãy kiểm tra:
            1. Số hợp đồng có đúng định dạng không?
            2. Số CCCD có hợp lệ (12 chữ số) không?
            3. Số điện thoại có hợp lệ (10 chữ số) không?
            4. Các trường bắt buộc có đầy đủ không?
            5. Có dấu hiệu bất thường nào không?
            
            Trả về kết quả kiểm tra chi tiết.
            """
            
            response = self.text_model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Lỗi validate hợp đồng: {e}")
            return None
    
    # ==========================================
    # 4. XỬ LÝ HÌNH ẢNH VÀ PDF
    # ==========================================
    
    def analyze_image(self, image_path: str, question: str = None) -> Optional[str]:
        """
        Phân tích hình ảnh bằng Gemini Vision
        
        Args:
            image_path: Đường dẫn file hình ảnh
            question: Câu hỏi về hình ảnh (optional)
            
        Returns:
            Mô tả hoặc câu trả lời từ Gemini
        """
        try:
            img = Image.open(image_path)
            
            if question:
                prompt = question
            else:
                prompt = "Mô tả chi tiết nội dung trong hình ảnh này"
            
            response = self.vision_model.generate_content([prompt, img])
            return response.text
            
        except Exception as e:
            print(f"Lỗi phân tích hình ảnh: {e}")
            return None
    
    def extract_text_from_image(self, image_path: str) -> Optional[str]:
        """
        Trích xuất văn bản từ hình ảnh (OCR)
        
        Args:
            image_path: Đường dẫn file hình ảnh
            
        Returns:
            Văn bản đã trích xuất
        """
        try:
            img = Image.open(image_path)
            
            prompt = """
            Trích xuất TẤT CẢ văn bản có trong hình ảnh này.
            Giữ nguyên định dạng và cấu trúc.
            Chỉ trả về văn bản, không giải thích thêm.
            """
            
            response = self.vision_model.generate_content([prompt, img])
            return response.text
            
        except Exception as e:
            print(f"Lỗi OCR: {e}")
            return None
    
    # ==========================================
    # 5. TẠO NỘI DUNG TỰ ĐỘNG
    # ==========================================
    
    def generate_zalo_message(self, customer_data: Dict, template: str = None) -> Optional[str]:
        """
        Tạo tin nhắn Zalo tự động dựa trên thông tin khách hàng
        
        Args:
            customer_data: Thông tin khách hàng
            template: Template mẫu (optional)
            
        Returns:
            Tin nhắn đã tạo
        """
        try:
            if template:
                prompt = f"""
                Tạo tin nhắn Zalo dựa trên template và thông tin khách hàng:
                
                Template: {template}
                
                Thông tin khách hàng:
                {json.dumps(customer_data, ensure_ascii=False, indent=2)}
                
                Hãy thay thế các biến trong template bằng thông tin thực tế.
                """
            else:
                prompt = f"""
                Tạo tin nhắn Zalo chuyên nghiệp để liên hệ khách hàng:
                
                Thông tin khách hàng:
                {json.dumps(customer_data, ensure_ascii=False, indent=2)}
                
                Tin nhắn cần:
                - Lịch sự, chuyên nghiệp
                - Ngắn gọn, dễ hiểu
                - Có thông tin hợp đồng
                """
            
            response = self.text_model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Lỗi tạo tin nhắn: {e}")
            return None


# ==========================================
# VÍ DỤ SỬ DỤNG
# ==========================================

if __name__ == "__main__":
    # Khởi tạo
    API_KEY = "YOUR_API_KEY_HERE"
    gemini = GeminiHelper(API_KEY)
    
    # Test kết nối
    if gemini.test_connection():
        print("✅ Kết nối thành công!")
    else:
        print("❌ Kết nối thất bại!")
        exit()
    
    # Ví dụ 1: Chat đơn giản
    response = gemini.chat("Giải thích RPA là gì?")
    print(f"\n📝 Chat:\n{response}")
    
    # Ví dụ 2: Phân tích Excel
    # response = gemini.analyze_excel_data("data.xlsx")
    # print(f"\n📊 Phân tích Excel:\n{response}")
    
    # Ví dụ 3: Validate hợp đồng
    contract = {
        "contract_id": "HD123456",
        "customer_name": "Nguyễn Văn A",
        "cccd": "001234567890",
        "phone": "0912345678"
    }
    response = gemini.validate_contract(contract)
    print(f"\n✅ Kiểm tra hợp đồng:\n{response}")
    
    # Ví dụ 4: Tạo tin nhắn Zalo
    customer = {
        "name": "Nguyễn Văn A",
        "contract_id": "HD123456",
        "phone": "0912345678"
    }
    message = gemini.generate_zalo_message(customer)
    print(f"\n💬 Tin nhắn Zalo:\n{message}")

