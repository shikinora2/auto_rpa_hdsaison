import { useState, useEffect, useRef } from 'react';
import {
    Card,
    Button,
    message,
    Table,
    Upload,
    Input,
    Row,
    Col,
} from 'antd';
import {
    SendOutlined,
    UserAddOutlined,
    UploadOutlined,
    DownloadOutlined,
    DeleteOutlined,
    FileExcelOutlined,
} from '@ant-design/icons';
import { zaloAPI, filesAPI } from '../../services/api';
import './Zalo.css';

const { TextArea } = Input;

const TEMPLATE_VARIABLES = [
    { label: 'Tên khách hàng', value: '{name}' },
    { label: 'Anh/Chị', value: '{gender}' },
    { label: 'Số điện thoại', value: '{phone}' },
    { label: 'Mã hợp đồng', value: '{contract_id}' },
    { label: 'Tên nhân viên', value: '{my_name}' },
    { label: 'Địa chỉ', value: '{address}' },
    { label: 'Số CCCD', value: '{cccd}' },
    { label: 'Ngày sinh', value: '{dob}' },
];

function Zalo({ taskStatus }) {
    const [session, setSession] = useState({ is_active: false });
    const [customers, setCustomers] = useState([]);
    const [messageTemplate, setMessageTemplate] = useState('');
    const [loading, setLoading] = useState({
        login: false,
        sendMessages: false,
        addFriends: false
    });
    const pollRef = useRef(null);
    const messageInputRef = useRef(null);

    const stopSessionPolling = () => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    };

    useEffect(() => {
        loadSession();
        return () => stopSessionPolling();
    }, []);

    useEffect(() => {
        if (!taskStatus) return;
        const task = taskStatus.data?.task;
        const st = taskStatus.status;

        // Realtime: backend phát hiện avatar/icon sau QR → cập nhật ngay
        if (task === 'zalo_session' && st === 'active') {
            setLoading(prev => ({ ...prev, login: false }));
            stopSessionPolling();
            loadSession();
            return;
        }

        // Cuối task: backend push trạng thái thực tế, luôn cập nhật đúng
        if (task === 'zalo_session' && st === 'session_state') {
            setLoading(prev => ({ ...prev, login: false }));
            stopSessionPolling();
            loadSession();
            return;
        }

        if (st === 'completed' || st === 'error' || st === 'stopping') {
            setLoading({ login: false, sendMessages: false, addFriends: false });
            stopSessionPolling();
        }
        // Gọi loadSession sau cả completed lẫn error để đảm bảo đồng bộ
        if (task === 'zalo_login' && (st === 'completed' || st === 'error')) {
            loadSession();
        }
    }, [taskStatus]);

    const loadSession = async () => {
        try {
            const { data } = await zaloAPI.getSession();
            setSession(data);
        } catch (error) {
            console.error('Failed to load session:', error);
        }
    };

    const handleUpload = async (info) => {
        const file = info.file;
        try {
            const { data } = await filesAPI.parseExcel(file);
            const rows = (data.data || []).map((row, i) => ({ ...row, _key: i }));
            setCustomers(rows);
            const missing = rows.filter(r => !r.phone && !r.name && !r.contract_id);
            if (missing.length === rows.length && rows.length > 0) {
                message.warning(`Đã tải ${data.row_count} dòng nhưng không tìm thấy cột SĐT/Tên/Mã HĐ. Kiểm tra lại định dạng file.`);
            } else {
                message.success(`Đã tải ${data.row_count} khách hàng`);
            }
        } catch {
            message.error('Không thể đọc file Excel');
        }
    };

    const handleDeleteCustomer = (key) => {
        setCustomers(prev => prev.filter(r => r._key !== key));
    };

    const handleDownloadTemplate = () => {
        window.open(filesAPI.templateUrl(), '_blank');
    };

    const insertTemplateVariable = (variable) => {
        const textarea = messageInputRef.current?.resizableTextArea?.textArea;

        if (!textarea) {
            setMessageTemplate(prev => `${prev}${prev ? ' ' : ''}${variable}`);
            return;
        }

        const selectionStart = textarea.selectionStart ?? messageTemplate.length;
        const selectionEnd = textarea.selectionEnd ?? messageTemplate.length;
        const nextValue =
            messageTemplate.slice(0, selectionStart) +
            variable +
            messageTemplate.slice(selectionEnd);

        setMessageTemplate(nextValue);

        window.requestAnimationFrame(() => {
            textarea.focus();
            const cursorPosition = selectionStart + variable.length;
            textarea.setSelectionRange(cursorPosition, cursorPosition);
        });
    };

    const handleSendMessages = async () => {
        if (!session.is_active) {
            message.warning('Vui lòng đăng nhập Zalo trước');
            return;
        }
        if (customers.length === 0) {
            message.warning('Vui lòng tải danh sách khách hàng');
            return;
        }
        if (!messageTemplate.trim()) {
            message.warning('Vui lòng nhập nội dung tin nhắn');
            return;
        }

        const validCustomers = customers.filter(customer => String(customer.phone || '').trim());
        if (validCustomers.length === 0) {
            message.warning('Danh sách hiện tại không còn khách hàng nào có số điện thoại hợp lệ');
            return;
        }

        setLoading(prev => ({ ...prev, sendMessages: true }));
        try {
            const payload = validCustomers.map((customer) => {
                const next = { ...customer };
                delete next._key;
                return next;
            });
            await zaloAPI.sendMessages({
                customers: payload,
                message_template: messageTemplate,
                check_friend_status: true
            });
            message.success('Đã bắt đầu gửi tin nhắn');
        } catch (error) {
            message.error(error.response?.data?.detail || 'Không thể gửi tin');
            setLoading(prev => ({ ...prev, sendMessages: false }));
        }
    };

    const handleAddFriends = async () => {
        if (!session.is_active) {
            message.warning('Vui lòng đăng nhập Zalo trước');
            return;
        }
        if (customers.length === 0) {
            message.warning('Vui lòng tải danh sách khách hàng');
            return;
        }

        const validCustomers = customers.filter(customer => String(customer.phone || '').trim());
        if (validCustomers.length === 0) {
            message.warning('Danh sách hiện tại không còn khách hàng nào có số điện thoại hợp lệ');
            return;
        }

        setLoading(prev => ({ ...prev, addFriends: true }));
        try {
            const payload = validCustomers.map((customer) => {
                const next = { ...customer };
                delete next._key;
                return next;
            });
            await zaloAPI.addFriends({
                customers: payload,
                greeting_template: messageTemplate
            });
            message.success('Đã bắt đầu kết bạn');
        } catch (error) {
            message.error(error.response?.data?.detail || 'Không thể kết bạn');
            setLoading(prev => ({ ...prev, addFriends: false }));
        }
    };

    const customerColumns = [
        { title: 'STT', key: 'stt', width: 55, render: (_, __, i) => i + 1, align: 'center' },
        { title: 'Số điện thoại', dataIndex: 'phone', key: 'phone', width: 140 },
        { title: 'Tên', dataIndex: 'name', key: 'name' },
        { title: 'Mã HĐ', dataIndex: 'contract_id', key: 'contract_id', width: 160 },
        {
            title: '',
            key: 'action',
            width: 48,
            render: (_, record) => (
                <Button
                    size="small"
                    danger
                    type="text"
                    icon={<DeleteOutlined />}
                    onClick={() => handleDeleteCustomer(record._key)}
                />
            ),
        },
    ];

    return (
        <div className="zalo-container">
            <Row gutter={[24, 24]}>
                {/* Dữ liệu khách hàng */}
                <Col xs={24}>
                    <Card
                        title={`Danh sách khách hàng${customers.length ? ` (${customers.length})` : ''}`}
                        className="customer-card"
                        extra={
                            <div style={{ display: 'flex', gap: 8 }}>
                                <Button
                                    icon={<DownloadOutlined />}
                                    onClick={handleDownloadTemplate}
                                    className="template-btn"
                                >
                                    Tải mẫu Excel
                                </Button>
                                <Upload
                                    accept=".xlsx,.xls"
                                    showUploadList={false}
                                    beforeUpload={() => false}
                                    onChange={handleUpload}
                                >
                                    <Button icon={<FileExcelOutlined />} type="primary">
                                        Tải lên danh sách
                                    </Button>
                                </Upload>
                            </div>
                        }
                    >
                        <Table
                            columns={customerColumns}
                            dataSource={customers}
                            rowKey={(r) => r._key}
                            size="small"
                            scroll={{ y: 420 }}
                            pagination={{ pageSize: 50, size: 'small', showTotal: (total) => `${total} khách hàng` }}
                        />
                    </Card>
                </Col>

                {/* Soạn tin nhắn */}
                <Col xs={24}>
                    <Card title="Soạn tin nhắn" className="message-card">
                        <div className="template-variable-toolbar">
                            <div className="template-variable-label">Chèn nhanh thông tin:</div>
                            <div className="template-variable-buttons">
                                {TEMPLATE_VARIABLES.map(item => (
                                    <Button
                                        key={item.value}
                                        size="small"
                                        className="template-variable-btn"
                                        onClick={() => insertTemplateVariable(item.value)}
                                    >
                                        {item.label}
                                    </Button>
                                ))}
                            </div>
                        </div>
                        <TextArea
                            ref={messageInputRef}
                            rows={4}
                            placeholder="Nhập nội dung tin nhắn. Sử dụng các nút {name}, {gender}, {contract_id}... để chèn nhanh thông tin khách hàng"
                            value={messageTemplate}
                            onChange={(e) => setMessageTemplate(e.target.value)}
                        />
                        <div className="template-variable-hint">
                            Các biến sẽ được thay bằng dữ liệu từng khách hàng khi gửi hoặc kết bạn hàng loạt.
                        </div>
                        <div className="zalo-actions">
                            <Button
                                type="primary"
                                icon={<SendOutlined />}
                                onClick={handleSendMessages}
                                loading={loading.sendMessages}
                                disabled={!session.is_active}
                                size="large"
                                className="send-btn"
                            >
                                Gửi tin nhắn hàng loạt
                            </Button>
                            <Button
                                icon={<UserAddOutlined />}
                                onClick={handleAddFriends}
                                loading={loading.addFriends}
                                disabled={!session.is_active}
                                size="large"
                                className="friend-btn"
                            >
                                Kết bạn hàng loạt
                            </Button>
                        </div>
                    </Card>
                </Col>
            </Row>


        </div>
    );
}

export default Zalo;
