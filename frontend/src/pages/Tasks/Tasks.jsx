import { useState, useEffect, useCallback, useRef } from 'react';
import dayjs from 'dayjs';
import {
    Card,
    Form,
    DatePicker,
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
    WarningOutlined,
    InfoCircleOutlined,
} from '@ant-design/icons';
import { configAPI, rpaAPI, filesAPI } from '../../services/api';
import useUserPersistentState from '../../hooks/useUserPersistentState';
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
    scrape_details: 'Lấy dữ liệu hợp đồng',
};

function Tasks({ taskStatus, progress, userStorageKey, sessionStatus: sharedSessionStatus }) {
    const [form] = Form.useForm();
    const [loading, setLoading] = useState({ check: false, download: false, scrape: false });
    const [sessionStatus, setSessionStatus] = useState(null);
    const [currentTask, setCurrentTask] = useState(null);
    const [completedProgress, setCompletedProgress] = useState(null);
    const downloadedArtifactsRef = useRef(new Set());
    const restoredFormRef = useRef(false);
    const [persistedTaskForm, setPersistedTaskForm] = useUserPersistentState(userStorageKey, 'tasks.form', {
        start_date: '',
        end_date: '',
        save_format: 'PDF',
    });

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
                save_format: persistedTaskForm.save_format || data.save_format || 'PDF',
            });
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }, [form, persistedTaskForm.save_format]);

    const triggerArtifactDownload = useCallback((artifactFilename) => {
        if (!artifactFilename) return;

        const uniqueKey = artifactFilename;
        if (downloadedArtifactsRef.current.has(uniqueKey)) return;
        downloadedArtifactsRef.current.add(uniqueKey);

        const url = filesAPI.download(artifactFilename, 'downloads');
        const link = document.createElement('a');
        link.href = url;
        link.download = artifactFilename;
        link.target = '_blank';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        message.success(`Đã tạo file kết quả và bắt đầu tải về: ${artifactFilename}`);
    }, []);

    useEffect(() => {
        loadConfig();
        checkSession();
    }, [loadConfig, checkSession]);

    useEffect(() => {
        if (restoredFormRef.current) return;
        restoredFormRef.current = true;

        const values = {
            save_format: persistedTaskForm.save_format || 'PDF',
        };

        if (persistedTaskForm.start_date && persistedTaskForm.end_date) {
            values.date_range = [
                dayjs(persistedTaskForm.start_date, 'DDMMYYYY'),
                dayjs(persistedTaskForm.end_date, 'DDMMYYYY'),
            ];
        }

        form.setFieldsValue(values);
    }, [form, persistedTaskForm]);

    useEffect(() => {
        if (!taskStatus) return;
        const task = taskStatus.data?.task;
        const st = taskStatus.status;

        if (st === 'running' && TASK_MAP[task]) {
            setCurrentTask(task);
            setCompletedProgress(null);
        }
        if (st === 'completed' || st === 'error') {
            const key = TASK_MAP[task];
            if (key) setLoading(prev => ({ ...prev, [key]: false }));
            setCurrentTask(null);

            if (st === 'completed' && TASK_MAP[task]) {
                const summary = taskStatus.data?.progress_summary;
                if (summary && Number(summary.total) > 0) {
                    setCompletedProgress({
                        task,
                        current: Number(summary.current || summary.total),
                        total: Number(summary.total),
                        percentage: Number(summary.percentage || 100),
                        message: summary.message || `Hoàn tất quét ${summary.total}/${summary.total} hợp đồng`,
                    });
                } else {
                    setCompletedProgress({
                        task,
                        current: 0,
                        total: 0,
                        percentage: 100,
                        message: 'Tác vụ đã hoàn tất',
                    });
                }
            }

            if (st === 'error' && TASK_MAP[task]) {
                setCompletedProgress(null);
            }

            const artifactFilename = taskStatus.data?.artifact_filename;
            if (st === 'completed' && (task === 'download_files' || task === 'scrape_details') && artifactFilename) {
                triggerArtifactDownload(artifactFilename);
            }
        }
        if (st === 'stopping') {
            setLoading({ check: false, download: false, scrape: false });
            setCurrentTask(null);
            setCompletedProgress(null);
        }
    }, [taskStatus, triggerArtifactDownload]);

    const getFormData = () => {
        const values = form.getFieldsValue();
        const dates = values.date_range || [];
        return {
            start_date: dates[0] ? dates[0].format('DDMMYYYY') : '',
            end_date: dates[1] ? dates[1].format('DDMMYYYY') : '',
            save_format: values.save_format,
        };
    };

    const isAnyRunning = Object.values(loading).some(Boolean);
    const hasSharedSession = typeof sharedSessionStatus?.is_logged_in === 'boolean';
    const isSessionChecking = hasSharedSession ? Boolean(sharedSessionStatus?.checking) : sessionStatus === null;
    const resolvedSessionLoggedIn = hasSharedSession ? sharedSessionStatus.is_logged_in : sessionStatus;
    const isLocked = resolvedSessionLoggedIn !== true;

    const handleCheckContracts = async () => {
        if (isLocked) {
            message.warning('Trang tác vụ đang bị khóa. Vui lòng đăng nhập HPO ở Trang Chủ trước.');
            return;
        }
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
        if (isLocked) {
            message.warning('Trang tác vụ đang bị khóa. Vui lòng đăng nhập HPO ở Trang Chủ trước.');
            return;
        }
        const data = getFormData();
        if (!data.start_date || !data.end_date) {
            message.warning('Vui lòng chọn khoảng thời gian');
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
        if (isLocked) {
            message.warning('Trang tác vụ đang bị khóa. Vui lòng đăng nhập HPO ở Trang Chủ trước.');
            return;
        }
        const data = getFormData();
        if (!data.start_date || !data.end_date) {
            message.warning('Vui lòng chọn khoảng thời gian');
            return;
        }
        setLoading(prev => ({ ...prev, scrape: true }));
        try {
            await rpaAPI.scrapeDetails(data);
            message.success('Đã bắt đầu lấy dữ liệu hợp đồng');
        } catch (error) {
            message.error(error.response?.data?.detail || 'Không thể bắt đầu lấy dữ liệu hợp đồng');
            setLoading(prev => ({ ...prev, scrape: false }));
        }
    };

    return (
        <div className="tasks-container">
            {/* Session Warning */}
            {!isSessionChecking && resolvedSessionLoggedIn === false && (
                <Alert
                    message="Chưa đăng nhập HPO — Vui lòng vào Trang Chủ để đăng nhập trước."
                    description="Các chức năng ở trang Tác vụ RPA sẽ bị khóa cho đến khi đăng nhập thành công."
                    type="warning"
                    showIcon
                    icon={<WarningOutlined />}
                    style={{ marginBottom: 16 }}
                />
            )}

            {/* Running/Completed Progress Banner */}
            {(currentTask || completedProgress) && (
                <div className="task-running-banner">
                    <div className="task-running-left">
                        <Tag color={currentTask ? 'processing' : 'success'}>
                            {TASK_LABELS[currentTask || completedProgress?.task]}
                        </Tag>
                        <span className="task-running-msg">
                            {currentTask
                                ? (progress?.message || 'Đang xử lý...')
                                : (completedProgress?.message || 'Hoàn tất')}
                        </span>
                    </div>
                    {(currentTask ? progress : completedProgress) && (
                        <div className="task-running-right">
                            <Progress
                                percent={currentTask ? progress.percentage : completedProgress.percentage}
                                size="small"
                                status={currentTask ? 'active' : 'success'}
                                format={() => {
                                    const p = currentTask ? progress : completedProgress;
                                    const current = Number(p?.current || 0);
                                    const total = Number(p?.total || 0);
                                    return total > 0 ? `${current}/${total}` : `${Math.round(Number(p?.percentage || 0))}%`;
                                }}
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
                <Form
                    form={form}
                    layout="vertical"
                    initialValues={{ save_format: 'PDF' }}
                    disabled={isLocked}
                    onValuesChange={(_, allValues) => {
                        const range = allValues.date_range || [];
                        setPersistedTaskForm({
                            start_date: range[0] ? range[0].format('DDMMYYYY') : '',
                            end_date: range[1] ? range[1].format('DDMMYYYY') : '',
                            save_format: allValues.save_format || 'PDF',
                        });
                    }}
                >
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
                                    disabled={isLocked || (isAnyRunning && !loading.check)}
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
                                        Tải từng hợp đồng theo định dạng đã chọn. Hệ thống tự lưu và tự tải file kết quả.
                                    </div>
                                </div>
                                <Button
                                    icon={loading.download ? null : <DownloadOutlined />}
                                    onClick={handleDownloadFiles}
                                    loading={loading.download}
                                    disabled={isLocked || (isAnyRunning && !loading.download)}
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
                                    <div className="task-action-title">Lấy dữ liệu hợp đồng → Excel</div>
                                    <div className="task-action-desc">
                                        Thu thập chi tiết từng HĐ và xuất Excel. Hệ thống tự lưu và tự tải file kết quả.
                                    </div>
                                </div>
                                <Button
                                    icon={loading.scrape ? null : <FileExcelOutlined />}
                                    onClick={handleScrapeDetails}
                                    loading={loading.scrape}
                                    disabled={isLocked || (isAnyRunning && !loading.scrape)}
                                    block
                                    size="large"
                                    className="task-action-btn task-action-btn--excel"
                                >
                                    {loading.scrape ? 'Đang lấy dữ liệu hợp đồng...' : 'Lấy dữ liệu → Excel'}
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
