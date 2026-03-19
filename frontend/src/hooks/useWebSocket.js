import { useState, useEffect, useCallback, useRef } from 'react';
import { WS_BASE_URL } from '../services/api';

const WS_URL = WS_BASE_URL + '/ws/logs';

/**
 * Custom hook để quản lý WebSocket connection
 * Tự động kết nối, reconnect khi mất kết nối
 */
export function useWebSocket() {
    const [logs, setLogs] = useState([]);
    const [status, setStatus] = useState('disconnected'); // disconnected, connecting, connected
    const [progress, setProgress] = useState(null); // { current, total, percentage, message }
    const [taskStatus, setTaskStatus] = useState(null); // { status, task, data }
    const [qrImage, setQrImage] = useState(null); // { qr_base64 }

    const wsRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);
    const pingIntervalRef = useRef(null);
    const reconnectFnRef = useRef(() => {});

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        setStatus('connecting');

        try {
            wsRef.current = new WebSocket(WS_URL);

            wsRef.current.onopen = () => {
                console.log('WebSocket connected');
                setStatus('connected');

                // Ping mỗi 30 giây để giữ kết nối
                pingIntervalRef.current = setInterval(() => {
                    if (wsRef.current?.readyState === WebSocket.OPEN) {
                        wsRef.current.send('ping');
                    }
                }, 30000);
            };

            wsRef.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    switch (data.type) {
                        case 'log':
                            setLogs(prev => {
                                const last = prev[prev.length - 1];
                                const isDup = last
                                    && last.type === data.type
                                    && last.timestamp === data.timestamp
                                    && last.level === data.level
                                    && last.message === data.message;
                                if (isDup) return prev;
                                return [...prev.slice(-999), data]; // Giữ tối đa 1000 logs
                            });
                            break;

                        case 'history':
                            // Nhận log history từ server khi kết nối
                            setLogs(data.data || []);
                            break;

                        case 'progress':
                            setProgress(data);
                            break;

                        case 'status':
                            setTaskStatus(data);
                            // Clear QR when login completes or errors
                            if (data.status === 'active' || data.status === 'completed' || data.status === 'error' || data.status === 'stopping') {
                                setQrImage(null);
                            }
                            break;

                        case 'qr_image':
                            setQrImage({ qr_base64: data.qr_base64 });
                            break;

                        default:
                            console.log('Unknown message type:', data);
                    }
                } catch (e) {
                    // Có thể là pong response
                    if (event.data !== 'pong') {
                        console.warn('Failed to parse WebSocket message:', e);
                    }
                }
            };

            wsRef.current.onclose = () => {
                console.log('WebSocket disconnected');
                setStatus('disconnected');
                clearInterval(pingIntervalRef.current);

                // Auto reconnect sau 3 giây
                reconnectTimeoutRef.current = setTimeout(() => {
                    reconnectFnRef.current();
                }, 3000);
            };

            wsRef.current.onerror = (error) => {
                console.error('WebSocket error:', error);
                wsRef.current?.close();
            };

        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            setStatus('disconnected');

            // Retry sau 5 giây
            reconnectTimeoutRef.current = setTimeout(() => {
                reconnectFnRef.current();
            }, 5000);
        }
    }, []);

    useEffect(() => {
        reconnectFnRef.current = connect;
    }, [connect]);

    const disconnect = useCallback(() => {
        clearTimeout(reconnectTimeoutRef.current);
        clearInterval(pingIntervalRef.current);

        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }

        setStatus('disconnected');
    }, []);

    const clearLogs = useCallback(() => {
        setLogs([]);
        setProgress(null);
    }, []);

    // Auto connect khi mount
    useEffect(() => {
        connect();

        return () => {
            disconnect();
        };
    }, [connect, disconnect]);

    return {
        logs,
        status,
        progress,
        taskStatus,
        qrImage,
        connect,
        disconnect,
        clearLogs,
        isConnected: status === 'connected',
    };
}

export default useWebSocket;
