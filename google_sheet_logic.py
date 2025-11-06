"""
Module xử lý kết nối và thao tác với Google Sheets API
"""

import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Phạm vi quyền truy cập Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

class GoogleSheetManager:
    """Quản lý kết nối và đọc dữ liệu từ Google Sheets"""
    
    def __init__(self, credentials_file='credentials.json', token_file='app_data/token.json'):
        """
        Khởi tạo Google Sheet Manager
        
        Args:
            credentials_file: Đường dẫn đến file credentials.json từ Google Cloud Console
            token_file: Đường dẫn đến file lưu token xác thực
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.creds = None
        self.service = None
        
    def authenticate(self):
        """
        Xác thực với Google Sheets API
        
        Returns:
            bool: True nếu xác thực thành công, False nếu thất bại
        """
        try:
            # Kiểm tra xem đã có token chưa
            if os.path.exists(self.token_file):
                self.creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            
            # Nếu không có credentials hợp lệ, yêu cầu đăng nhập
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    # Refresh token nếu hết hạn
                    self.creds.refresh(Request())
                else:
                    # Kiểm tra file credentials.json
                    if not os.path.exists(self.credentials_file):
                        raise FileNotFoundError(
                            f"Không tìm thấy file '{self.credentials_file}'.\n\n"
                            "Vui lòng tải file credentials.json từ Google Cloud Console:\n"
                            "1. Truy cập https://console.cloud.google.com/\n"
                            "2. Tạo project mới hoặc chọn project có sẵn\n"
                            "3. Bật Google Sheets API\n"
                            "4. Tạo OAuth 2.0 Client ID (Desktop app)\n"
                            "5. Tải file credentials.json và đặt vào thư mục gốc"
                        )
                    
                    # Đăng nhập lần đầu
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)
                
                # Lưu token để sử dụng lần sau
                os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
                with open(self.token_file, 'w') as token:
                    token.write(self.creds.to_json())
            
            # Tạo service
            self.service = build('sheets', 'v4', credentials=self.creds)
            return True
            
        except FileNotFoundError as e:
            raise e
        except Exception as e:
            raise Exception(f"Lỗi xác thực Google Sheets API: {str(e)}")
    
    def read_sheet_data(self, spreadsheet_id, range_name='Sheet1!A:Z'):
        """
        Đọc dữ liệu từ Google Sheet
        
        Args:
            spreadsheet_id: ID của Google Sheet (lấy từ URL)
            range_name: Phạm vi đọc dữ liệu (mặc định: Sheet1!A:Z)
        
        Returns:
            list: Danh sách các dòng dữ liệu (mỗi dòng là một list)
        """
        try:
            if not self.service:
                raise Exception("Chưa xác thực. Vui lòng gọi authenticate() trước.")
            
            # Gọi API để đọc dữ liệu
            sheet = self.service.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                raise Exception("Sheet không có dữ liệu hoặc phạm vi đọc không đúng.")
            
            return values
            
        except HttpError as e:
            if e.resp.status == 404:
                raise Exception(
                    "Không tìm thấy Google Sheet.\n\n"
                    "Vui lòng kiểm tra:\n"
                    "1. Sheet ID có đúng không?\n"
                    "2. Bạn đã chia sẻ Sheet với email trong credentials.json chưa?"
                )
            elif e.resp.status == 403:
                raise Exception(
                    "Không có quyền truy cập Google Sheet.\n\n"
                    "Vui lòng:\n"
                    "1. Chia sẻ Sheet với email trong credentials.json\n"
                    "2. Hoặc đặt Sheet ở chế độ 'Anyone with the link can view'"
                )
            else:
                raise Exception(f"Lỗi HTTP {e.resp.status}: {str(e)}")
        except Exception as e:
            raise Exception(f"Lỗi khi đọc dữ liệu: {str(e)}")
    
    def parse_customer_data(self, values):
        """
        Parse dữ liệu từ Sheet thành format cho Auto Zalo
        
        Args:
            values: Dữ liệu từ Sheet (list of lists)
        
        Returns:
            list: Danh sách dict chứa thông tin khách hàng
        """
        if not values or len(values) < 2:
            raise Exception("Dữ liệu Sheet không hợp lệ (cần ít nhất 2 dòng: header + data)")
        
        # Dòng đầu tiên là header
        headers = [str(h).strip().lower() for h in values[0]]
        
        # Mapping các tên cột có thể có
        column_mapping = {
            'name': ['tên', 'ten', 'name', 'họ tên', 'ho ten', 'fullname'],
            'phone': ['sđt', 'sdt', 'phone', 'số điện thoại', 'so dien thoai', 'điện thoại', 'dien thoai'],
            'address': ['địa chỉ', 'dia chi', 'address', 'đc', 'dc'],
            'cccd': ['cccd', 'cmnd', 'id', 'số cccd', 'so cccd'],
            'dob': ['ngày sinh', 'ngay sinh', 'dob', 'date of birth', 'sinh nhật', 'sinh nhat'],
            'contract_id': ['hợp đồng', 'hop dong', 'contract', 'contract id', 'mã hợp đồng', 'ma hop dong'],
            'gender': ['giới tính', 'gioi tinh', 'gender', 'sex', 'gt']
        }
        
        # Tìm index của các cột
        column_indices = {}
        for key, possible_names in column_mapping.items():
            for idx, header in enumerate(headers):
                if any(name in header for name in possible_names):
                    column_indices[key] = idx
                    break
        
        # Kiểm tra các cột bắt buộc
        required_fields = ['phone']
        missing_fields = [field for field in required_fields if field not in column_indices]
        if missing_fields:
            raise Exception(
                f"Thiếu cột bắt buộc trong Sheet: {', '.join(missing_fields)}\n\n"
                f"Các cột hiện có: {', '.join(headers)}"
            )
        
        # Parse dữ liệu
        customers = []
        for row_idx, row in enumerate(values[1:], start=2):  # Bỏ qua header
            try:
                # Lấy giá trị từ các cột
                customer = {}
                for key, col_idx in column_indices.items():
                    if col_idx < len(row):
                        value = str(row[col_idx]).strip()
                        customer[key] = value if value else ""
                    else:
                        customer[key] = ""
                
                # Bỏ qua dòng không có số điện thoại
                if not customer.get('phone'):
                    continue
                
                # Chuẩn hóa số điện thoại (loại bỏ ký tự đặc biệt)
                phone = customer['phone'].replace(' ', '').replace('-', '').replace('.', '')
                customer['phone'] = phone
                
                customers.append(customer)
                
            except Exception as e:
                print(f"Lỗi khi parse dòng {row_idx}: {str(e)}")
                continue
        
        if not customers:
            raise Exception("Không có dữ liệu khách hàng hợp lệ trong Sheet")
        
        return customers
    
    def parse_contract_data(self, values):
        """
        Parse dữ liệu từ Sheet thành format cho Kiểm Tra Hợp Đồng
        
        Args:
            values: Dữ liệu từ Sheet (list of lists)
        
        Returns:
            list: Danh sách dict chứa thông tin hợp đồng
        """
        if not values or len(values) < 2:
            raise Exception("Dữ liệu Sheet không hợp lệ (cần ít nhất 2 dòng: header + data)")
        
        # Dòng đầu tiên là header
        headers = [str(h).strip().lower() for h in values[0]]
        
        # Mapping các tên cột có thể có
        column_mapping = {
            'contract_id': ['hợp đồng', 'hop dong', 'contract', 'contract id', 'mã hợp đồng', 'ma hop dong', 'số hợp đồng', 'so hop dong'],
            'cccd': ['cccd', 'cmnd', 'id', 'số cccd', 'so cccd', 'căn cước', 'can cuoc']
        }
        
        # Tìm index của các cột
        column_indices = {}
        for key, possible_names in column_mapping.items():
            for idx, header in enumerate(headers):
                if any(name in header for name in possible_names):
                    column_indices[key] = idx
                    break
        
        # Kiểm tra các cột bắt buộc
        required_fields = ['contract_id', 'cccd']
        missing_fields = [field for field in required_fields if field not in column_indices]
        if missing_fields:
            raise Exception(
                f"Thiếu cột bắt buộc trong Sheet: {', '.join(missing_fields)}\n\n"
                f"Các cột hiện có: {', '.join(headers)}"
            )
        
        # Parse dữ liệu
        contracts = []
        for row_idx, row in enumerate(values[1:], start=2):  # Bỏ qua header
            try:
                contract = {}
                for key, col_idx in column_indices.items():
                    if col_idx < len(row):
                        value = str(row[col_idx]).strip()
                        contract[key] = value if value else ""
                    else:
                        contract[key] = ""
                
                # Bỏ qua dòng không có đủ thông tin
                if not contract.get('contract_id') or not contract.get('cccd'):
                    continue
                
                contracts.append(contract)
                
            except Exception as e:
                print(f"Lỗi khi parse dòng {row_idx}: {str(e)}")
                continue
        
        if not contracts:
            raise Exception("Không có dữ liệu hợp đồng hợp lệ trong Sheet")
        
        return contracts


def get_spreadsheet_id_from_url(url):
    """
    Trích xuất Spreadsheet ID từ URL Google Sheets
    
    Args:
        url: URL của Google Sheet
    
    Returns:
        str: Spreadsheet ID
    """
    try:
        # URL format: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit...
        if '/spreadsheets/d/' in url:
            parts = url.split('/spreadsheets/d/')
            if len(parts) > 1:
                spreadsheet_id = parts[1].split('/')[0]
                return spreadsheet_id
        
        # Nếu người dùng nhập trực tiếp ID
        if len(url) > 20 and '/' not in url:
            return url
        
        raise ValueError("URL không hợp lệ")
    except Exception as e:
        raise Exception(
            f"Không thể trích xuất Sheet ID từ URL.\n\n"
            f"URL hợp lệ có dạng:\n"
            f"https://docs.google.com/spreadsheets/d/SHEET_ID/edit...\n\n"
            f"Hoặc nhập trực tiếp SHEET_ID"
        )

