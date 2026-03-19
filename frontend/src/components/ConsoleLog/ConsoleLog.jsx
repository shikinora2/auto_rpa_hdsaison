import { useEffect, useRef } from 'react';
import { Badge } from 'antd';
import {
    CheckCircleOutlined,
    InfoCircleOutlined,
    WarningOutlined,
    CloseCircleOutlined,
    ClearOutlined,
    WifiOutlined,
    DisconnectOutlined
} from '@ant-design/icons';
import './ConsoleLog.css';

/**
 * Component hiển thị log realtime từ WebSocket
 */
function ConsoleLog({ logs = [], status = 'disconnected', onClear, progress }) {
    const logContainerRef = useRef(null);

    // Auto scroll xuống khi có log mới
    useEffect(() => {
        if (logContainerRef.current) {
            logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        }
    }, [logs]);

    const getLevelIcon = (level) => {
        switch (level) {
            case 'success':
                return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
            case 'warning':
                return <WarningOutlined style={{ color: '#faad14' }} />;
            case 'error':
                return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
            default:
                return <InfoCircleOutlined style={{ color: '#1890ff' }} />;
        }
    };

    const getLevelClass = (level) => {
        return `log-entry log-${level || 'info'}`;
    };

    const formatTime = (timestamp) => {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleTimeString('vi-VN');
    };

    return (
        <div className="console-log-container">
            <div className="console-header">
                <div className="console-title">
                    <span>Console Log</span>
                    <Badge
                        status={status === 'connected' ? 'success' : status === 'connecting' ? 'processing' : 'error'}
                        text={status === 'connected' ? 'Đã kết nối' : status === 'connecting' ? 'Đang kết nối...' : 'Mất kết nối'}
                    />
                </div>
                <div className="console-actions">
                    {progress && (
                        <span className="progress-text">
                            {progress.current}/{progress.total} ({progress.percentage}%)
                        </span>
                    )}
                    <button className="clear-btn" onClick={onClear} title="Xóa log">
                        <ClearOutlined />
                    </button>
                </div>
            </div>

            <div className="console-body" ref={logContainerRef}>
                {logs.length === 0 ? (
                    <div className="empty-log">
                        <DisconnectOutlined style={{ fontSize: 24, marginBottom: 8 }} />
                        <p>Chưa có log nào. Bắt đầu một tác vụ để xem log.</p>
                    </div>
                ) : (
                    logs.map((log, index) => (
                        <div key={index} className={getLevelClass(log.level)}>
                            <span className="log-time">{formatTime(log.timestamp)}</span>
                            <span className="log-icon">{getLevelIcon(log.level)}</span>
                            <span className="log-message">{log.message}</span>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

export default ConsoleLog;
