import { useState, useEffect, useRef, useCallback } from 'react';
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
    Alert,
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
    scrape_details: 'Lấy dữ liệu hợp đồng → Excel',
    login: 'Đăng nhập HPO',
    zalo_login: 'Login Zalo',
    send_messages: 'Gửi tin nhắn Zalo',
    add_friends: 'Kết bạn Zalo',
};

function Dashboard({ taskStatus, progress, headless, sessionStatus, onVerifySession, onSessionUpdate, rpaStatus, qrImage }) {
    const [form] = Form.useForm();
    const [loggingIn, setLoggingIn] = useState(false);

    // ─── Zalo state ───────────────────────────────────────────
    const [zaloSession, setZaloSession] = useState({ is_active: false });
    const [zaloLoading, setZaloLoading] = useState(false);
    const [localQrBase64, setLocalQrBase64] = useState(null);
    const pollRef = useRef(null);
    const zaloLoginRequestedRef = useRef(false);

    const loadConfig = useCallback(async () => {
        try {
            const { data } = await configAPI.get();
            form.setFieldsValue({
                username: data.username || '',
                password: '',
            });
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }, [form]);

    const stopSessionPolling = useCallback(() => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }, []);

    const syncQrFromCache = useCallback(async () => {
        try {
            const { data: qrData } = await zaloAPI.getQR();
            if (qrData.qr_base64) {
                setLocalQrBase64(qrData.qr_base64);
            }
            if (qrData.is_running && (qrData.current_task === 'zalo_login' || qrData.current_task === 'login')) {
                setZaloLoading(true);
            }
        } catch (error) {
            console.debug('Failed to sync cached Zalo QR:', error);
        }
    }, []);

    const startSessionPolling = useCallback(() => {
        stopSessionPolling();
        pollRef.current = setInterval(async () => {
            try {
                const { data } = await zaloAPI.getSession();
                if (data.is_active) {
                    setZaloSession(data);
                    setZaloLoading(false);
                    setLocalQrBase64(null);
                    stopSessionPolling();
                    return;
                }

                if (data.is_running && (data.current_task === 'zalo_login' || data.current_task === 'login')) {
                    setZaloLoading(true);
                    await syncQrFromCache();
                } else {
                    setZaloLoading(false);
                }
            } catch (error) {
                console.debug('Zalo polling failed:', error);
            }
        }, 3000);
    }, [stopSessionPolling, syncQrFromCache]);

    const loadZaloSession = useCallback(async () => {
        try {
            const { data } = await zaloAPI.getSession();
            setZaloSession(data);
            if (!data.is_active) {
                setLocalQrBase64(null);

                if (data.is_running && (data.current_task === 'zalo_login' || data.current_task === 'login')) {
                    setZaloLoading(true);
                    startSessionPolling();
                    await syncQrFromCache();
                } else {
                    setZaloLoading(false);
                }
            }
        } catch (error) {
            console.error('Failed to load Zalo session:', error);
        }
    }, [startSessionPolling, syncQrFromCache]);

    useEffect(() => {
        loadConfig();
    }, [loadConfig]);

    useEffect(() => {
        if (!taskStatus) return;
        const task = taskStatus.data?.task;
        const st = taskStatus.status;
        const isZaloTask = task === 'zalo_login' || task === 'zalo_session' || task === 'send_messages' || task === 'add_friends';
        if (task === 'login' && (st === 'completed' || st === 'error')) {
            setLoggingIn(false);
        }
        if (task === 'zalo_session' && (st === 'active' || st === 'session_state')) {
            setZaloLoading(false);
            setLocalQrBase64(null);
            zaloLoginRequestedRef.current = false;
            stopSessionPolling();
            loadZaloSession();
            if (st === 'active') {
                message.success('Đăng nhập Zalo thành công. Bạn có thể dùng các chức năng Auto Zalo.');
            }
        }
        if (task === 'zalo_login' && (st === 'completed' || st === 'error')) {
            setZaloLoading(false);
            setLocalQrBase64(null);
            stopSessionPolling();
            loadZaloSession();
            if (st === 'error' && zaloLoginRequestedRef.current) {
                message.error('Đăng nhập Zalo thất bại hoặc hết thời gian quét QR.');
            }
            zaloLoginRequestedRef.current = false;
        }
        if (isZaloTask && (st === 'completed' || st === 'error' || st === 'stopping')) {
            setZaloLoading(false);
            if (st === 'error') {
                zaloLoginRequestedRef.current = false;
            }
            stopSessionPolling();
        }
    }, [taskStatus, loadZaloSession, stopSessionPolling]);

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

    const handleZaloLogin = async () => {
        stopSessionPolling();
        setLocalQrBase64(null);
        setZaloLoading(true);
        zaloLoginRequestedRef.current = true;
        try {
            await zaloAPI.login();
            message.info('Đã gửi yêu cầu lấy mã QR Zalo. Vui lòng chờ mã hiển thị và quét để đăng nhập.');
            await syncQrFromCache();
            startSessionPolling();
        } catch (error) {
            if (error?.response?.status === 400 && /Another Zalo task is running/i.test(error?.response?.data?.detail || '')) {
                message.info('Tác vụ đăng nhập Zalo đang chạy, đang đồng bộ lại mã QR...');
                setZaloLoading(true);
                await syncQrFromCache();
                startSessionPolling();
                return;
            }
            message.error(error.response?.data?.detail || 'Không thể đăng nhập Zalo');
            setZaloLoading(false);
            zaloLoginRequestedRef.current = false;
        }
    };

    const handleZaloLogout = async () => {
        try {
            stopSessionPolling();
            await zaloAPI.logout();
            setZaloSession({ is_active: false });
            message.success('Đã đăng xuất Zalo');
        } catch {
            message.error('Không thể đăng xuất Zalo');
        }
    };

    useEffect(() => {
        loadZaloSession();
        return () => stopSessionPolling();
    }, [loadZaloSession, stopSessionPolling]);

    // Sync WebSocket-pushed QR to local state
    useEffect(() => {
        if (qrImage && qrImage.qr_base64) {
            setLocalQrBase64(qrImage.qr_base64);
        }
    }, [qrImage]);

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

                            <div className="hpo-actions-row">
                                <Button
                                    type="primary"
                                    icon={<LoginOutlined />}
                                    onClick={handleLoginAndSave}
                                    loading={loggingIn}
                                    size="large"
                                    block
                                    className="login-btn hpo-action-btn"
                                >
                                    {loggingIn ? 'Đang đăng nhập...' : 'Đăng nhập HPO'}
                                </Button>
                                <Button
                                    danger
                                    onClick={handleLogout}
                                    block
                                    size="large"
                                    icon={<LogoutOutlined />}
                                    className="hpo-action-btn"
                                >
                                    Xóa phiên
                                </Button>
                            </div>

                            {sessionStatus?.is_logged_in && !sessionStatus?.checking && (
                                <div className="hpo-login-success-msg" role="status" aria-live="polite">
                                    ✅ Đăng nhập HPO thành công. Bạn có thể sử dụng các chức năng ở trang Tác vụ RPA.
                                </div>
                            )}
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
                        <div className="account-footer" style={{ padding: '24px 16px' }}>
                            <div style={{ textAlign: 'center', marginBottom: 20 }}>
                                {zaloSession.is_active ? (
                                    <Alert
                                        message="Kết nối Zalo thành công"
                                        description={`Đang hoạt động với tên: ${zaloSession.zalo_name}`}
                                        type="success"
                                        showIcon
                                    />
                                ) : (
                                    <Alert
                                        message="Zalo hiện chưa đăng nhập"
                                        description="Vui lòng bấm nút bên dưới và quét mã QR để bắt đầu gửi tin hoặc kết bạn."
                                        type="info"
                                        showIcon
                                    />
                                )}
                            </div>

                            {/* QR code hiển thị khi đang chờ đăng nhập */}
                            {!zaloSession.is_active && localQrBase64 && (
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


        </div>
    );
}

export default Dashboard;
