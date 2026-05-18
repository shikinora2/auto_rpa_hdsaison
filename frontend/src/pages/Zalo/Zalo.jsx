import { useState, useEffect, useRef, useCallback } from 'react';
import {
    Card,
    Button,
    message,
    Table,
    Tag,
    Upload,
    Input,
    Row,
    Col,
    Alert,
    Tabs,
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
import useUserPersistentState from '../../hooks/useUserPersistentState';
import './Zalo.css';

const { TextArea } = Input;

const TEMPLATE_VARIABLES = [
    { label: 'Tên khách hàng', value: '{name}' },
    { label: 'Anh/Chị', value: '{gender}' },
    { label: 'Số điện thoại', value: '{phone}' },
    { label: 'Mã hợp đồng', value: '{contract_id}' },
    { label: 'Sản phẩm', value: '{san_pham}' },
    { label: 'Tên nhân viên', value: '{my_name}' },
    { label: 'Địa chỉ', value: '{address}' },
    { label: 'Số CCCD', value: '{cccd}' },
    { label: 'Ngày sinh', value: '{dob}' },
];

const FRIEND_STATUS_META = {
    pending: { label: 'Đang xử lý', color: 'processing' },
    success: { label: 'Kết bạn thành công', color: 'success' },
    already_friend: { label: 'Đã là bạn bè', color: 'blue' },
    already_sent: { label: 'Đã gửi lời mời trước', color: 'gold' },
    failed: { label: 'Kết bạn thất bại', color: 'error' },
    rate_limited: { label: 'Bị giới hạn (chống spam)', color: 'volcano' },
    skipped: { label: 'Không thực hiện', color: 'default' },
    idle: { label: 'Chưa thao tác', color: 'default' },
};

const SEND_STATUS_META = {
    pending: { label: 'Đang xử lý', color: 'processing' },
    success: { label: 'Gửi tin thành công', color: 'success' },
    failed: { label: 'Gửi tin thất bại', color: 'error' },
    blocked: { label: 'Không gửi do bị giới hạn', color: 'volcano' },
    skipped: { label: 'Không thực hiện', color: 'default' },
    idle: { label: 'Chưa thao tác', color: 'default' },
};

function splitTaskStatus(taskStatusValue) {
    const code = taskStatusValue?.code;
    const text = String(taskStatusValue?.text || '').toLowerCase();

    if (!code) {
        return {
            friend: { code: 'idle', text: FRIEND_STATUS_META.idle.label },
            send: { code: 'idle', text: SEND_STATUS_META.idle.label },
        };
    }

    // Pending realtime
    if (code === 'pending') {
        if (text.includes('kết bạn + gửi')) {
            return {
                friend: { code: 'pending', text: 'Đang kết bạn...' },
                send: { code: 'pending', text: 'Đang chờ gửi tin...' },
            };
        }
        if (text.includes('kết bạn')) {
            return {
                friend: { code: 'pending', text: 'Đang kết bạn...' },
                send: { code: 'idle', text: SEND_STATUS_META.idle.label },
            };
        }
        return {
            friend: { code: 'idle', text: FRIEND_STATUS_META.idle.label },
            send: { code: 'pending', text: 'Đang gửi tin...' },
        };
    }

    // Combined flow: add friend + send message
    if (code === 'success_and_sent') {
        return {
            friend: { code: 'success', text: 'Kết bạn thành công' },
            send: { code: 'success', text: 'Gửi tin thành công' },
        };
    }
    if (code === 'already_friend_sent') {
        return {
            friend: { code: 'already_friend', text: 'Đã là bạn bè' },
            send: { code: 'success', text: 'Gửi tin thành công' },
        };
    }
    if (code === 'already_sent_and_sent') {
        return {
            friend: { code: 'already_sent', text: 'Đã gửi lời mời trước' },
            send: { code: 'success', text: 'Gửi tin thành công' },
        };
    }
    if (code === 'success_send_failed') {
        return {
            friend: { code: 'success', text: 'Kết bạn thành công' },
            send: { code: 'failed', text: 'Gửi tin thất bại' },
        };
    }
    if (code === 'already_friend_send_failed') {
        return {
            friend: { code: 'already_friend', text: 'Đã là bạn bè' },
            send: { code: 'failed', text: 'Gửi tin thất bại' },
        };
    }
    if (code === 'already_sent_send_failed') {
        return {
            friend: { code: 'already_sent', text: 'Đã gửi lời mời trước' },
            send: { code: 'failed', text: 'Gửi tin thất bại' },
        };
    }
    if (code === 'send_failed') {
        return {
            friend: { code: 'idle', text: FRIEND_STATUS_META.idle.label },
            send: { code: 'failed', text: 'Gửi tin thất bại' },
        };
    }

    if (code === 'rate_limited') {
        return {
            friend: { code: 'rate_limited', text: 'Bị giới hạn chống spam' },
            send: { code: 'blocked', text: 'Không gửi do bị giới hạn' },
        };
    }

    // Add-friend only flow
    if (code === 'success' || code === 'already_friend' || code === 'already_sent') {
        return {
            friend: { code, text: taskStatusValue?.text || FRIEND_STATUS_META[code]?.label },
            send: { code: 'idle', text: SEND_STATUS_META.idle.label },
        };
    }

    // Send-message only flow
    if (['success_friend', 'success_stranger', 'success_unknown'].includes(code)) {
        return {
            friend: { code: 'idle', text: FRIEND_STATUS_META.idle.label },
            send: { code: 'success', text: taskStatusValue?.text || 'Gửi tin thành công' },
        };
    }

    if (['not_registered', 'not_found', 'no_phone'].includes(code)) {
        return {
            friend: { code: 'idle', text: FRIEND_STATUS_META.idle.label },
            send: { code: 'failed', text: taskStatusValue?.text || 'Gửi tin thất bại' },
        };
    }

    return {
        friend: { code: 'failed', text: taskStatusValue?.text || 'Kết bạn thất bại' },
        send: { code: 'failed', text: taskStatusValue?.text || 'Gửi tin thất bại' },
    };
}

function renderStatusTag(status, metaMap) {
    const meta = metaMap[status?.code] || metaMap.idle;
    return <Tag color={meta.color}>{status?.text || meta.label}</Tag>;
}

function Zalo({ taskStatus, logs, progress, userStorageKey }) {
    const [session, setSession] = useState({ is_active: false });
    const [customers, setCustomers] = useUserPersistentState(userStorageKey, 'zalo.customers', []);
    const [messageTemplate, setMessageTemplate] = useUserPersistentState(userStorageKey, 'zalo.messageTemplate', '');
    const [greetingTemplate, setGreetingTemplate] = useUserPersistentState(userStorageKey, 'zalo.greetingTemplate', '');
    const [attachmentFilename, setAttachmentFilename] = useUserPersistentState(userStorageKey, 'zalo.attachmentFilename', '');
    const [activeComposeTab, setActiveComposeTab] = useState('message');
    const [uploadingAttachment, setUploadingAttachment] = useState(false);
    const [loading, setLoading] = useState({
        login: false,
        sendMessages: false,
        addFriends: false,
            });
    const pollRef = useRef(null);
    const messageInputRef = useRef(null);
    const greetingInputRef = useRef(null);
    const lastRealtimeLogRef = useRef('');
    const lastRealtimeProgressRef = useRef('');
    const isLocked = !session.is_active;

    const updateCustomerStatusByPhone = useCallback((phone, status) => {
        const normalizedPhone = String(phone || '').trim();
        if (!normalizedPhone) return;

        setCustomers(prev => prev.map(customer => (
            String(customer.phone || '').trim() === normalizedPhone
                ? { ...customer, taskStatus: status }
                : customer
        )));
    }, [setCustomers]);

    const getRunningTaskType = useCallback(() => {
        const task = taskStatus?.data?.task;
        const st = taskStatus?.status;
        if (!task || (st !== 'running' && st !== 'active' && st !== 'paused')) return null;
        if (task === 'add_friends' || task === 'send_messages') return task;
        return null;
    }, [taskStatus]);

    const markPendingStatus = (taskType) => {
        const pendingText = taskType === 'add_friends'
            ? 'Đang kết bạn...'
            : 'Đang nhắn tin...';
        setCustomers(prev => prev.map(customer => (
            String(customer.phone || '').trim()
                ? { ...customer, taskStatus: { code: 'pending', text: pendingText } }
                : customer
        )));
    };

    const applyTaskResultToCustomers = useCallback((taskType, resultData) => {
        let details = [];

        if (taskType === 'send_messages') {
            details = resultData?.results?.details || [];
        } else if (taskType === 'add_friends') {
            details = resultData?.results || [];
        }

        if (!Array.isArray(details) || details.length === 0) return;

        const byPhone = new Map();
        details.forEach(item => {
            const phone = String(item?.phone || '').trim();
            if (phone) byPhone.set(phone, item);
        });

        setCustomers(prev => prev.map(customer => {
            const phone = String(customer.phone || '').trim();
            if (!phone || !byPhone.has(phone)) return customer;

            const item = byPhone.get(phone);

            if (taskType === 'send_messages') {
                if (item.status === 'success') {
                    const friendStatus = item.friend_status || 'unknown';
                    return {
                        ...customer,
                        taskStatus: {
                            code: `success_${friendStatus}`,
                            text: friendStatus === 'friend'
                                ? 'Gửi tin thành công (Bạn bè)'
                                : friendStatus === 'stranger'
                                    ? 'Gửi tin thành công (Người lạ)'
                                    : 'Gửi tin thành công'
                        }
                    };
                }

                return {
                    ...customer,
                    taskStatus: {
                        code: item.status || 'failed',
                        text: item.status === 'not_registered'
                            ? 'Không thể tìm bằng số điện thoại'
                            : item.status === 'not_found'
                                ? 'Không tìm thấy tài khoản'
                                : item.status === 'no_phone'
                                    ? 'Thiếu số điện thoại'
                                    : 'Gửi tin thất bại'
                    }
                };
            }

            return {
                ...customer,
                taskStatus: {
                    code: item.status || 'failed',
                    text: item.status === 'success_and_sent'
                        ? 'Kết bạn + gửi tin thành công'
                        : item.status === 'already_friend_sent'
                            ? 'Đã là bạn, gửi tin thành công'
                            : item.status === 'already_sent_and_sent'
                                ? 'Đã gửi lời mời trước, gửi tin thành công'
                                : item.status === 'success_send_failed'
                                    ? 'Kết bạn xong, gửi tin thất bại'
                                    : item.status === 'already_friend_send_failed'
                                        ? 'Đã là bạn, gửi tin thất bại'
                                        : item.status === 'already_sent_send_failed'
                                            ? 'Đã gửi lời mời trước, gửi tin thất bại'
                                            : item.status === 'send_failed'
                                                ? 'Gửi tin thất bại'
                                                : item.status === 'rate_limited'
                        ? 'Zalo giới hạn tìm kiếm/kết bạn, tác vụ đã dừng'
                        : item.status === 'already_friend'
                        ? 'Đã là bạn bè'
                        : item.status === 'already_sent'
                            ? 'Đã gửi lời mời trước đó'
                            : item.status === 'success'
                                ? 'Đã gửi lời mời kết bạn'
                                : 'Kết bạn thất bại'
                }
            };
        }));
    }, [setCustomers]);

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
            setLoading({ login: false, sendMessages: false, addFriends: false,  });
            stopSessionPolling();
        }

        if (st === 'completed' && (task === 'send_messages' || task === 'add_friends')) {
            applyTaskResultToCustomers(task, taskStatus.data || {});
        }

        if (st === 'zalo_row_update') {
            applyTaskResultToCustomers(task, taskStatus.data || {});
        }

        if (st === 'error' && (task === 'send_messages' || task === 'add_friends')) {
            const taskLabel = task === 'add_friends'
                ? 'kết bạn'
                : 'nhắn tin';
            const errorText = String(taskStatus?.data?.error || '');
            const isRateLimited = /Tìm số điện thoại quá nhiều lần|hoạt động bất thường|Bạn hãy thử lại vào/i.test(errorText);
            setCustomers(prev => prev.map(customer => (
                customer.taskStatus?.code === 'pending'
                    ? {
                        ...customer,
                        taskStatus: {
                            code: isRateLimited ? 'rate_limited' : 'error',
                            text: isRateLimited
                                ? 'Zalo giới hạn tìm kiếm/kết bạn, tác vụ đã dừng'
                                : `Lỗi khi ${taskLabel}`,
                        }
                    }
                    : customer
            )));
        }

        // Gọi loadSession sau cả completed lẫn error để đảm bảo đồng bộ
        if (task === 'zalo_login' && (st === 'completed' || st === 'error')) {
            loadSession();
        }
    }, [taskStatus, applyTaskResultToCustomers, setCustomers]);

    useEffect(() => {
        const runningTask = getRunningTaskType();
        if (!runningTask || !progress?.message) return;

        const marker = `${progress.timestamp || ''}|${progress.current || ''}|${progress.total || ''}|${progress.message || ''}`;
        if (lastRealtimeProgressRef.current === marker) return;
        lastRealtimeProgressRef.current = marker;

        const phoneMatch = String(progress.message).match(/Đang xử lý:\s*([0-9]{8,15})/i);
        if (!phoneMatch) return;

        const phone = phoneMatch[1];
        updateCustomerStatusByPhone(phone, {
            code: 'pending',
            text: runningTask === 'add_friends'
                ? 'Đang kết bạn...'
                : 'Đang gửi tin nhắn...',
        });
    }, [progress, getRunningTaskType, updateCustomerStatusByPhone]);

    useEffect(() => {
        if (!Array.isArray(logs) || logs.length === 0) return;
        const runningTask = getRunningTaskType();
        if (!runningTask) return;

        const latest = logs[logs.length - 1];
        const text = String(latest?.message || '');
        const marker = `${latest?.timestamp || ''}|${latest?.level || ''}|${text}`;
        if (!text || lastRealtimeLogRef.current === marker) return;
        lastRealtimeLogRef.current = marker;

        const phoneMatch = text.match(/([0-9]{8,15})/);
        if (!phoneMatch) return;
        const phone = phoneMatch[1];

        if (runningTask === 'add_friends') {
            if (text.includes('Kết bạn thành công')) {
                updateCustomerStatusByPhone(
                    phone,
                    { code: 'success', text: 'Đã gửi lời mời kết bạn' }
                );
                return;
            }
            if (text.includes('Đã là bạn bè')) {
                updateCustomerStatusByPhone(phone, { code: 'already_friend', text: 'Đã là bạn bè' });
                return;
            }
            if (text.includes('Đã gửi lời mời')) {
                updateCustomerStatusByPhone(phone, { code: 'already_sent', text: 'Đã gửi lời mời trước đó' });
                return;
            }
            if (text.includes('Thất bại') || text.includes('Lỗi')) {
                updateCustomerStatusByPhone(phone, { code: 'failed', text: 'Kết bạn thất bại' });
            }
            return;
        }

        if (runningTask === 'send_messages') {
            if (text.includes('thành công')) {
                updateCustomerStatusByPhone(phone, { code: 'success_unknown', text: 'Gửi tin thành công' });
                return;
            }
            if (text.includes('chưa đăng ký')) {
                updateCustomerStatusByPhone(phone, { code: 'not_registered', text: 'SĐT chưa đăng ký hoặc không cho phép tìm' });
                return;
            }
            if (text.includes('Không tìm thấy') || text.includes('không tìm thấy')) {
                updateCustomerStatusByPhone(phone, { code: 'not_found', text: 'Không tìm thấy tài khoản' });
                return;
            }
            if (text.includes('Thất bại') || text.includes('Lỗi')) {
                updateCustomerStatusByPhone(phone, { code: 'failed', text: 'Gửi tin nhắn thất bại' });
            }
        }
    }, [logs, getRunningTaskType, updateCustomerStatusByPhone]);

    const loadSession = async () => {
        try {
            const { data } = await zaloAPI.getSession();
            setSession(data);
        } catch (error) {
            console.error('Failed to load session:', error);
        }
    };

    const handleUpload = async (info) => {
        if (isLocked) {
            message.warning('Trang Auto Zalo đang bị khóa. Vui lòng đăng nhập Zalo ở Trang Chủ trước.');
            return;
        }
        const file = info.file;
        try {
            const { data } = await filesAPI.parseExcel(file);
            const rows = (data.data || []).map((row, i) => ({ ...row, _key: i, taskStatus: null }));
            setCustomers(rows);
            const missing = rows.filter(r => !r.phone && !r.name);
            if (missing.length === rows.length && rows.length > 0) {
                message.warning(`Đã tải ${data.row_count} dòng nhưng không tìm thấy cột SĐT/Họ tên. Kiểm tra lại định dạng file.`);
            } else {
                message.success(`Đã tải ${data.row_count} khách hàng`);
            }
        } catch {
            message.error('Không thể đọc file Excel');
        }
    };

    const handleDeleteCustomer = (key) => {
        if (isLocked) {
            message.warning('Trang Auto Zalo đang bị khóa. Vui lòng đăng nhập Zalo ở Trang Chủ trước.');
            return;
        }
        setCustomers(prev => prev.filter(r => r._key !== key));
    };

    const handleDownloadTemplate = (mode = 'minimal') => {
        if (isLocked) {
            message.warning('Trang Auto Zalo đang bị khóa. Vui lòng đăng nhập Zalo ở Trang Chủ trước.');
            return;
        }
        window.open(filesAPI.templateUrl(mode), '_blank');
    };

    const handleUploadAttachment = async (info) => {
        if (isLocked) {
            message.warning('Trang Auto Zalo đang bị khóa. Vui lòng đăng nhập Zalo ở Trang Chủ trước.');
            return;
        }

        const file = info?.file?.originFileObj || info?.file;
        if (!file) {
            return;
        }

        setUploadingAttachment(true);
        try {
            const { data } = await filesAPI.upload(file);
            const uploadedName = String(data?.filename || '').trim();
            if (!uploadedName) {
                throw new Error('Không nhận được tên file từ server');
            }
            setAttachmentFilename(uploadedName);
            message.success('Đã tải ảnh đính kèm');
        } catch (error) {
            message.error(error?.response?.data?.detail || 'Không thể tải ảnh đính kèm');
        } finally {
            setUploadingAttachment(false);
        }
    };

    const clearAttachment = () => {
        if (isLocked) {
            message.warning('Trang Auto Zalo đang bị khóa. Vui lòng đăng nhập Zalo ở Trang Chủ trước.');
            return;
        }
        setAttachmentFilename('');
    };

    const insertTemplateVariable = (variable) => {
        if (isLocked) {
            message.warning('Trang Auto Zalo đang bị khóa. Vui lòng đăng nhập Zalo ở Trang Chủ trước.');
            return;
        }
        const isInviteTab = activeComposeTab === 'invite';
        const textarea = isInviteTab
            ? greetingInputRef.current?.resizableTextArea?.textArea
            : messageInputRef.current?.resizableTextArea?.textArea;
        const value = isInviteTab ? greetingTemplate : messageTemplate;
        const setValue = isInviteTab ? setGreetingTemplate : setMessageTemplate;
        const maxLen = isInviteTab ? 150 : null;

        if (!textarea) {
            setValue(prev => {
                const next = `${prev}${prev ? ' ' : ''}${variable}`;
                return maxLen ? next.slice(0, maxLen) : next;
            });
            return;
        }

        const selectionStart = textarea.selectionStart ?? value.length;
        const selectionEnd = textarea.selectionEnd ?? value.length;
        let nextValue =
            value.slice(0, selectionStart) +
            variable +
            value.slice(selectionEnd);

        if (maxLen && nextValue.length > maxLen) {
            nextValue = nextValue.slice(0, maxLen);
        }

        setValue(nextValue);

        window.requestAnimationFrame(() => {
            textarea.focus();
            const cursorPosition = Math.min(selectionStart + variable.length, nextValue.length);
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
        markPendingStatus('send_messages');
        try {
            const payload = validCustomers.map((customer) => {
                const next = { ...customer };
                delete next._key;
                return next;
            });
            await zaloAPI.sendMessages({
                customers: payload,
                message_template: messageTemplate,
                check_friend_status: true,
                attachment_filename: attachmentFilename || null,
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
        markPendingStatus('add_friends');
        try {
            const payload = validCustomers.map((customer) => {
                const next = { ...customer };
                delete next._key;
                return next;
            });
            await zaloAPI.addFriends({
                customers: payload,
                greeting_template: greetingTemplate
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
        { title: 'Tên', dataIndex: 'name', key: 'name', width: 220 },
        { title: 'Mã HĐ', dataIndex: 'contract_id', key: 'contract_id', width: 160 },
        {
            title: 'Kết bạn',
            key: 'friendStatus',
            dataIndex: 'taskStatus',
            width: 210,
            render: (taskStatusValue) => {
                const split = splitTaskStatus(taskStatusValue);
                return renderStatusTag(split.friend, FRIEND_STATUS_META);
            }
        },
        {
            title: 'Gửi tin',
            key: 'sendStatus',
            dataIndex: 'taskStatus',
            width: 210,
            render: (taskStatusValue) => {
                const split = splitTaskStatus(taskStatusValue);
                return renderStatusTag(split.send, SEND_STATUS_META);
            }
        },
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
                    disabled={isLocked}
                />
            ),
        },
    ];

    return (
        <div className="zalo-container">
            {isLocked && (
                <Alert
                    message="Chưa đăng nhập Zalo"
                    description="Vui lòng đăng nhập Zalo ở Trang Chủ trước. Các chức năng Auto Zalo đang bị khóa."
                    type="warning"
                    showIcon
                    style={{ marginBottom: 16 }}
                />
            )}
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
                                    onClick={() => handleDownloadTemplate('minimal')}
                                    className="template-btn"
                                    disabled={isLocked}
                                >
                                    Tải mẫu Excel (STT, Họ tên, SĐT)
                                </Button>
                                <Button
                                    icon={<DownloadOutlined />}
                                    onClick={() => handleDownloadTemplate('full')}
                                    className="template-btn"
                                    disabled={isLocked}
                                >
                                    Mẫu đầy đủ (tùy chọn)
                                </Button>
                                <Upload
                                    accept=".xlsx,.xls"
                                    showUploadList={false}
                                    beforeUpload={() => false}
                                    onChange={handleUpload}
                                    disabled={isLocked}
                                >
                                    <Button icon={<FileExcelOutlined />} type="primary" disabled={isLocked}>
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
                            scroll={{ y: 420, x: 980 }}
                            pagination={{ pageSize: 50, size: 'small', showTotal: (total) => `${total} khách hàng` }}
                        />
                    </Card>
                </Col>

                {/* Soạn nội dung */}
                <Col xs={24}>
                    <Card title="Soạn nội dung" className="message-card">
                        <Tabs
                            size="small"
                            activeKey={activeComposeTab}
                            onChange={setActiveComposeTab}
                            items={[
                                {
                                    key: 'message',
                                    label: 'Soạn tin nhắn',
                                    children: (
                                        <>
                                            <div className="template-variable-toolbar">
                                                <div className="template-variable-label">Chèn nhanh thông tin:</div>
                                                <div className="template-variable-buttons">
                                                    {TEMPLATE_VARIABLES.map(item => (
                                                        <Button
                                                            key={item.value}
                                                            size="small"
                                                            className="template-variable-btn"
                                                            onClick={() => insertTemplateVariable(item.value)}
                                                            disabled={isLocked}
                                                        >
                                                            {item.label}
                                                        </Button>
                                                    ))}
                                                </div>
                                            </div>
                                            <TextArea
                                                ref={messageInputRef}
                                                rows={4}
                                                placeholder="Nhập nội dung tin nhắn. Sử dụng các nút {name}, {gender}, {contract_id}, {san_pham}... để chèn nhanh thông tin khách hàng"
                                                value={messageTemplate}
                                                onChange={(e) => setMessageTemplate(e.target.value)}
                                                disabled={isLocked}
                                            />
                                            <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                                <Upload
                                                    accept=".png,.jpg,.jpeg,.webp,.gif,image/png,image/jpeg,image/webp,image/gif"
                                                    showUploadList={false}
                                                    beforeUpload={() => false}
                                                    onChange={handleUploadAttachment}
                                                    disabled={isLocked || uploadingAttachment}
                                                >
                                                    <Button
                                                        icon={<UploadOutlined />}
                                                        loading={uploadingAttachment}
                                                        disabled={isLocked || uploadingAttachment}
                                                    >
                                                        Đính kèm ảnh
                                                    </Button>
                                                </Upload>
                                                {attachmentFilename && (
                                                    <>
                                                        <span style={{ color: '#1677ff' }}>Ảnh đã chọn: {attachmentFilename}</span>
                                                        <Button
                                                            size="small"
                                                            icon={<DeleteOutlined />}
                                                            onClick={clearAttachment}
                                                            disabled={isLocked || uploadingAttachment}
                                                        >
                                                            Xóa ảnh
                                                        </Button>
                                                    </>
                                                )}
                                            </div>
                                            <div className="template-variable-hint">
                                                Nội dung này dùng cho nút Gửi tin nhắn hàng loạt và Kết bạn rồi gửi nội dung tin nhắn.
                                            </div>
                                        </>
                                    ),
                                },
                                {
                                    key: 'invite',
                                    label: 'Nội dung lời mời kết bạn',
                                    children: (
                                        <>
                                            <div className="template-variable-toolbar">
                                                <div className="template-variable-label">Chèn nhanh thông tin:</div>
                                                <div className="template-variable-buttons">
                                                    {TEMPLATE_VARIABLES.map(item => (
                                                        <Button
                                                            key={`invite-${item.value}`}
                                                            size="small"
                                                            className="template-variable-btn"
                                                            onClick={() => insertTemplateVariable(item.value)}
                                                            disabled={isLocked}
                                                        >
                                                            {item.label}
                                                        </Button>
                                                    ))}
                                                </div>
                                            </div>
                                            <TextArea
                                                ref={greetingInputRef}
                                                rows={3}
                                                maxLength={150}
                                                showCount
                                                placeholder="Nhập nội dung lời mời kết bạn (tối đa 150 ký tự)"
                                                value={greetingTemplate}
                                                onChange={(e) => setGreetingTemplate(e.target.value.slice(0, 150))}
                                                disabled={isLocked}
                                            />
                                            <div className="template-variable-hint">
                                                Nội dung này chỉ dùng cho thao tác kết bạn. Tối đa 150 ký tự.
                                            </div>
                                        </>
                                    ),
                                },
                            ]}
                        />
                        <div className="zalo-actions">
                            <Button
                                type="primary"
                                icon={<SendOutlined />}
                                onClick={handleSendMessages}
                                loading={loading.sendMessages}
                                disabled={isLocked}
                                size="large"
                                className="send-btn"
                            >
                                Gửi tin nhắn hàng loạt
                            </Button>
                            <Button
                                icon={<UserAddOutlined />}
                                onClick={handleAddFriends}
                                loading={loading.addFriends}
                                disabled={isLocked}
                                size="large"
                                className="friend-btn"
                            >
                                Kết bạn hàng loạt
                            </Button>
                            <Button
                                type="default"
                                icon={<UserAddOutlined />}
                                onClick={handleAddFriendsAndSend}
                                loading={loading.addFriendsAndSend}
                                disabled={isLocked}
                                size="large"
                                className="friend-btn"
                            >
                                Kết bạn rồi gửi nội dung tin nhắn
                            </Button>
                        </div>
                    </Card>
                </Col>
            </Row>


        </div>
    );
}

export default Zalo;
