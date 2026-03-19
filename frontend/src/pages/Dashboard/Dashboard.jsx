import { useState, useEffect, useRef } from 'react';
import {
    Card,
    Form,
    Input,
    Button,
    message,
    Row,
    Col,
    Badge,
    Progress,
    Tooltip,
    Tag,
    Popconfirm,
    Modal,
} from 'antd';
import {
    UserOutlined,
    LockOutlined,
    LoginOutlined,
    LogoutOutlined,
    ReloadOutlined,
    PlusOutlined,
    DeleteOutlined,
} from '@ant-design/icons';
import { configAPI, rpaAPI, zaloAPI } from '../../services/api';
import './Dashboard.css';
import '../Zalo/Zalo.css';

const TASK_LABELS = {
    check_contracts: 'Kiểm tra HĐ',
    download_files: 'Tải file PDF/JSON',
    scrape_details: 'Cào chi tiết → Excel',
    login: 'Đăng nhập HPO',
    zalo_login: 'Login Zalo',
    send_messages: 'Gửi tin nhắn Zalo',
    add_friends: 'Kết bạn Zalo',
};

function Dashboard({ taskStatus, wsStatus = 'disconnected', progress, headless, onHeadlessChange, sessionStatus, onVerifySession, onSessionUpdate, rpaStatus, qrImage }) {
    const [form] = Form.useForm();
    const [loggingIn, setLoggingIn] = useState(false);

    // ─── Zalo state ───────────────────────────────────────────
    const [accounts, setAccounts] = useState([]);
    const [selectedAccount, setSelectedAccount] = useState(null);
    const [zaloSession, setZaloSession] = useState({ is_active: false });
    const [zaloLoading, setZaloLoading] = useState(false);
    const [localQrBase64, setLocalQrBase64] = useState(null);
    const [addAccountModal, setAddAccountModal] = useState(false);
    const [newAccountName, setNewAccountName] = useState('');
    const pollRef = useRef(null);
    const selectedAccountRef = useRef(null);
    useEffect(() => { selectedAccountRef.current = selectedAccount; }, [selectedAccount]);

    useEffect(() => {
        loadConfig();
    }, []);

    useEffect(() => {
        if (!taskStatus) return;
        const task = taskStatus.data?.task;
        const st = taskStatus.status;
        if (task === 'login' && (st === 'completed' || st === 'error')) {
            setLoggingIn(false);
        }
        if (task === 'zalo_session' && (st === 'active' || st === 'session_state')) {
            setZaloLoading(false);
            setLocalQrBase64(null);
            stopSessionPolling();
            loadZaloSession(selectedAccountRef.current);
        }
        if (task === 'zalo_login' && (st === 'completed' || st === 'error')) {
            setZaloLoading(false);
            setLocalQrBase64(null);
            stopSessionPolling();
            loadZaloSession(selectedAccountRef.current);
        }
        if (st === 'completed' || st === 'error' || st === 'stopping') {
            setZaloLoading(false);
            stopSessionPolling();
        }
    }, [taskStatus]);

    const loadConfig = async () => {
        try {
            const { data } = await configAPI.get();
            form.setFieldsValue({
                username: data.username || '',
                password: '',
            });
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    };

    const handleLoginAndSave = async () => {
        try {
            const values = await form.validateFields();
            if (!values.password) {
                message.warning('Vui lòng nhập mật khẩu');
                return;
            }
            setLoggingIn(true);
            await configAPI.update({
                username: values.username,
                password: values.password,
                headless: headless,
            });
            await rpaAPI.login({
                username: values.username,
                password: values.password,
                headless: headless,
            });
            message.info('Đang đăng nhập HPO, vui lòng chờ...');
        } catch (error) {
            if (error?.errorFields) return; // antd validation error
            message.error(error.response?.data?.detail || 'Không thể đăng nhập');
            setLoggingIn(false);
        }
    };

    const handleLogout = async () => {
        try {
            await rpaAPI.logout();
            onSessionUpdate({ is_logged_in: false, checking: false });
            message.success('Đã xóa phiên đăng nhập HPO');
        } catch {
            message.error('Không thể đăng xuất');
        }
    };

    const handlePause = async () => {
        // Moved to App.jsx header
    };

    const handleStop = async () => {
        // Moved to App.jsx header
    };

    // ─── Zalo helpers ─────────────────────────────────────────
    const startSessionPolling = (accountId) => {
        stopSessionPolling();
        pollRef.current = setInterval(async () => {
            try {
                const { data } = await zaloAPI.getSession(accountId);
                if (data.is_active) {
                    setZaloSession(data);
                    setZaloLoading(false);
                    stopSessionPolling();
                }
            } catch { /* ignore */ }
        }, 3000);
    };

    const stopSessionPolling = () => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    };

    const loadAccounts = async () => {
        try {
            const { data } = await zaloAPI.getAccounts();
            setAccounts(data.accounts || []);
            const defaultAcc = data.accounts?.find(a => a.is_default);
            if (defaultAcc) setSelectedAccount(defaultAcc.id);
        } catch (error) {
            console.error('Failed to load Zalo accounts:', error);
        }
    };

    const loadZaloSession = async (accountId) => {
        if (!accountId) return;
        try {
            const { data } = await zaloAPI.getSession(accountId);
            setZaloSession(data);
            if (!data.is_active) {
                // Try fetch cached QR image immediately (for page reload scenario)
                try {
                    const { data: qrData } = await zaloAPI.getQR(accountId);
                    if (qrData.qr_base64) {
                        setLocalQrBase64(qrData.qr_base64);
                    }
                } catch { /* ignore */ }
                // Auto-start login task if nothing is running
                if (!data.is_running) {
                    setZaloLoading(true);
                    try {
                        await zaloAPI.login(accountId);
                    } catch (err) {
                        // 400 = another task running, ignore silently
                        if (err?.response?.status !== 400) {
                            setZaloLoading(false);
                        }
                    }
                } else if (data.current_task === 'zalo_login') {
                    // A login task is already running — just reflect that in UI
                    setZaloLoading(true);
                }
            }
        } catch (error) {
            console.error('Failed to load Zalo session:', error);
        }
    };

    const handleAddAccount = async () => {
        if (!newAccountName.trim()) {
            message.warning('Vui lòng nhập tên tài khoản');
            return;
        }
        try {
            await zaloAPI.addAccount({ name: newAccountName });
            message.success('Đã thêm tài khoản');
            setAddAccountModal(false);
            setNewAccountName('');
            loadAccounts();
        } catch {
            message.error('Không thể thêm tài khoản');
        }
    };

    const handleDeleteAccount = async (id) => {
        try {
            await zaloAPI.deleteAccount(id);
            message.success('Đã xóa tài khoản');
            if (selectedAccount === id) setSelectedAccount(null);
            loadAccounts();
        } catch {
            message.error('Không thể xóa tài khoản');
        }
    };

    const handleZaloLogin = async () => {
        setZaloLoading(true);
        try {
            await zaloAPI.login(selectedAccount);
            message.info('Đang mở trình duyệt Zalo, vui lòng quét mã QR');
            startSessionPolling(selectedAccount);
        } catch (error) {
            message.error(error.response?.data?.detail || 'Không thể đăng nhập Zalo');
            setZaloLoading(false);
        }
    };

    const handleZaloLogout = async () => {
        try {
            stopSessionPolling();
            await zaloAPI.logout(selectedAccount);
            setZaloSession({ is_active: false });
            message.success('Đã đăng xuất Zalo');
        } catch {
            message.error('Không thể đăng xuất Zalo');
        }
    };

    useEffect(() => {
        loadAccounts();
        return () => stopSessionPolling();
    }, []);

    useEffect(() => {
        stopSessionPolling();
        setLocalQrBase64(null);
        if (!selectedAccount) {
            setZaloSession({ is_active: false });
            setZaloLoading(false);
            return;
        }
        loadZaloSession(selectedAccount);
    }, [selectedAccount]);

    // Sync WebSocket-pushed QR to local state
    useEffect(() => {
        if (qrImage && qrImage.account_id === selectedAccount && qrImage.qr_base64) {
            setLocalQrBase64(qrImage.qr_base64);
        }
    }, [qrImage, selectedAccount]);

    const currentTaskName = TASK_LABELS[taskStatus?.data?.task] || null;

    return (
        <div className="dashboard-container">
            {/* Progress Bar (global) */}
            {progress && rpaStatus.is_running && (
                <div className="global-progress-bar">
                    <div className="global-progress-header">
                        <span className="global-progress-label">
                            <Badge status="processing" />
                            {currentTaskName || 'Đang xử lý'} — {progress.message}
                        </span>
                        <span className="global-progress-count">
                            {progress.current}/{progress.total} ({progress.percentage}%)
                        </span>
                    </div>
                    <Progress
                        percent={progress.percentage}
                        status="active"
                        showInfo={false}
                        strokeColor={{ from: '#868CFF', to: '#4318FF' }}
                        size={['100%', 6]}
                    />
                </div>
            )}

            <Row gutter={[24, 24]}>
                {/* Login Form */}
                <Col xs={24} lg={12}>
                    <Card
                        title="Cấu hình đăng nhập HPO"
                        className="config-card"
                        extra={
                            <Tooltip title="Kiểm tra lại phiên">
                                <Button
                                    size="small"
                                    icon={<ReloadOutlined />}
                                    onClick={onVerifySession}
                                    loading={sessionStatus.checking}
                                />
                            </Tooltip>
                        }
                    >
                        <Form form={form} layout="vertical" initialValues={{ headless: false }}>
                            <div className="login-fields-row">
                                <Form.Item
                                    name="username"
                                    label="Tên đăng nhập"
                                    rules={[{ required: true, message: 'Nhập tên đăng nhập' }]}
                                    style={{ flex: 1, marginBottom: 0 }}
                                >
                                    <Input prefix={<UserOutlined />} placeholder="Nhập username HPO" className="login-input" />
                                </Form.Item>
                                <Form.Item
                                    name="password"
                                    label="Mật khẩu"
                                    rules={[{ required: true, message: 'Nhập mật khẩu' }]}
                                    style={{ flex: 1, marginBottom: 0 }}
                                >
                                    <Input.Password prefix={<LockOutlined />} placeholder="Nhập mật khẩu" className="login-input" />
                                </Form.Item>
                            </div>

                            <div className="action-buttons-vertical" style={{ marginTop: 16 }}>
                                <Row gutter={8}>
                                    <Col span={16}>
                                        <Button
                                            type="primary"
                                            icon={<LoginOutlined />}
                                            onClick={handleLoginAndSave}
                                            loading={loggingIn}
                                            size="large"
                                            block
                                            className="login-btn"
                                        >
                                            {loggingIn ? 'Đang đăng nhập...' : 'Đăng nhập HPO'}
                                        </Button>
                                    </Col>
                                    <Col span={8}>
                                        <Button
                                            danger
                                            onClick={handleLogout}
                                            block
                                            size="large"
                                            icon={<LogoutOutlined />}
                                        >
                                            Xóa phiên
                                        </Button>
                                    </Col>
                                </Row>
                            </div>
                        </Form>
                    </Card>
                </Col>

                {/* Zalo Account Management */}
                <Col xs={24} lg={12}>
                    <Card
                        title="Quản lý tài khoản Zalo"
                        className="account-card"
                        style={{ height: '100%' }}
                    >
                        <div className="account-list">
                            {accounts.length === 0 && (
                                <div className="account-empty">Chưa có tài khoản nào</div>
                            )}
                            {accounts.map(acc => (
                                <div
                                    key={acc.id}
                                    className={`account-item${selectedAccount === acc.id ? ' selected' : ''}`}
                                    onClick={() => setSelectedAccount(acc.id)}
                                >
                                    <div className="account-item-left">
                                        <span className="account-item-name">{acc.name}</span>
                                        <div className="account-item-tags">
                                            {acc.is_default && <Tag color="blue">Mặc định</Tag>}
                                            {selectedAccount === acc.id && (
                                                <Tag color={zaloSession.is_active ? 'green' : 'default'}>
                                                    {zaloSession.is_active
                                                        ? (zaloSession.zalo_name ? zaloSession.zalo_name : 'Đã đăng nhập')
                                                        : 'Chưa đăng nhập'}
                                                </Tag>
                                            )}
                                        </div>
                                    </div>
                                    <Popconfirm
                                        title="Xóa tài khoản này?"
                                        onConfirm={() => handleDeleteAccount(acc.id)}
                                    >
                                        <Button
                                            size="small"
                                            danger
                                            type="text"
                                            icon={<DeleteOutlined />}
                                            onClick={(e) => e.stopPropagation()}
                                        />
                                    </Popconfirm>
                                </div>
                            ))}
                        </div>
                        <div className="account-footer">
                            {/* QR code hiển thị khi đang chờ đăng nhập */}
                            {zaloLoading && localQrBase64 && (
                                <div className="zalo-qr-wrapper">
                                    <div className="zalo-qr-label">Quét mã QR bằng ứng dụng Zalo</div>
                                    <img
                                        src={`data:image/png;base64,${localQrBase64}`}
                                        alt="Zalo QR Code"
                                        className="zalo-qr-image"
                                    />
                                    <div className="zalo-qr-hint">Đang chờ quét mã...</div>
                                </div>
                            )}
                            {zaloLoading && !localQrBase64 && (
                                <div className="zalo-qr-wrapper">
                                    <div className="zalo-qr-label">Đang tạo mã QR...</div>
                                    <div className="zalo-qr-placeholder" />
                                    <div className="zalo-qr-hint">Vui lòng chờ trong giây lát</div>
                                </div>
                            )}
                            <Button icon={<PlusOutlined />} onClick={() => setAddAccountModal(true)} block>
                                Thêm tài khoản
                            </Button>
                            {zaloSession.is_active ? (
                                <Button danger icon={<LogoutOutlined />} onClick={handleZaloLogout} block size="large">
                                    Đăng xuất Zalo
                                </Button>
                            ) : (
                                <Button
                                    type="primary"
                                    icon={<LoginOutlined />}
                                    onClick={handleZaloLogin}
                                    loading={zaloLoading}
                                    disabled={!selectedAccount}
                                    block
                                    size="large"
                                    className="zalo-login-btn"
                                >
                                    Đăng nhập Zalo
                                </Button>
                            )}
                        </div>
                    </Card>
                </Col>
            </Row>

            <Modal
                title="Thêm tài khoản Zalo"
                open={addAccountModal}
                onOk={handleAddAccount}
                onCancel={() => setAddAccountModal(false)}
            >
                <Input
                    placeholder="Tên tài khoản (VD: Nhân viên A)"
                    value={newAccountName}
                    onChange={(e) => setNewAccountName(e.target.value)}
                    size="large"
                />
            </Modal>
        </div>
    );
}

export default Dashboard;
