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
  DownloadOutlined, FileExcelOutlined,
  PauseCircleOutlined, PlayCircleOutlined, StopOutlined,
} from '@ant-design/icons';
import { smsAPI, filesAPI } from '../../services/api';
import useUserPersistentState from '../../hooks/useUserPersistentState';
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
const TAG_COLOR = { sent: 'success', failed: 'error', pending: 'processing', processed: 'processing', delivered: 'success' };
const TAG_LABEL = { sent: 'Đã gửi từ ĐT', failed: 'Không gửi được', pending: 'Đang chuyển xuống ĐT', processed: 'ĐT đã nhận', delivered: 'Đã nhận báo cáo' };

const CARRIER_LABELS = {
  viettel: 'Viettel',
  mobifone: 'MobiFone',
  vinaphone: 'VinaPhone',
  vietnammobile: 'Vietnamobile',
  other: 'Khác',
};

const CARRIER_PREFIXES = {
  viettel: ['086', '096', '097', '098', '032', '033', '034', '035', '036', '037', '038', '039'],
  mobifone: ['089', '090', '093', '070', '079', '077', '076', '078'],
  vinaphone: ['088', '091', '094', '081', '082', '083', '084', '085'],
  vietnammobile: ['092', '056', '058'],
};

function normalizeVietnamPhone(phone) {
  const digits = String(phone || '').replace(/\D/g, '');
  if (!digits) return '';

  if (digits.startsWith('84')) {
    return `0${digits.slice(2)}`;
  }

  return digits;
}

function normalizePhoneForSend(phone) {
  const normalized = normalizeVietnamPhone(phone);
  if (/^0\d{9}$/.test(normalized)) return normalized;
  return '';
}

function getCarrierByPhone(phone) {
  const normalized = normalizePhoneForSend(phone);
  if (!normalized) return 'other';

  const prefix3 = normalized.slice(0, 3);
  const found = Object.entries(CARRIER_PREFIXES).find(([, prefixes]) => prefixes.includes(prefix3));
  return found?.[0] || 'other';
}

function toVietnameseHonorific(gender) {
  const normalized = String(gender || '').trim().toLowerCase();
  if (!normalized) return 'Anh/Chị';
  if (normalized.includes('nam')) return 'Anh';
  if (normalized.includes('nữ') || normalized.includes('nu')) return 'Chị';
  return 'Anh/Chị';
}

function StatusBadge({ status }) {
  if (status === 'ok') return <Badge status="success" text="Đã kết nối" />;
  if (status === 'warn') return <Badge status="warning" text="Thiết bị có thể offline" />;
  if (status === 'error') return <Badge status="error" text="Không kết nối" />;
  return <Badge status="default" text="Chưa kiểm tra" />;
}

// ─── Tab 1: Cấu hình ────────────────────────────────────
function ConfigTab() {
  const [form] = Form.useForm();
  const deviceIp = Form.useWatch('device_ip', form);
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

  useEffect(() => {
    if (!deviceIp) return undefined;
    const timer = setInterval(() => {
      checkHealthStatus();
    }, 30000);
    return () => clearInterval(timer);
  }, [deviceIp]);

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
    } catch {
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

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={{
          device_port: 8080,
          enabled: false,
          use_specific_sim: false,
          sim_number: 1,
        }}
        className="sms-config-form"
      >
        <Form.Item label="Chế độ Kết nối" style={{ marginBottom: 16 }}>
          <Button type="primary" disabled>Local Server (Chung Wifi/LAN)</Button>
        </Form.Item>

        {healthStatus && (
          <Alert
            type={healthStatus.status === 'ok' ? 'success' : healthStatus.status === 'warn' ? 'warning' : 'error'}
            showIcon
            style={{ marginBottom: 16 }}
            message={
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <StatusBadge status={healthStatus.status} />
                <span>{healthStatus.message}</span>
              </div>
            }
            description={null}
          />
        )}

        <Alert
          className="sms-info-alert"
          type="info"
          showIcon
          message="Hướng dẫn kết nối Local Server"
          description={
            <ol style={{ margin: 0, paddingLeft: 16 }}>
              <li>Bật <b>Local Server</b> trong app Android SMS Gateway.</li>
              <li>Đảm bảo máy tính và điện thoại <b>cùng mạng WiFi/LAN</b>.</li>
              <li>Nhập IP hiển thị, Port, Username, Password vào form bên dưới.</li>
            </ol>
          }
          style={{ marginBottom: 16 }}
        />

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

        <Form.Item name="use_specific_sim" valuePropName="checked" style={{ marginBottom: 8 }}>
          <Checkbox>Bật chọn SIM gửi SMS</Checkbox>
        </Form.Item>

        <Form.Item
          shouldUpdate={(prev, curr) => (
            prev.use_specific_sim !== curr.use_specific_sim
            || prev.sim_number !== curr.sim_number
          )}
          noStyle
        >
          {({ getFieldValue }) => (
            <Form.Item
              name="sim_number"
              label="SIM gửi"
              rules={[
                {
                  validator: (_, value) => {
                    if (!getFieldValue('use_specific_sim')) return Promise.resolve();
                    if (value === 1 || value === 2) return Promise.resolve();
                    return Promise.reject(new Error('Vui lòng chọn SIM 1 hoặc SIM 2'));
                  }
                }
              ]}
            >
              <div style={{ display: 'flex', gap: 10 }}>
                <Button
                  type={getFieldValue('sim_number') === 1 ? 'primary' : 'default'}
                  onClick={() => form.setFieldValue('sim_number', 1)}
                  htmlType="button"
                  disabled={!getFieldValue('use_specific_sim')}
                >
                  SIM 1
                </Button>
                <Button
                  type={getFieldValue('sim_number') === 2 ? 'primary' : 'default'}
                  onClick={() => form.setFieldValue('sim_number', 2)}
                  htmlType="button"
                  disabled={!getFieldValue('use_specific_sim')}
                >
                  SIM 2
                </Button>
              </div>
            </Form.Item>
          )}
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
function SendTab({ userStorageKey }) {
  const [customers, setCustomers] = useUserPersistentState(userStorageKey, 'sms.send.customers', []);
  const [selectedCarrierFilters, setSelectedCarrierFilters] = useState([]);
  const [messageTemplate, setMessageTemplate] = useUserPersistentState(userStorageKey, 'sms.send.messageTemplate', '');
  const [manualPhoneInput, setManualPhoneInput] = useUserPersistentState(userStorageKey, 'sms.send.manualPhoneInput', '');
  const [manualPhones, setManualPhones] = useUserPersistentState(userStorageKey, 'sms.send.manualPhones', []);
  const [charCount, setCharCount] = useState(0);
  const [sendingState, setSendingState] = useState({ isSending: false, total: 0, current: 0 });
  const [isPaused, setIsPaused] = useState(false);
  const [currentDelayMs, setCurrentDelayMs] = useState(0);
  const [lastDelayMs, setLastDelayMs] = useState(null);

  // Cấu hình nâng cao
  const [delayConfig, setDelayConfig] = useUserPersistentState(userStorageKey, 'sms.send.delayConfig', { min: 1000, max: 3000 });
  const [addRandomChar, setAddRandomChar] = useUserPersistentState(userStorageKey, 'sms.send.addRandomChar', false);

  // Refs để điều khiển vòng lặp async
  const messageInputRef = useRef(null);
  const isSendingRef = useRef(false);
  const isPausedRef = useRef(false);

  // Sync state -> ref
  useEffect(() => { isPausedRef.current = isPaused; }, [isPaused]);

  const updateCustomerSendStatusByPhone = useCallback((phone, code, message_id = null) => {
    const normalizedPhone = String(phone || '').trim();
    if (!normalizedPhone) return;

    setCustomers(prev => prev.map(customer => (
      String(customer.phone || '').trim() === normalizedPhone
        ? {
          ...customer,
          smsStatus: { code, message_id: message_id || customer.smsStatus?.message_id },
          smsError: code === 'failed' ? (customer.smsError || 'Lỗi gửi tin') : null,
        }
        : customer
    )));
  }, [setCustomers]);

  // Polling check trang thai pending tu gateway local
  useEffect(() => {
    const pollPendingStatuses = () => {
      setCustomers(prev => {
        const pendings = prev.filter(c => c.smsStatus?.message_id && ['pending', 'processed'].includes(c.smsStatus?.code));
        if (pendings.length === 0) return prev;

        pendings.forEach(p => {
          smsAPI.getStatus(p.smsStatus.message_id).then(res => {
            const data = res.data;
            if (data.success && data.state) {
              const newState = data.state.toLowerCase();
              if (newState !== p.smsStatus.code) {
                setCustomers(current => current.map(c =>
                  c._key === p._key
                    ? { ...c, smsStatus: { ...c.smsStatus, code: newState }, smsError: data.error || (newState === 'failed' ? 'Lỗi gửi tin' : null) }
                    : c
                ));
              }
            }
          }).catch(() => { });
        });
        return prev;
      });
    };

    const timer = setInterval(pollPendingStatuses, 4000);
    return () => clearInterval(timer);
  }, [setCustomers]);

  const handleUpload = async (info) => {
    const file = info.file;
    try {
      const { data } = await filesAPI.parseExcel(file);
      const rows = (data.data || []).map((row, i) => ({
        ...row,
        _key: i,
        smsStatus: null,
        smsError: null,
      }));
      setCustomers(rows);
      const valid = rows.filter(r => String(r.phone || '').trim());
      message.success(`Đã tải ${data.row_count} dữ liệu. Có ${valid.length} SĐT hợp lệ.`);
    } catch {
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
    const fileRecipients = filteredFileCustomers
      .map(customer => ({
        type: 'file',
        customer,
        phoneRaw: String(customer?.phone || '').trim(),
        phoneSend: normalizePhoneForSend(customer?.phone),
      }))
      .filter(item => item.phoneSend);

    const manualRecipients = manualPhones
      .map(phone => ({
        type: 'manual',
        phoneRaw: String(phone || '').trim(),
        phoneSend: normalizePhoneForSend(phone),
      }))
      .filter(item => item.phoneSend);

    const recipients = [
      ...fileRecipients,
      ...manualRecipients,
    ];

    const skippedInvalid = (filteredFileCustomers.length - fileRecipients.length) + (manualPhones.length - manualRecipients.length);

    if (recipients.length === 0) {
      message.warning('Không có số điện thoại nào hợp lệ để gửi');
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

    if (skippedInvalid > 0) {
      message.warning(`Bỏ qua ${skippedInvalid} số không hợp lệ. Chỉ gửi các số di động VN hợp lệ.`);
    }

    setSendingState({ isSending: true, total: recipients.length, current: 0 });
    setIsPaused(false);
    setCurrentDelayMs(0);
    setLastDelayMs(null);
    isSendingRef.current = true;
    isPausedRef.current = false;

    // Reset trạng thái của danh sách file trước khi chạy đợt gửi mới.
    setCustomers(prev => prev.map(customer => ({
      ...customer,
      smsStatus: null,
      smsError: null,
    })));

    let successCount = 0;

    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

    const buildMessageByRecipient = (recipient) => {
      const customer = recipient.type === 'file'
        ? recipient.customer
        : {
          phone: recipient.phoneRaw,
          name: '',
          gender: '',
          contract_id: '',
          cccd: '',
          address: '',
        };

      let text = messageTemplate
        .replace(/{name}/g, customer.name || '')
        .replace(/{gender}/g, toVietnameseHonorific(customer.gender))
        .replace(/{phone}/g, customer.phone || '')
        .replace(/{contract_id}/g, customer.contract_id || '')
        .replace(/{cccd}/g, customer.cccd || '')
        .replace(/{address}/g, customer.address || '');

      if (addRandomChar) {
        const randChar = chars.charAt(Math.floor(Math.random() * chars.length));
        text += ` [${randChar}]`;
      }

      return text;
    };

    for (let i = 0; i < recipients.length; i++) {
      if (!isSendingRef.current) break; // Bị hủy

      // Kiểm tra trạng thái Tạm dừng
      while (isPausedRef.current) {
        if (!isSendingRef.current) break;
        await new Promise(r => setTimeout(r, 500));
      }
      if (!isSendingRef.current) break;

      const recipient = recipients[i];
      const phoneRaw = recipient.phoneRaw;
      const phoneSend = recipient.phoneSend;
      setSendingState(prev => ({ ...prev, current: i + 1 }));

      if (recipient.type === 'file') {
        updateCustomerSendStatusByPhone(phoneRaw, 'pending');
      }

      const text = buildMessageByRecipient(recipient);

      try {
        const { data } = await smsAPI.send({
          phone_numbers: [phoneSend],
          message: text,
        });
        successCount++;

        if (recipient.type === 'file') {
          updateCustomerSendStatusByPhone(phoneRaw, 'pending', data?.message_id);
        }

        // Nghỉ ngơi giữa 2 lần gửi
        if (i < recipients.length - 1 && isSendingRef.current) {
          const delayTimeout = Math.floor(Math.random() * (delayConfig.max - delayConfig.min + 1)) + delayConfig.min;
          setLastDelayMs(delayTimeout);

          const startAt = Date.now();
          setCurrentDelayMs(delayTimeout);

          await new Promise((resolve) => {
            const timer = setInterval(() => {
              const elapsed = Date.now() - startAt;
              const remain = Math.max(0, delayTimeout - elapsed);
              setCurrentDelayMs(remain);

              if (remain <= 0 || !isSendingRef.current) {
                clearInterval(timer);
                setCurrentDelayMs(0);
                resolve();
              }
            }, 100);
          });
        }
      } catch (err) {
        console.error("Gửi SMS lỗi cho SĐT", phoneRaw, err);
        if (recipient.type === 'file') {
          setCustomers(prev => prev.map(customer => (
            String(customer.phone || '').trim() === String(phoneRaw || '').trim()
              ? {
                ...customer,
                smsStatus: { code: 'failed' },
                smsError: err.response?.data?.detail || err.message || 'Không gửi được',
              }
              : customer
          )));
        }
      }
    }

    const wasCanceled = !isSendingRef.current;
    isSendingRef.current = false;
    setSendingState(prev => ({ ...prev, isSending: false }));
    setIsPaused(false);
    setCurrentDelayMs(0);

    if (wasCanceled) {
      message.info(`Đã dừng gửi tin. Gửi thành công: ${successCount} tin.`);
    } else {
      message.success(`Đã hoàn tất gửi tin. Thành công: ${successCount}/${recipients.length}`);
    }
  };

  const handleStop = () => {
    isSendingRef.current = false;
    setIsPaused(false);
    setCurrentDelayMs(0);
  };

  const handleAddManualPhone = () => {
    const phone = String(manualPhoneInput || '').trim();
    if (!phone) {
      message.warning('Vui lòng nhập số điện thoại trước khi thêm');
      return;
    }
    if (manualPhones.includes(phone)) {
      message.warning('Số điện thoại này đã có trong danh sách thủ công');
      return;
    }
    setManualPhones(prev => [...prev, phone]);
    setManualPhoneInput('');
  };

  const handleRemoveManualPhone = (phone) => {
    setManualPhones(prev => prev.filter(p => p !== phone));
  };

  const customerColumns = [
    { title: 'STT', key: 'stt', width: 55, render: (_, __, i) => i + 1, align: 'center' },
    { title: 'Số điện thoại', dataIndex: 'phone', key: 'phone', width: 140 },
    { title: 'Tên', dataIndex: 'name', key: 'name' },
    {
      title: 'Nhà mạng',
      key: 'carrier',
      dataIndex: 'phone',
      width: 140,
      filteredValue: selectedCarrierFilters.length ? selectedCarrierFilters : null,
      filters: [
        { text: CARRIER_LABELS.viettel, value: 'viettel' },
        { text: CARRIER_LABELS.mobifone, value: 'mobifone' },
        { text: CARRIER_LABELS.vinaphone, value: 'vinaphone' },
        { text: CARRIER_LABELS.vietnammobile, value: 'vietnammobile' },
      ],
      onFilter: (value, record) => getCarrierByPhone(record?.phone) === value,
      render: (phone) => {
        const carrier = getCarrierByPhone(phone);
        return (
          <Tag color={carrier === 'other' ? 'default' : 'blue'}>
            {CARRIER_LABELS[carrier] || CARRIER_LABELS.other}
          </Tag>
        );
      },
    },
    { title: 'Mã HĐ', dataIndex: 'contract_id', key: 'contract_id' },
    {
      title: 'Trạng thái gửi',
      key: 'smsStatus',
      width: 180,
      render: (_, record) => {
        const code = record?.smsStatus?.code;
        if (!code) {
          return <span style={{ color: '#64748b', fontSize: 12 }}>Chưa gửi</span>;
        }
        return (
          <Tag color={TAG_COLOR[code] || 'default'}>
            {TAG_LABEL[code] || code}
          </Tag>
        );
      },
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
          onClick={() => setCustomers(prev => prev.filter(r => r._key !== record._key))}
        />
      ),
    },
  ];

  const filteredFileCustomers = customers.filter((customer) => {
    if (!selectedCarrierFilters.length) return true;
    return selectedCarrierFilters.includes(getCarrierByPhone(customer?.phone));
  });

  const validFileCustomersCount = filteredFileCustomers.filter(c => normalizePhoneForSend(c?.phone)).length;
  const validManualPhonesCount = manualPhones.filter(p => normalizePhoneForSend(p)).length;
  const totalRecipientsCount = validFileCustomersCount + validManualPhonesCount;

  return (
    <div className="sms-tab-content">
      {/* Tải dữ liệu Khách hàng */}
      <div className="sms-section-header">
        <SendOutlined className="sms-section-icon" />
        <span>Gửi tin nhắn Hàng loạt từ File</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <b style={{ lineHeight: '32px' }}>
          Danh sách nhận tin {customers.length > 0 && `(${filteredFileCustomers.length}/${customers.length} khách)`}
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
        onChange={(_, filters) => {
          const carrierValues = Array.isArray(filters?.carrier)
            ? filters.carrier.filter(Boolean)
            : [];
          setSelectedCarrierFilters(carrierValues);
        }}
        size="small"
        scroll={{ y: 250 }}
        pagination={false}
        className="sms-customers-table"
        locale={{ emptyText: 'Chưa có danh sách khách hàng' }}
      />

      <div className="sms-manual-send-box">
        <b>Gửi thủ công lẻ từng số:</b>
        <Space style={{ width: '100%', marginTop: 8 }} wrap>
          <Input
            value={manualPhoneInput}
            onChange={(e) => setManualPhoneInput(e.target.value)}
            onPressEnter={handleAddManualPhone}
            placeholder="Nhập số điện thoại thủ công"
            style={{ width: 260 }}
            disabled={sendingState.isSending}
          />
          <Button
            icon={<PlusOutlined />}
            onClick={handleAddManualPhone}
            disabled={sendingState.isSending}
          >
            Thêm SĐT
          </Button>
        </Space>

        <div style={{ marginTop: 8, color: '#94a3b8', fontSize: 12 }}>
          Lưu ý: Danh sách thủ công chỉ dùng biến {'{phone}'}. Các biến nhanh khác như {'{name}'}, {'{contract_id}'} sẽ tự động để trống.
        </div>

        <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {manualPhones.map((phone) => (
            <Tag
              key={phone}
              color="blue"
              closable
              onClose={() => handleRemoveManualPhone(phone)}
              style={{ marginInlineEnd: 0 }}
            >
              {phone}
            </Tag>
          ))}
          {manualPhones.length === 0 && (
            <span style={{ color: '#64748b', fontSize: 12 }}>Chưa có số thủ công nào</span>
          )}
        </div>
      </div>

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
          placeholder="[automation marketing] Chao {gender} {name}, chuc mung ho so {contract_id} da duoc duyet..."
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
            {!isPaused && currentDelayMs > 0 && (
              <div style={{ marginBottom: 8, color: '#94a3b8', fontSize: 12 }}>
                Đang chờ ngẫu nhiên giữa 2 lần gửi: <b>{Math.ceil(currentDelayMs)}</b> ms
                {typeof lastDelayMs === 'number' && (
                  <span> (đã random: {lastDelayMs} ms)</span>
                )}
              </div>
            )}
            <Progress
              percent={Math.round((sendingState.current / sendingState.total) * 100)}
              status={isPaused ? "normal" : "active"}
            />
          </div>
        ) : (
          <Button
            type="primary"
            onClick={handleSendBatch}
            disabled={totalRecipientsCount === 0}
            icon={<SendOutlined />}
            size="large"
            style={{ width: '100%' }}
          >
            Bắt đầu Gửi SMS ({totalRecipientsCount} số)
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
  const [syncing, setSyncing] = useState(false);
  const [clearing, setClearing] = useState(false);

  const loadHistory = useCallback(async (sync = false) => {
    if (sync) setSyncing(true);
    setLoading(true);
    try {
      const { data } = await smsAPI.getMessages(200, sync);
      setMessages(data.messages || []);
      if (sync && data.sync) {
        message.success(`Đã đồng bộ ${data.sync.synced}/${data.sync.checked} tin cần cập nhật`);
      }
    } catch {
      message.error('Không thể tải lịch sử tin nhắn');
    } finally {
      if (sync) setSyncing(false);
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
      width: 155,
      render: (val) => {
        if (!val) return '—';
        const d = new Date(val);
        return d.toLocaleString('vi-VN');
      },
    },
    {
      title: 'Message ID',
      dataIndex: 'id',
      key: 'id',
      width: 185,
      ellipsis: { showTitle: false },
      render: (id) => id ? (
        <Tooltip title={id}>
          <span className="sms-history-code-cell">{id}</span>
        </Tooltip>
      ) : '—',
    },
    {
      title: 'Số điện thoại',
      dataIndex: 'phones',
      key: 'phones',
      width: 150,
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
      width: 250,
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
      width: 140,
      align: 'center',
      render: (status) => (
        <Tag color={TAG_COLOR[status] || 'default'}>
          {TAG_LABEL[status] || status}
        </Tag>
      ),
    },
    {
      title: 'Device ID',
      dataIndex: 'device_id',
      key: 'device_id',
      width: 200,
      responsive: ['xl'],
      ellipsis: { showTitle: false },
      render: (id) => id ? (
        <Tooltip title={id}>
          <span className="sms-history-code-cell">{id}</span>
        </Tooltip>
      ) : '—',
    },
    {
      title: 'Lỗi',
      dataIndex: 'error',
      key: 'error',
      width: 220,
      responsive: ['xxl'],
      ellipsis: { showTitle: false },
      render: (err) => err ? (
        <Tooltip title={err}>
          <Text type="danger" ellipsis style={{ fontSize: 12, display: 'block' }}>{err}</Text>
        </Tooltip>
      ) : '—',
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
            onClick={() => loadHistory(false)}
            loading={loading}
          >
            Làm mới
          </Button>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => loadHistory(true)}
            loading={syncing}
          >
            Đồng bộ trạng thái
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
            {messages.filter(m => ['sent', 'delivered'].includes(String(m.status || '').toLowerCase())).length}
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
        tableLayout="fixed"
        className="sms-history-table"
        pagination={{ pageSize: 20, showSizeChanger: false }}
        locale={{ emptyText: 'Chưa có tin nhắn nào được gửi' }}
        scroll={{ x: 1080 }}
      />
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────
export default function SmsGateway({ userStorageKey }) {
  const [activeTab, setActiveTab] = useUserPersistentState(userStorageKey, 'sms.activeTab', 'config');

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
      children: <SendTab userStorageKey={userStorageKey} />,
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
              Gửi/nhận SMS qua Android (Local Server)
            </p>
          </div>
        </div>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        className="sms-gateway-tabs"
        type="card"
      />
    </div>
  );
}
