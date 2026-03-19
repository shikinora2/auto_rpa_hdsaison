import { useState, useEffect, useCallback } from 'react';
import {
    Card,
    Form,
    DatePicker,
    Input,
    Select,
    Button,
    message,
    Row,
    Col,
    Alert,
    Progress,
    Tag,
    Tooltip,
} from 'antd';
import {
    SearchOutlined,
    DownloadOutlined,
    FileExcelOutlined,
    FolderOpenOutlined,
    WarningOutlined,
    InfoCircleOutlined,
} from '@ant-design/icons';
import { configAPI, rpaAPI } from '../../services/api';
import './Tasks.css';

const { RangePicker } = DatePicker;

const TASK_MAP = {
    check_contracts: 'check',
    download_files: 'download',
    scrape_details: 'scrape',
};

const TASK_LABELS = {
    check_contracts: 'Kiểm tra HĐ',
    download_files: 'Tải file',
    scrape_details: 'Cào chi tiết',
};

function Tasks({ taskStatus, progress }) {
    const [form] = Form.useForm();
    const [loading, setLoading] = useState({ check: false, download: false, scrape: false });
    const [sessionStatus, setSessionStatus] = useState(null);
    const [currentTask, setCurrentTask] = useState(null);

    const checkSession = useCallback(async () => {
        // Fast path: trả về trạng thái cache, không mở browser (dùng khi trang load)
        try {
            const { data } = await rpaAPI.checkSession();
            setSessionStatus(data.is_logged_in);
        } catch (error) {
            console.debug('Failed to check session:', error);
            setSessionStatus(false);
        }
    }, []);

    const loadConfig = useCallback(async () => {
        try {
            const { data } = await configAPI.get();
            form.setFieldsValue({
                save_directory: data.save_directory || '',
                save_format: data.save_format || 'PDF',
            });
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }, [form]);

    useEffect(() => {
        loadConfig();
        checkSession();
    }, [loadConfig, checkSession]);

    useEffect(() => {
        if (!taskStatus) return;
        const task = taskStatus.data?.task;
        const st = taskStatus.status;

        if (st === 'running' && TASK_MAP[task]) {
            setCurrentTask(task);
        }
        if (st === 'completed' || st === 'error') {
            const key = TASK_MAP[task];
            if (key) setLoading(prev => ({ ...prev, [key]: false }));
            setCurrentTask(null);
        }
        if (st === 'stopping') {
            setLoading({ check: false, download: false, scrape: false });
            setCurrentTask(null);
        }
    }, [taskStatus]);

    const getFormData = () => {
        const values = form.getFieldsValue();
        const dates = values.date_range || [];
        return {
            start_date: dates[0] ? dates[0].format('DDMMYYYY') : '',
            end_date: dates[1] ? dates[1].format('DDMMYYYY') : '',
            save_directory: values.save_directory,
            save_format: values.save_format,
        };
    };

    const isAnyRunning = Object.values(loading).some(Boolean);

    const handleCheckContracts = async () => {
        const data = getFormData();
        if (!data.start_date || !data.end_date) {
            message.warning('Vui lòng chọn khoảng thời gian');
            return;
        }
        setLoading(prev => ({ ...prev, check: true }));
        try {
            await rpaAPI.checkContracts(data);
            message.success('Đã bắt đầu kiểm tra hợp đồng');
        } catch (error) {
            message.error(error.response?.data?.detail || 'Không thể bắt đầu kiểm tra');
            setLoading(prev => ({ ...prev, check: false }));
        }
    };

    const handleDownloadFiles = async () => {
        const data = getFormData();
        if (!data.start_date || !data.end_date) {
            message.warning('Vui lòng chọn khoảng thời gian');
            return;
        }
        if (!data.save_directory) {
            message.warning('Vui lòng nhập thư mục lưu file');
            return;
        }
        setLoading(prev => ({ ...prev, download: true }));
        try {
            await rpaAPI.downloadFiles(data);
            message.success('Đã bắt đầu tải file');
        } catch (error) {
            message.error(error.response?.data?.detail || 'Không thể bắt đầu tải');
            setLoading(prev => ({ ...prev, download: false }));
        }
    };

    const handleScrapeDetails = async () => {
        const data = getFormData();
        if (!data.start_date || !data.end_date) {
            message.warning('Vui lòng chọn khoảng thời gian');
            return;
        }
        setLoading(prev => ({ ...prev, scrape: true }));
        try {
            await rpaAPI.scrapeDetails(data);
            message.success('Đã bắt đầu cào chi tiết');
        } catch (error) {
            message.error(error.response?.data?.detail || 'Không thể bắt đầu cào');
            setLoading(prev => ({ ...prev, scrape: false }));
        }
    };

    return (
        <div className="tasks-container">
            {/* Session Warning */}
            {sessionStatus === false && (
                <Alert
                    message="Chưa đăng nhập HPO — Vui lòng vào Trang Chủ để đăng nhập trước."
                    type="warning"
                    showIcon
                    icon={<WarningOutlined />}
                    style={{ marginBottom: 16 }}
                />
            )}

            {/* Running Progress Banner */}
            {currentTask && (
                <div className="task-running-banner">
                    <div className="task-running-left">
                        <Tag color="processing">{TASK_LABELS[currentTask]}</Tag>
                        <span className="task-running-msg">
                            {progress?.message || 'Đang xử lý...'}
                        </span>
                    </div>
                    {progress && (
                        <div className="task-running-right">
                            <Progress
                                percent={progress.percentage}
                                size="small"
                                status="active"
                                format={() => `${progress.current}/${progress.total}`}
                                strokeColor={{ from: '#868CFF', to: '#4318FF' }}
                                style={{ width: 200 }}
                            />
                        </div>
                    )}
                </div>
            )}

            <Card
                title={
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span>Tác vụ RPA</span>
                        {currentTask && (
                            <Tag color="blue">{TASK_LABELS[currentTask]}</Tag>
                        )}
                    </div>
                }
                className="tasks-card"
            >
                <Form form={form} layout="vertical" initialValues={{ save_format: 'PDF' }}>
                    <Row gutter={16}>
                        <Col xs={24} md={14}>
                            <Form.Item
                                name="date_range"
                                label="Khoảng thời gian lọc hợp đồng"
                                rules={[{ required: true, message: 'Vui lòng chọn thời gian' }]}
                            >
                                <RangePicker
                                    format="DD/MM/YYYY"
                                    style={{ width: '100%' }}
                                    size="large"
                                    placeholder={['Từ ngày', 'Đến ngày']}
                                />
                            </Form.Item>
                        </Col>
                        <Col xs={24} md={10}>
                            <Form.Item
                                name="save_format"
                                label={
                                    <span>
                                        Định dạng lưu&nbsp;
                                        <Tooltip title="Áp dụng cho tác vụ Tải file">
                                            <InfoCircleOutlined style={{ color: '#707eae' }} />
                                        </Tooltip>
                                    </span>
                                }
                            >
                                <Select size="large">
                                    <Select.Option value="PDF">PDF (file hợp đồng)</Select.Option>
                                    <Select.Option value="JSON">JSON (dữ liệu thô)</Select.Option>
                                </Select>
                            </Form.Item>
                        </Col>
                    </Row>

                    <Form.Item
                        name="save_directory"
                        label={
                            <span>
                                Thư mục lưu file&nbsp;
                                <Tooltip title="Cần thiết cho tác vụ Tải file và Cào chi tiết">
                                    <InfoCircleOutlined style={{ color: '#707eae' }} />
                                </Tooltip>
                            </span>
                        }
                    >
                        <Input
                            prefix={<FolderOpenOutlined />}
                            placeholder="VD: D:\Downloads\contracts"
                            size="large"
                        />
                    </Form.Item>

                    {/* Task Action Cards */}
                    <Row gutter={[16, 16]} className="task-action-row">
                        <Col xs={24} sm={8}>
                            <div className={`task-action-card ${loading.check ? 'task-action-card--active' : ''}`}>
                                <div className="task-action-icon task-action-icon--blue">
                                    <SearchOutlined />
                                </div>
                                <div className="task-action-info">
                                    <div className="task-action-title">Kiểm tra số lượng</div>
                                    <div className="task-action-desc">
                                        Đếm tổng số HĐ trong khoảng thời gian. Không tải file.
                                    </div>
                                </div>
                                <Button
                                    type="primary"
                                    icon={loading.check ? null : <SearchOutlined />}
                                    onClick={handleCheckContracts}
                                    loading={loading.check}
                                    disabled={isAnyRunning && !loading.check}
                                    block
                                    size="large"
                                    className="task-action-btn task-action-btn--blue"
                                >
                                    {loading.check ? 'Đang kiểm tra...' : 'Kiểm tra'}
                                </Button>
                            </div>
                        </Col>

                        <Col xs={24} sm={8}>
                            <div className={`task-action-card ${loading.download ? 'task-action-card--active' : ''}`}>
                                <div className="task-action-icon task-action-icon--green">
                                    <DownloadOutlined />
                                </div>
                                <div className="task-action-info">
                                    <div className="task-action-title">Tải file PDF / JSON</div>
                                    <div className="task-action-desc">
                                        Tải từng hợp đồng về máy theo định dạng đã chọn. Cần nhập thư mục.
                                    </div>
                                </div>
                                <Button
                                    icon={loading.download ? null : <DownloadOutlined />}
                                    onClick={handleDownloadFiles}
                                    loading={loading.download}
                                    disabled={isAnyRunning && !loading.download}
                                    block
                                    size="large"
                                    className="task-action-btn task-action-btn--green"
                                >
                                    {loading.download ? 'Đang tải...' : 'Tải file'}
                                </Button>
                            </div>
                        </Col>

                        <Col xs={24} sm={8}>
                            <div className={`task-action-card ${loading.scrape ? 'task-action-card--active' : ''}`}>
                                <div className="task-action-icon task-action-icon--purple">
                                    <FileExcelOutlined />
                                </div>
                                <div className="task-action-info">
                                    <div className="task-action-title">Cào chi tiết → Excel</div>
                                    <div className="task-action-desc">
                                        Thu thập chi tiết từng HĐ và xuất ra file Excel. Cần nhập thư mục.
                                    </div>
                                </div>
                                <Button
                                    icon={loading.scrape ? null : <FileExcelOutlined />}
                                    onClick={handleScrapeDetails}
                                    loading={loading.scrape}
                                    disabled={isAnyRunning && !loading.scrape}
                                    block
                                    size="large"
                                    className="task-action-btn task-action-btn--excel"
                                >
                                    {loading.scrape ? 'Đang cào...' : 'Cào → Excel'}
                                </Button>
                            </div>
                        </Col>
                    </Row>
                </Form>
            </Card>
        </div>
    );
}

export default Tasks;
