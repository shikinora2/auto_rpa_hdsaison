import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Tabs, Form, Input, InputNumber, Switch, Button, Table, Tag,
  Space, Typography, Divider, message, Popconfirm, Badge, Alert,
  Tooltip, Upload, Progress, Checkbox,
} from 'antd';
import {
  MobileOutlined, SendOutlined, HistoryOutlined,
  SettingOutlined, CheckCircleOutlined, CloseCircleOutlined,
  DeleteOutlined, ReloadOutlined, WifiOutlined, PlusOutlined,
  MinusCircleOutlined, DownloadOutlined, FileExcelOutlined,
  PauseCircleOutlined, PlayCircleOutlined, StopOutlined,
} from '@ant-design/icons';
import { smsAPI, filesAPI } from '../../services/api';
import './SmsGateway.css';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

const TEMPLATE_VARIABLES = [
  { label: 'Tên KH', value: '{name}' },
  { label: 'Anh/Chị', value: '{gender}' },
  { label: 'SĐT', value: '{phone}' },
  { label: 'Mã HĐ', value: '{contract_id}' },
  { label: 'Số CCCD', value: '{cccd}' },
  { label: 'Địa chỉ', value: '{address}' },
];

// ─── Helpers ────────────────────────────────────────────
const TAG_COLOR = { sent: 'success', failed: 'error', pending: 'processing' };
const TAG_LABEL = { sent: 'Đã gửi', failed: 'Thất bại', pending: 'Đang gửi' };

function StatusBadge({ status }) {
  if (status === 'ok') return <Badge status="success" text="Đã kết nối" />;
  if (status === 'error') return <Badge status="error" text="Không kết nối" />;
  return <Badge status="default" text="Chưa kiểm tra" />;
}

// ─── Tab 1: Cấu hình ────────────────────────────────────
function ConfigTab() {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [pinging, setPinging] = useState(false);
  const [healthStatus, setHealthStatus] = useState(null); // null | { status, message }

  const checkHealthStatus = async () => {
    setPinging(true);
    setHealthStatus(null);
    try {
      const { data } = await smsAPI.health();
      setHealthStatus(data);
    } catch (err) {
      setHealthStatus({ status: 'error', message: err.response?.data?.detail || err.message });
    } finally {
      setPinging(false);
    }
  };

  useEffect(() => {
    smsAPI.getConfig().then(({ data }) => {
      if (data.success) {
        form.setFieldsValue(data.config);
        if (data.config.device_ip) {
          checkHealthStatus();
        }
      }
    }).catch(() => { });
  }, [form]);

  const handleSave = async (values) => {
    setSaving(true);
    try {
      await smsAPI.saveConfig(values);
      message.success('Đã lưu cấu hình SMS Gateway!');
      checkHealthStatus(); // Sau khi lưu, tự động ping lại ngay
    } catch (err) {
      message.error('Lưu cấu hình thất bại: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const handlePing = async () => {
    // Lưu tạm các values trên form trước khi ping nếu có sửa đổi
    const values = form.getFieldsValue();
    try {
      setSaving(true);
      await smsAPI.saveConfig(values);
      await checkHealthStatus();
      message.success('Đã gửi yêu cầu kiểm tra.');
    } catch (err) {
      message.error('Lưu để kiểm tra gặp lỗi.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="sms-tab-content">
      <div className="sms-section-header">
        <SettingOutlined className="sms-section-icon" />
        <span>Cấu hình kết nối Android Gateway</span>
      </div>

      <Alert
        className="sms-info-alert"
        type="info"
        showIcon
        message="Thông tin thiết bị hoạt động"
        description={
          <>
            <p style={{ margin: 0, marginBottom: 8 }}>
              Hệ thống hiện tại <b>chỉ hỗ trợ kết nối 1 thiết bị Android làm Gateway duy nhất</b> để đảm bảo tính đồng bộ của lịch sử SMS.
            </p>
            {healthStatus && (
              <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(0,0,0,0.2)', borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)' }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
                  <b style={{ marginRight: 8 }}>Trạng thái kết nối Gateway hiện tại:</b>
                  <StatusBadge status={healthStatus.status} />
                </div>
                <Text type={healthStatus.status === 'ok' ? 'success' : 'danger'}>
                  {healthStatus.message}
                </Text>
              </div>
            )}
            <Divider style={{ margin: '12px 0' }} />
            <ol style={{ margin: 0, paddingLeft: 16 }}>
              <li>Cài app <a href="https://github.com/capcom6/android-sms-gateway/releases" target="_blank" rel="noreferrer">Android SMS Gateway</a> lên điện thoại</li>
              <li>Bật <b>Local Server</b> trong app → ghi lại IP, port, username, password</li>
              <li>Đảm bảo máy tính và điện thoại <b>cùng mạng WiFi/LAN</b></li>
              <li>Nhập thông tin bên dưới → Lưu → Kiểm tra kết nối</li>
            </ol>
          </>
        }
      />

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={{ device_port: 8080, enabled: false }}
        className="sms-config-form"
      >
        <div className="sms-form-row">
          <Form.Item
            name="device_ip"
            label="IP Thiết bị Android"
            rules={[{ required: true, message: 'Nhập IP thiết bị' }]}
            className="sms-form-item-flex"
          >
            <Input
              prefix={<MobileOutlined />}
              placeholder="192.168.1.x"
              autoComplete="off"
            />
          </Form.Item>

          <Form.Item
            name="device_port"
            label="Port"
            rules={[{ required: true }]}
            style={{ width: 140, flexShrink: 0 }}
          >
            <InputNumber min={1} max={65535} style={{ width: '100%' }} />
          </Form.Item>
        </div>

        <div className="sms-form-row">
          <Form.Item
            name="username"
            label="Username"
            rules={[{ required: true, message: 'Nhập username' }]}
            className="sms-form-item-flex"
          >
            <Input prefix={<WifiOutlined />} placeholder="Username từ Gateway app" autoComplete="off" />
          </Form.Item>

          <Form.Item
            name="password"
            label="Password"
            rules={[{ required: true, message: 'Nhập password' }]}
            className="sms-form-item-flex"
          >
            <Input.Password placeholder="Password từ Gateway app" autoComplete="new-password" />
          </Form.Item>
        </div>

        <Form.Item name="enabled" label="Bật SMS Gateway" valuePropName="checked">
          <Switch checkedChildren="BẬT" unCheckedChildren="TẮT" />
        </Form.Item>

        <div className="sms-form-actions">
          <Button
            type="default"
            icon={<WifiOutlined />}
            loading={pinging}
            onClick={handlePing}
          >
            Kiểm tra kết nối
          </Button>
          <Button
            type="primary"
            htmlType="submit"
            loading={saving}
            icon={<CheckCircleOutlined />}
          >
            Lưu cấu hình
          </Button>
        </div>
      </Form>
    </div>
  );
}

// ─── Tab 2: Gửi SMS Hàng loạt ─────────────────────────────────────
function SendTab() {
  const [customers, setCustomers] = useState([]);
  const [messageTemplate, setMessageTemplate] = useState('');
  const [charCount, setCharCount] = useState(0);
  const [sendingState, setSendingState] = useState({ isSending: false, total: 0, current: 0 });
  const [isPaused, setIsPaused] = useState(false);

  // Cấu hình nâng cao
  const [delayConfig, setDelayConfig] = useState({ min: 1000, max: 3000 });
  const [addRandomChar, setAddRandomChar] = useState(false);

  // Refs để điều khiển vòng lặp async
  const messageInputRef = useRef(null);
  const isSendingRef = useRef(false);
  const isPausedRef = useRef(false);

  // Sync state -> ref
  useEffect(() => { isPausedRef.current = isPaused; }, [isPaused]);

  const handleUpload = async (info) => {
    const file = info.file;
    try {
      const { data } = await filesAPI.parseExcel(file);
      const rows = (data.data || []).map((row, i) => ({ ...row, _key: i }));
      setCustomers(rows);
      const valid = rows.filter(r => String(r.phone || '').trim());
      message.success(`Đã tải ${data.row_count} dữ liệu. Có ${valid.length} SĐT hợp lệ.`);
    } catch (error) {
      message.error('Không thể đọc file Excel');
    }
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
    setCharCount(nextValue.length);

    window.requestAnimationFrame(() => {
      textarea.focus();
      const cursorPosition = selectionStart + variable.length;
      textarea.setSelectionRange(cursorPosition, cursorPosition);
    });
  };

  const handleSendBatch = async () => {
    const validCustomers = customers.filter(c => String(c.phone || '').trim());
    if (validCustomers.length === 0) {
      message.warning('Không có số điện thoại nào hợp lệ trong danh sách');
      return;
    }
    if (!messageTemplate.trim()) {
      message.warning('Vui lòng nhập nội dung tin nhắn');
      return;
    }
    if (delayConfig.min > delayConfig.max) {
      message.warning('Độ trễ tối thiểu không được lớn hơn độ trễ tối đa');
      return;
    }

    setSendingState({ isSending: true, total: validCustomers.length, current: 0 });
    setIsPaused(false);
    isSendingRef.current = true;
    isPausedRef.current = false;
    let successCount = 0;

    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

    for (let i = 0; i < validCustomers.length; i++) {
      if (!isSendingRef.current) break; // Bị hủy

      // Kiểm tra trạng thái Tạm dừng
      while (isPausedRef.current) {
        if (!isSendingRef.current) break;
        await new Promise(r => setTimeout(r, 500));
      }
      if (!isSendingRef.current) break;

      const c = validCustomers[i];
      setSendingState(prev => ({ ...prev, current: i + 1 }));

      let text = messageTemplate
        .replace(/{name}/g, c.name || '')
        .replace(/{gender}/g, c.gender || '')
        .replace(/{phone}/g, c.phone || '')
        .replace(/{contract_id}/g, c.contract_id || '')
        .replace(/{cccd}/g, c.cccd || '')
        .replace(/{address}/g, c.address || '');

      if (addRandomChar) {
        const randChar = chars.charAt(Math.floor(Math.random() * chars.length));
        text += ` [${randChar}]`;
      }

      try {
        await smsAPI.send({
          phone_numbers: [c.phone],
          message: text,
        });
        successCount++;

        // Nghỉ ngơi giữa 2 lần gửi
        if (i < validCustomers.length - 1 && isSendingRef.current) {
          const delayTimeout = Math.floor(Math.random() * (delayConfig.max - delayConfig.min + 1)) + delayConfig.min;
          await new Promise(r => setTimeout(r, delayTimeout));
        }
      } catch (err) {
        console.error("Gửi SMS lỗi cho SĐT", c.phone, err);
      }
    }

    const wasCanceled = !isSendingRef.current;
    isSendingRef.current = false;
    setSendingState(prev => ({ ...prev, isSending: false }));
    setIsPaused(false);

    if (wasCanceled) {
      message.info(`Đã dừng gửi tin. Gửi thành công: ${successCount} tin.`);
    } else {
      message.success(`Đã hoàn tất gửi tin. Thành công: ${successCount}/${validCustomers.length}`);
    }
  };

  const handleStop = () => {
    isSendingRef.current = false;
    setIsPaused(false);
  };

  const customerColumns = [
    { title: 'STT', key: 'stt', width: 55, render: (_, __, i) => i + 1, align: 'center' },
    { title: 'Số điện thoại', dataIndex: 'phone', key: 'phone', width: 140 },
    { title: 'Tên', dataIndex: 'name', key: 'name' },
    { title: 'Mã HĐ', dataIndex: 'contract_id', key: 'contract_id' },
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
          onClick={() => setCustomers(prev => prev.filter(r => r._key !== record._key))}
        />
      ),
    },
  ];

  return (
    <div className="sms-tab-content" style={{ maxWidth: 800 }}>
      {/* Tải dữ liệu Khách hàng */}
      <div className="sms-section-header">
        <SendOutlined className="sms-section-icon" />
        <span>Gửi tin nhắn Hàng loạt từ File</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <b style={{ lineHeight: '32px' }}>
          Danh sách nhận tin {customers.length > 0 && `(${customers.length} khách)`}
        </b>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={handleDownloadTemplate} size="small">
            Tải mẫu Excel
          </Button>
          <Upload accept=".xlsx,.xls,.csv" showUploadList={false} beforeUpload={() => false} onChange={handleUpload}>
            <Button icon={<FileExcelOutlined />} type="primary" size="small">
              Tải lên danh sách
            </Button>
          </Upload>
        </Space>
      </div>

      <Table
        columns={customerColumns}
        dataSource={customers}
        rowKey={(r) => r._key}
        size="small"
        scroll={{ y: 250 }}
        pagination={false}
        className="sms-customers-table"
        locale={{ emptyText: 'Chưa có danh sách khách hàng' }}
      />

      <Divider style={{ margin: '16px 0' }} />

      {/* Trình soạn thảo SMS */}
      <div style={{ marginBottom: 12 }}>
        <b>Soạn nội dung gửi:</b>
        <div className="template-variable-buttons" style={{ marginTop: 8, marginBottom: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {TEMPLATE_VARIABLES.map(item => (
            <Tag
              color="blue"
              key={item.value}
              style={{ cursor: 'pointer', padding: '4px 8px', fontSize: 13 }}
              onClick={() => insertTemplateVariable(item.value)}
            >
              <PlusOutlined style={{ marginRight: 4 }} />{item.label}
            </Tag>
          ))}
        </div>
      </div>

      <div style={{ position: 'relative', marginBottom: 16 }}>
        <span className={`sms-char-count ${charCount > 160 ? 'warn' : ''}`} style={{ position: 'absolute', right: 8, top: -24, fontSize: 12, color: '#888' }}>
          {charCount}/160 ký tự {charCount > 160 && '(đa phần)'}
        </span>
        <TextArea
          ref={messageInputRef}
          rows={5}
          disabled={sendingState.isSending}
          placeholder="[HD Saison] Chao {gender} {name}, chuc mung ho so {contract_id} da duoc duyet..."
          value={messageTemplate}
          onChange={(e) => {
            setMessageTemplate(e.target.value);
            setCharCount(e.target.value.length);
          }}
          style={{ background: '#141414', color: '#e0e0e0', borderColor: '#434343' }}
        />
      </div>

      {/* Cấu hình gửi nâng cao */}
      <div style={{ padding: '12px 16px', background: '#1f1f1f', borderRadius: 8, border: '1px solid #303030', marginBottom: 20 }}>
        <b style={{ display: 'block', marginBottom: 12 }}>Cấu hình gửi:</b>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" style={{ flexWrap: 'wrap' }}>
            <span>Độ trễ random giữa mỗi lần gửi:</span>
            <InputNumber
              min={0} max={60000}
              value={delayConfig.min}
              onChange={v => setDelayConfig(prev => ({ ...prev, min: v || 0 }))}
              addonAfter="ms"
              style={{ width: 110 }}
              disabled={sendingState.isSending}
            />
            <span>Đến</span>
            <InputNumber
              min={0} max={60000}
              value={delayConfig.max}
              onChange={v => setDelayConfig(prev => ({ ...prev, max: v || 0 }))}
              addonAfter="ms"
              style={{ width: 110 }}
              disabled={sendingState.isSending}
            />
          </Space>
          <Checkbox
            checked={addRandomChar}
            onChange={e => setAddRandomChar(e.target.checked)}
            disabled={sendingState.isSending}
          >
            Chèn 1 ký tự ngẫu nhiên vào cuối câu để tránh bộ lọc Spam SMS của nhà mạng [a-z0-9]
          </Checkbox>
        </Space>
      </div>

      <div className="sms-form-actions">
        {sendingState.isSending ? (
          <div style={{ width: '100%', textAlign: 'left', background: 'rgba(0,0,0,0.2)', padding: '12px 16px', borderRadius: 8, border: '1px solid #177ddc' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <b style={{ color: '#177ddc' }}>
                {isPaused ? 'Đã tạm dừng...' : `Đang gửi ${sendingState.current} / ${sendingState.total} tin nhắn...`}
              </b>
              <Space>
                {isPaused ? (
                  <Button type="primary" size="small" icon={<PlayCircleOutlined />} onClick={() => setIsPaused(false)}>
                    Tiếp tục
                  </Button>
                ) : (
                  <Button type="default" size="small" icon={<PauseCircleOutlined />} onClick={() => setIsPaused(true)}>
                    Tạm dừng
                  </Button>
                )}
                <Button danger size="small" icon={<StopOutlined />} onClick={handleStop}>
                  Hủy gửi
                </Button>
              </Space>
            </div>
            <Progress
              percent={Math.round((sendingState.current / sendingState.total) * 100)}
              status={isPaused ? "normal" : "active"}
            />
          </div>
        ) : (
          <Button
            type="primary"
            onClick={handleSendBatch}
            disabled={customers.length === 0}
            icon={<SendOutlined />}
            size="large"
            style={{ width: '100%' }}
          >
            Bắt đầu Gửi SMS ({customers.filter(c => String(c.phone || '').trim()).length} khách)
          </Button>
        )}
      </div>
    </div>
  );
}

// ─── Tab 3: Lịch sử ─────────────────────────────────────
function HistoryTab() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [clearing, setClearing] = useState(false);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await smsAPI.getMessages(200);
      setMessages(data.messages || []);
    } catch {
      message.error('Không thể tải lịch sử tin nhắn');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const handleClear = async () => {
    setClearing(true);
    try {
      await smsAPI.clearMessages();
      setMessages([]);
      message.success('Đã xóa toàn bộ lịch sử');
    } catch {
      message.error('Xóa lịch sử thất bại');
    } finally {
      setClearing(false);
    }
  };

  const columns = [
    {
      title: 'Thời gian',
      dataIndex: 'sent_at',
      key: 'sent_at',
      width: 160,
      render: (val) => {
        if (!val) return '—';
        const d = new Date(val);
        return d.toLocaleString('vi-VN');
      },
    },
    {
      title: 'Số điện thoại',
      dataIndex: 'phones',
      key: 'phones',
      render: (phones) => (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {(phones || []).map((p) => (
            <Tag key={p} color="blue" style={{ margin: 0 }}>{p}</Tag>
          ))}
        </div>
      ),
    },
    {
      title: 'Nội dung',
      dataIndex: 'message',
      key: 'message',
      ellipsis: { showTitle: false },
      render: (text) => (
        <Tooltip title={text}>
          <Text ellipsis style={{ maxWidth: 280, display: 'block' }}>{text}</Text>
        </Tooltip>
      ),
    },
    {
      title: 'Trạng thái',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      align: 'center',
      render: (status) => (
        <Tag color={TAG_COLOR[status] || 'default'}>
          {TAG_LABEL[status] || status}
        </Tag>
      ),
    },
    {
      title: 'Lỗi',
      dataIndex: 'error',
      key: 'error',
      render: (err) => err ? <Text type="danger" style={{ fontSize: 12 }}>{err}</Text> : '—',
    },
  ];

  return (
    <div className="sms-tab-content">
      <div className="sms-section-header">
        <HistoryOutlined className="sms-section-icon" />
        <span>Lịch sử tin nhắn đã gửi</span>
        <div className="sms-history-actions">
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={loadHistory}
            loading={loading}
          >
            Làm mới
          </Button>
          {messages.length > 0 && (
            <Popconfirm
              title="Xóa toàn bộ lịch sử?"
              description="Hành động này không thể hoàn tác."
              onConfirm={handleClear}
              okText="Xóa"
              cancelText="Hủy"
              okButtonProps={{ danger: true }}
            >
              <Button size="small" danger icon={<DeleteOutlined />} loading={clearing}>
                Xóa tất cả
              </Button>
            </Popconfirm>
          )}
        </div>
      </div>

      <div className="sms-history-summary">
        <Text type="secondary">Tổng: <b>{messages.length}</b> tin nhắn</Text>
        <Text type="secondary" style={{ marginLeft: 16 }}>
          Thành công: <b style={{ color: '#52c41a' }}>
            {messages.filter(m => m.status === 'sent').length}
          </b>
        </Text>
        <Text type="secondary" style={{ marginLeft: 16 }}>
          Thất bại: <b style={{ color: '#ff4d4f' }}>
            {messages.filter(m => m.status === 'failed').length}
          </b>
        </Text>
      </div>

      <Table
        columns={columns}
        dataSource={messages}
        rowKey={(r) => r.id + r.sent_at}
        loading={loading}
        size="small"
        className="sms-history-table"
        pagination={{ pageSize: 20, showSizeChanger: false }}
        locale={{ emptyText: 'Chưa có tin nhắn nào được gửi' }}
        scroll={{ x: 700 }}
      />
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────
export default function SmsGateway() {
  const tabItems = [
    {
      key: 'config',
      label: (
        <span className="sms-tab-label">
          <SettingOutlined /> Cấu hình
        </span>
      ),
      children: <ConfigTab />,
    },
    {
      key: 'send',
      label: (
        <span className="sms-tab-label">
          <SendOutlined /> Gửi SMS
        </span>
      ),
      children: <SendTab />,
    },
    {
      key: 'history',
      label: (
        <span className="sms-tab-label">
          <HistoryOutlined /> Lịch sử
        </span>
      ),
      children: <HistoryTab />,
    },
  ];

  return (
    <div className="sms-gateway-page">
      <div className="sms-gateway-header">
        <div className="sms-gateway-title-wrap">
          <MobileOutlined className="sms-gateway-title-icon" />
          <div>
            <h2 className="sms-gateway-title">SMS Gateway</h2>
            <p className="sms-gateway-subtitle">
              Gửi SMS qua điện thoại Android (Local Network)
            </p>
          </div>
        </div>
      </div>

      <Tabs
        defaultActiveKey="config"
        items={tabItems}
        className="sms-gateway-tabs"
        type="card"
      />
    </div>
  );
}
