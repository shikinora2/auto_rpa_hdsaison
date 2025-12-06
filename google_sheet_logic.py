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
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']  # Quyền đọc và ghi

class GoogleSheetManager:
    """Quản lý kết nối và đọc dữ liệu từ Google Sheets"""
    
    def __init__(self, credentials_file='credentials.json', token_file='token.json'):
        """
        Khởi tạo Google Sheet Manager

        Args:
            credentials_file: Đường dẫn đến file credentials.json từ Google Cloud Console
            token_file: Đường dẫn đến file lưu token xác thực (mặc định: token.json)
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.creds = None
        self.service = None
        self.current_spreadsheet_id = None  # Lưu spreadsheet ID hiện tại để dùng lại
        
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
                    abs_cred_path = os.path.abspath(self.credentials_file)
                    current_dir = os.getcwd()

                    if not os.path.exists(self.credentials_file):
                        raise FileNotFoundError(
                            f"Không tìm thấy file '{self.credentials_file}'.\n\n"
                            f"Đường dẫn tìm kiếm: {abs_cred_path}\n"
                            f"Thư mục hiện tại: {current_dir}\n\n"
                            "Vui lòng tải file credentials.json từ Google Cloud Console:\n"
                            "1. Truy cập https://console.cloud.google.com/\n"
                            "2. Tạo project mới hoặc chọn project có sẵn\n"
                            "3. Bật Google Sheets API\n"
                            "4. Tạo OAuth 2.0 Client ID (Desktop app)\n"
                            "5. Tải file credentials.json và đặt vào thư mục gốc của ứng dụng"
                        )
                    
                    # Đăng nhập lần đầu
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)
                
                # Lưu token để sử dụng lần sau
                token_dir = os.path.dirname(self.token_file)
                if token_dir:  # Chỉ tạo thư mục nếu có đường dẫn
                    os.makedirs(token_dir, exist_ok=True)
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

    def write_sheet_data(self, spreadsheet_id, range_name, values):
        """
        Ghi dữ liệu vào Google Sheet

        Args:
            spreadsheet_id: ID của Google Sheet
            range_name: Phạm vi ghi dữ liệu (VD: Sheet1!A1:G1)
            values: Dữ liệu cần ghi (list of lists)

        Returns:
            dict: Kết quả từ API
        """
        try:
            if not self.service:
                raise Exception("Chưa xác thực. Vui lòng gọi authenticate() trước.")

            body = {
                'values': values
            }

            result = self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()

            return result

        except HttpError as e:
            if e.resp.status == 403:
                raise Exception(
                    "Không có quyền ghi vào Google Sheet.\n\n"
                    "Vui lòng:\n"
                    "1. Chia sẻ Sheet với quyền 'Editor'\n"
                    "2. Hoặc đặt Sheet ở chế độ 'Anyone with the link can edit'"
                )
            else:
                raise Exception(f"Lỗi HTTP {e.resp.status}: {str(e)}")
        except Exception as e:
            raise Exception(f"Lỗi khi ghi dữ liệu: {str(e)}")

    def create_contract_headers(self, spreadsheet_id, sheet_name='Sheet1'):
        """
        Tạo header cho Sheet theo định dạng file Excel trong downloads_contracts

        Args:
            spreadsheet_id: ID của Google Sheet
            sheet_name: Tên sheet (mặc định: Sheet1)

        Returns:
            bool: True nếu thành công
        """
        headers = [
            'STT',
            'Số hợp đồng',
            'Họ tên',
            'Ngày sinh',
            'SĐT',
            'Số CCCD',
            'Ngày kết thúc'
        ]

        range_name = f"{sheet_name}!A1:G1"
        self.write_sheet_data(spreadsheet_id, range_name, [headers])
        return True

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

    def append_sheet_data(self, spreadsheet_id, range_name, values):
        """
        Thêm dữ liệu vào cuối sheet

        Args:
            spreadsheet_id: ID của Google Sheet
            range_name: Phạm vi thêm (ví dụ: 'Sheet1!A1' hoặc 'Sheet1')
            values: List of lists chứa dữ liệu cần thêm

        Returns:
            Số lượng rows đã thêm
        """
        try:
            if not self.service:
                raise Exception("Chưa xác thực. Vui lòng gọi authenticate() trước.")

            body = {
                'values': values
            }

            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

            return result.get('updates', {}).get('updatedRows', 0)

        except HttpError as error:
            error_details = str(error)
            if 'Unable to parse range' in error_details:
                raise Exception(f"Lỗi format range: '{range_name}'. Vui lòng sử dụng format như 'Sheet1!A1' hoặc 'Sheet1'")
            raise Exception(f"Lỗi khi thêm dữ liệu: {error}")

    def clear_sheet_data(self, spreadsheet_id, range_name):
        """
        Xóa dữ liệu trong một phạm vi

        Args:
            spreadsheet_id: ID của Google Sheet
            range_name: Phạm vi xóa (ví dụ: 'Sheet1!A1:D10')

        Returns:
            True nếu thành công
        """
        try:
            if not self.service:
                raise Exception("Chưa xác thực. Vui lòng gọi authenticate() trước.")

            self.service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()

            return True

        except HttpError as error:
            raise Exception(f"Lỗi khi xóa dữ liệu: {error}")

    def batch_update_sheet(self, spreadsheet_id, data_list):
        """
        Cập nhật nhiều phạm vi cùng lúc

        Args:
            spreadsheet_id: ID của Google Sheet
            data_list: List of dicts với format {'range': 'Sheet1!A1', 'values': [[...]]}

        Returns:
            Tổng số cells đã cập nhật
        """
        try:
            if not self.service:
                raise Exception("Chưa xác thực. Vui lòng gọi authenticate() trước.")

            batch_data = []
            for item in data_list:
                batch_data.append({
                    'range': item['range'],
                    'values': item['values']
                })

            body = {
                'valueInputOption': 'USER_ENTERED',
                'data': batch_data
            }

            result = self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()

            return result.get('totalUpdatedCells', 0)

        except HttpError as error:
            raise Exception(f"Lỗi khi batch update: {error}")

    def get_spreadsheet_info(self, spreadsheet_id):
        """
        Lấy thông tin về spreadsheet

        Args:
            spreadsheet_id: ID của Google Sheet

        Returns:
            Dict chứa thông tin spreadsheet (title, sheets, url)
        """
        try:
            if not self.service:
                raise Exception("Chưa xác thực. Vui lòng gọi authenticate() trước.")

            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()

            title = sheet_metadata.get('properties', {}).get('title', 'Unknown')
            sheets = sheet_metadata.get('sheets', [])
            sheet_names = [sheet.get('properties', {}).get('title', '') for sheet in sheets]

            return {
                'title': title,
                'sheets': sheet_names,
                'url': f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
            }

        except HttpError as error:
            raise Exception(f"Lỗi khi lấy thông tin spreadsheet: {error}")

    def set_spreadsheet_id(self, spreadsheet_id):
        """
        Lưu spreadsheet ID hiện tại để sử dụng cho các thao tác tiếp theo

        Args:
            spreadsheet_id: ID của Google Sheet
        """
        self.current_spreadsheet_id = spreadsheet_id

    def get_current_spreadsheet_id(self):
        """
        Lấy spreadsheet ID hiện tại

        Returns:
            str: Spreadsheet ID hiện tại hoặc None
        """
        return self.current_spreadsheet_id

    # === WRAPPER METHODS - Sử dụng spreadsheet_id đã lưu ===

    def read_current_sheet(self, range_name):
        """
        Đọc dữ liệu từ sheet hiện tại (sử dụng spreadsheet_id đã lưu)

        Args:
            range_name: Phạm vi đọc (ví dụ: 'Sheet1!A1:D10')

        Returns:
            List of lists chứa dữ liệu
        """
        if not self.current_spreadsheet_id:
            raise Exception("Chưa thiết lập spreadsheet ID. Vui lòng kết nối với Google Sheet trước.")
        return self.read_sheet_data(self.current_spreadsheet_id, range_name)

    def write_current_sheet(self, range_name, values):
        """
        Ghi dữ liệu vào sheet hiện tại (sử dụng spreadsheet_id đã lưu)

        Args:
            range_name: Phạm vi ghi (ví dụ: 'Sheet1!A1')
            values: List of lists chứa dữ liệu

        Returns:
            Số lượng cells đã cập nhật
        """
        if not self.current_spreadsheet_id:
            raise Exception("Chưa thiết lập spreadsheet ID. Vui lòng kết nối với Google Sheet trước.")
        return self.write_sheet_data(self.current_spreadsheet_id, range_name, values)

    def append_current_sheet(self, range_name, values):
        """
        Thêm dữ liệu vào sheet hiện tại (sử dụng spreadsheet_id đã lưu)

        Args:
            range_name: Phạm vi thêm (ví dụ: 'Sheet1!A1')
            values: List of lists chứa dữ liệu

        Returns:
            Số lượng rows đã thêm
        """
        if not self.current_spreadsheet_id:
            raise Exception("Chưa thiết lập spreadsheet ID. Vui lòng kết nối với Google Sheet trước.")
        return self.append_sheet_data(self.current_spreadsheet_id, range_name, values)

    def clear_current_sheet(self, range_name):
        """
        Xóa dữ liệu trong sheet hiện tại (sử dụng spreadsheet_id đã lưu)

        Args:
            range_name: Phạm vi xóa (ví dụ: 'Sheet1!A1:D10')

        Returns:
            True nếu thành công
        """
        if not self.current_spreadsheet_id:
            raise Exception("Chưa thiết lập spreadsheet ID. Vui lòng kết nối với Google Sheet trước.")
        return self.clear_sheet_data(self.current_spreadsheet_id, range_name)

    def batch_update_current_sheet(self, data_list):
        """
        Batch update sheet hiện tại (sử dụng spreadsheet_id đã lưu)

        Args:
            data_list: List of dicts với format {'range': 'Sheet1!A1', 'values': [[...]]}

        Returns:
            Tổng số cells đã cập nhật
        """
        if not self.current_spreadsheet_id:
            raise Exception("Chưa thiết lập spreadsheet ID. Vui lòng kết nối với Google Sheet trước.")
        return self.batch_update_sheet(self.current_spreadsheet_id, data_list)

    def get_current_spreadsheet_info(self):
        """
        Lấy thông tin về spreadsheet hiện tại (sử dụng spreadsheet_id đã lưu)

        Returns:
            Dict chứa thông tin spreadsheet (title, sheets, url)
        """
        if not self.current_spreadsheet_id:
            raise Exception("Chưa thiết lập spreadsheet ID. Vui lòng kết nối với Google Sheet trước.")
        return self.get_spreadsheet_info(self.current_spreadsheet_id)


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

