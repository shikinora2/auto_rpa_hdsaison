import { useState, useEffect, useRef, useCallback } from 'react';
import { ConfigProvider, Layout, Menu, theme, Switch, Tooltip, Button, message, Modal, Form, Input, Popover, Badge, Drawer } from 'antd';
import viVN from 'antd/locale/vi_VN';
import dayjs from 'dayjs';
import 'dayjs/locale/vi';
import {
  HomeOutlined,
  ToolOutlined,
  MessageOutlined,
  RobotOutlined,
  MobileOutlined,
  WifiOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  StopOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  UserOutlined,
  TeamOutlined,
  BellOutlined,
  BookOutlined,
} from '@ant-design/icons';

import { authAPI, configAPI, rpaAPI, zaloAPI } from './services/api';
import Dashboard from './pages/Dashboard';
import Tasks from './pages/Tasks';
import Zalo from './pages/Zalo';
import SmsGateway from './pages/SmsGateway';
import AdminUsers from './pages/AdminUsers';
import LoginPage from './pages/Auth/LoginPage';
import { useWebSocket } from './hooks/useWebSocket';

import './App.css';

dayjs.locale('vi');

const { Sider, Content } = Layout;

// Menu items configuration
const baseMenuItems = [
  {
    key: 'dashboard',
    icon: <HomeOutlined />,
    label: 'Trang Chủ',
  },
  {
    key: 'tasks',
    icon: <ToolOutlined />,
    label: 'Tác Vụ RPA',
  },
  {
    key: 'zalo',
    icon: <MessageOutlined />,
    label: 'Auto Zalo',
  },
  {
    key: 'sms-gateway',
    icon: <MobileOutlined />,
    label: 'SMS Gateway',
  },
];

// Page titles mapping
const pageTitles = {
  dashboard: 'Dashboard',
  tasks: 'Tác Vụ RPA',
  zalo: 'Auto Zalo',
  'sms-gateway': 'SMS Gateway',
  'admin-users': 'Quản Trị Tài Khoản',
};

const TASK_LABELS = {
  check_contracts: 'Kiểm tra HĐ',
  download_files: 'Tải file PDF/JSON',
  scrape_details: 'Lấy thông tin chi tiết → Excel',
  login: 'Đăng nhập HPO',
  zalo_login: 'Login Zalo',
  send_messages: 'Gửi tin nhắn Zalo',
  add_friends: 'Kết bạn Zalo',
};

const HELP_GUIDES = {
  dashboard: {
    title: 'Hướng dẫn Trang Chủ',
    summary: 'Dùng để quản lý phiên đăng nhập HPO và Zalo trước khi chạy tác vụ.',
    steps: [
      'Nhập tài khoản HPO và bấm Đăng nhập HPO để mở phiên làm việc.',
      'Dùng nút Kiểm tra lại phiên để xác nhận trạng thái thực tế.',
      'Ở phần Zalo, bấm Đăng nhập Zalo rồi quét mã QR trên điện thoại.',
      'Nếu cần đăng nhập lại từ đầu, bấm Xóa phiên (HPO) hoặc Đăng xuất Zalo.',
    ],
  },
  tasks: {
    title: 'Hướng dẫn Tác Vụ RPA',
    summary: 'Chạy các nghiệp vụ kiểm tra, tải file và lấy thông tin chi tiết hợp đồng.',
    steps: [
      'Chọn khoảng thời gian hợp đồng trước khi bấm bất kỳ tác vụ nào.',
      'Kiểm tra số lượng: chỉ đếm số hợp đồng, không tải dữ liệu.',
      'Tải file PDF/JSON: tải file hợp đồng theo định dạng đã chọn.',
      'Lấy thông tin chi tiết → Excel: xuất file Excel tổng hợp thông tin.',
    ],
  },
  zalo: {
    title: 'Hướng dẫn Auto Zalo',
    summary: 'Gửi tin nhắn hoặc kết bạn hàng loạt dựa trên danh sách dữ liệu.',
    steps: [
      'Bảo đảm trạng thái Zalo đã đăng nhập thành công ở Trang Chủ.',
      'Nạp danh sách khách hàng theo đúng mẫu dữ liệu đầu vào.',
      'Cấu hình nội dung, số lượng, độ trễ theo đúng nhu cầu nghiệp vụ.',
      'Theo dõi log và trạng thái để xử lý tạm dừng/dừng khi cần.',
    ],
  },
  'sms-gateway': {
    title: 'Hướng dẫn SMS Gateway',
    summary: 'Quản lý kết nối thiết bị SMS và gửi tin nhắn qua SIM đã cấu hình.',
    steps: [
      'Chọn đúng SIM và thông số kết nối trước khi bấm Kết nối.',
      'Sau khi kết nối, dùng tab kiểm tra để xác nhận thiết bị hoạt động.',
      'Gửi SMS thử nghiệm với số điện thoại mẫu để kiểm tra luồng gửi.',
      'Khi kết thúc làm việc, bấm Ngắt kết nối để giải phóng thiết bị.',
    ],
  },
  'admin-users': {
    title: 'Hướng dẫn Quản Lý User',
    summary: 'Dành cho admin để tạo, phê duyệt, cập nhật và xóa tài khoản người dùng.',
    steps: [
      'Tạo tài khoản mới bằng nút Thêm user với đầy đủ username và mật khẩu.',
      'Phê duyệt tài khoản mới trước khi người dùng có thể đăng nhập hệ thống.',
      'Cập nhật vai trò hoặc trạng thái active theo đúng chính sách nội bộ.',
      'Chỉ xóa tài khoản không còn sử dụng để tránh ảnh hưởng lịch sử thao tác.',
    ],
  },
};

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isAuthChecking, setIsAuthChecking] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [changePwdForm] = Form.useForm();
  const [activeTab, setActiveTab] = useState('dashboard');
  const { logs, status, progress, taskStatus, qrImage } = useWebSocket();
  const lastTaskStatusRef = useRef('');
  const lastProgressRef = useRef(-1);
  const lastLogRef = useRef('');
  const prevWsStatusRef = useRef('');
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);
  const [isGuideOpen, setIsGuideOpen] = useState(false);

  // System status — shared across header
  const [headless, setHeadless] = useState(false);
  const [sessionStatus, setSessionStatus] = useState({ is_logged_in: false, checking: true });
  const [rpaStatus, setRpaStatus] = useState({ is_running: false, is_paused: false });
  const isAdmin = currentUser?.role === 'admin';
  const userStorageKey = currentUser?.id ? `uid_${currentUser.id}` : (currentUser?.username ? `u_${currentUser.username}` : 'guest');
  const menuItems = isAdmin
    ? [
        ...baseMenuItems,
        {
          key: 'admin-users',
          icon: <TeamOutlined />,
          label: 'Quản Lý User',
        },
      ]
    : baseMenuItems;

  const pushNotification = useCallback((entry) => {
    const nextItem = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      level: entry.level || 'info',
      text: entry.text || '',
      createdAt: Date.now(),
      read: isNotificationOpen,
    };

    if (!nextItem.text.trim()) return;

    setNotifications(prev => [nextItem, ...prev].slice(0, 120));
    if (!isNotificationOpen) {
      setUnreadCount(prev => Math.min(999, prev + 1));
    }

    if (entry.important) {
      message.open({
        key: entry.key || `important-${nextItem.id}`,
        type: nextItem.level,
        content: nextItem.text,
        duration: entry.duration ?? 3,
      });
    }
  }, [isNotificationOpen]);

  useEffect(() => {
    let mounted = true;
    authAPI.me()
      .then(({ data }) => {
        if (!mounted) return;
        const user = data?.user || null;
        setCurrentUser(user);
        setIsAuthenticated(Boolean(user));
      })
      .catch(() => {
        if (!mounted) return;
        setCurrentUser(null);
        setIsAuthenticated(false);
      })
      .finally(() => {
        if (mounted) setIsAuthChecking(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const handleNotificationOpenChange = (open) => {
    setIsNotificationOpen(open);
    if (open) {
      setUnreadCount(0);
      setNotifications(prev => prev.map(item => (item.read ? item : { ...item, read: true })));
    }
  };

  const clearNotificationHistory = () => {
    setNotifications([]);
    setUnreadCount(0);
  };

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }
    (async () => {
      try { const { data } = await configAPI.get(); setHeadless(data.headless || false); } catch (error) { console.debug('Failed to load config:', error); }
      try { const { data } = await rpaAPI.getStatus(); setRpaStatus(data); } catch (error) { console.debug('Failed to load RPA status:', error); }
      try {
        const { data } = await rpaAPI.checkSession();
        setSessionStatus({ is_logged_in: data.is_logged_in, checking: false });
      } catch (error) {
        console.debug('Failed to check session:', error);
        setSessionStatus({ is_logged_in: false, checking: false });
      }
    })();
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated || !taskStatus) return;

    const taskKey = taskStatus?.data?.task || taskStatus?.task || 'unknown';
    const dedupeKey = `${taskKey}:${taskStatus.status}`;
    if (lastTaskStatusRef.current === dedupeKey) return;
    lastTaskStatusRef.current = dedupeKey;

    const taskLabel = TASK_LABELS[taskKey] || taskKey;
    if (taskStatus.status === 'running' || taskStatus.status === 'active') {
      pushNotification({
        key: 'task-runtime',
        level: 'info',
        text: `${taskLabel}: đang thực thi...`,
      });
      return;
    }

    if (taskStatus.status === 'paused') {
      pushNotification({
        key: 'task-runtime',
        level: 'warning',
        text: `${taskLabel}: đã tạm dừng`,
      });
      return;
    }

    if (taskStatus.status === 'completed') {
      pushNotification({
        key: 'task-runtime',
        level: 'success',
        text: `${taskLabel}: hoàn tất`,
      });
      return;
    }

    if (taskStatus.status === 'error') {
      pushNotification({
        key: 'task-runtime',
        level: 'error',
        text: `${taskLabel}: xảy ra lỗi, vui lòng kiểm tra lại`,
        important: true,
        duration: 4,
      });
      return;
    }

    if (taskStatus.status === 'stopping') {
      pushNotification({
        key: 'task-runtime',
        level: 'warning',
        text: `${taskLabel}: đang dừng tác vụ...`,
      });
    }
  }, [isAuthenticated, taskStatus, pushNotification]);

  useEffect(() => {
    if (!isAuthenticated || !progress) return;
    if (String(progress.message || '').includes('Đang xử lý:')) return;
    const percent = Number(progress.percentage || 0);
    if (Number.isNaN(percent)) return;

    const rounded = Math.max(0, Math.min(100, Math.round(percent)));
    const shouldNotify = rounded === 100 || rounded % 20 === 0;
    if (!shouldNotify || lastProgressRef.current === rounded) return;

    lastProgressRef.current = rounded;
    pushNotification({
      key: `task-progress-${rounded}`,
      level: rounded === 100 ? 'success' : 'info',
      text: `${progress.message || 'Tiến trình'}: ${rounded}%`,
    });
  }, [isAuthenticated, progress, pushNotification]);

  useEffect(() => {
    if (!isAuthenticated || logs.length === 0) return;

    const latest = logs[logs.length - 1];
    const logKey = `${latest.timestamp || ''}:${latest.level || ''}:${latest.message || ''}`;
    if (lastLogRef.current === logKey) return;
    lastLogRef.current = logKey;

    const text = String(latest.message || '').trim();
    if (!text) return;

    const isPerCustomerRealtime = /(\[[0-9]+\/[0-9]+\].*(Kết bạn|gửi|Thất bại|Đã là bạn bè)|Đang xử lý:\s*[0-9]{8,15})/i.test(text);
    if (isPerCustomerRealtime) return;

    const level = latest.level || 'info';
    const looksLikeStep = /bước|step|dang |đang /i.test(text);
    if (level === 'info' && !looksLikeStep) return;

    const mappedLevel = level === 'error' ? 'error' : level === 'warning' ? 'warning' : level === 'success' ? 'success' : 'info';
    pushNotification({
      key: `ws-log-${latest.timestamp || Date.now()}`,
      level: mappedLevel,
      text,
      important: mappedLevel === 'error' || mappedLevel === 'warning',
      duration: mappedLevel === 'error' ? 4 : 3,
    });
  }, [isAuthenticated, logs, pushNotification]);

  useEffect(() => {
    if (!isAuthenticated) return;
    if (prevWsStatusRef.current === status) return;

    if (prevWsStatusRef.current && status === 'disconnected') {
      pushNotification({
        key: 'ws-status-offline',
        level: 'warning',
        text: 'Mất kết nối backend, đang chờ kết nối lại...',
        important: true,
        duration: 4,
      });
    }

    if (prevWsStatusRef.current && prevWsStatusRef.current !== 'connected' && status === 'connected') {
      pushNotification({
        key: 'ws-status-online',
        level: 'success',
        text: 'Đã kết nối lại backend',
      });
    }

    prevWsStatusRef.current = status;
  }, [isAuthenticated, status, pushNotification]);

  useEffect(() => {
    if (!isAuthenticated) return;
    authAPI.me()
      .then(({ data }) => {
        const user = data?.user || null;
        if (user) {
          setCurrentUser(user);
        }
      })
      .catch(() => {
        setIsAuthenticated(false);
        setCurrentUser(null);
      });
  }, [isAuthenticated]);

  const liveRpaStatus = (() => {
    if (!taskStatus) return rpaStatus;
    const st = taskStatus.status;
    if (st === 'running' || st === 'paused') {
      return { is_running: true, is_paused: st === 'paused' };
    }
    if (st === 'completed' || st === 'error' || st === 'stopping') {
      return { is_running: false, is_paused: false };
    }
    return rpaStatus;
  })();

  const liveSessionStatus =
    taskStatus?.data?.task === 'login' && taskStatus.status === 'completed'
      ? { is_logged_in: true, checking: false }
      : sessionStatus;

  const handleHeadlessToggle = async (val) => {
    setHeadless(val);
    try {
      await configAPI.update({ headless: val });
    } catch (error) {
      console.debug('Failed to save headless setting:', error);
    }
  };

  const handleVerifySession = async () => {
    setSessionStatus(prev => ({ ...prev, checking: true }));
    try {
      const { data } = await rpaAPI.verifySession();
      setSessionStatus({ is_logged_in: data.is_logged_in, checking: false });
    } catch { setSessionStatus({ is_logged_in: false, checking: false }); }
  };

  const isZaloTask = ['zalo_login', 'send_messages', 'add_friends'].includes(taskStatus?.data?.task);

  const handlePause = async () => {
    try {
      if (isZaloTask) {
        if (liveRpaStatus.is_paused) { await zaloAPI.resume(); message.info('Đã tiếp tục tác vụ Zalo'); }
        else { await zaloAPI.pause(); message.warning('Đã tạm dừng tác vụ Zalo'); }
        // rpaStatus được cập nhật tự động qua WebSocket broadcast từ backend
      } else {
        if (liveRpaStatus.is_paused) { await rpaAPI.resume(); message.info('Đã tiếp tục tác vụ'); }
        else { await rpaAPI.pause(); message.warning('Đã tạm dừng tác vụ'); }
        const { data } = await rpaAPI.getStatus();
        setRpaStatus(data);
      }
    } catch (error) {
      console.debug('Pause/resume failed:', error);
    }
  };

  const handleStop = async () => {
    try {
      if (isZaloTask) { await zaloAPI.stop(); message.warning('Đang dừng tác vụ Zalo...'); }
      else { await rpaAPI.stop(); message.warning('Đang dừng tác vụ...'); }
    } catch (error) {
      console.debug('Stop failed:', error);
    }
  };

  const currentTaskName = TASK_LABELS[taskStatus?.data?.task] || null;
  const statusInfo = (() => {
    if (liveRpaStatus.is_running) {
      if (liveRpaStatus.is_paused) return { text: 'Tạm dừng' };
      return { text: 'Đang chạy' };
    }
    return { text: 'Sẵn sàng' };
  })();

  const headerStats = [
    {
      key: 'session',
      label: 'Phiên HPO',
      value: liveSessionStatus.checking ? 'Kiểm tra...' : liveSessionStatus.is_logged_in ? 'Đã đăng nhập' : 'Chưa đăng nhập',
      icon: <WifiOutlined />,
      iconClass: liveSessionStatus.checking ? 'warning' : liveSessionStatus.is_logged_in ? 'success' : 'error',
    },
    {
      key: 'rpa',
      label: 'RPA',
      value: statusInfo.text,
      icon: <RobotOutlined />,
      iconClass: liveRpaStatus.is_running ? (liveRpaStatus.is_paused ? 'warning' : 'success') : 'info',
    },
    {
      key: 'task',
      label: 'Tác vụ',
      value: currentTaskName || 'Không có',
      icon: <ThunderboltOutlined />,
      iconClass: currentTaskName ? 'warning' : 'info',
    },
  ];

  const handleMenuClick = (e) => {
    setActiveTab(e.key);
  };

  const dashboardView = (
    <Dashboard
      taskStatus={taskStatus}
      progress={progress}
      headless={headless}
      sessionStatus={liveSessionStatus}
      onVerifySession={handleVerifySession}
      onSessionUpdate={setSessionStatus}
      rpaStatus={liveRpaStatus}
      qrImage={qrImage}
    />
  );

  const handleLoginSuccess = (user) => {
    setCurrentUser(user || null);
    setIsAuthenticated(true);
  };

  const handleLogout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.debug('Logout request failed:', error);
    } finally {
      setCurrentUser(null);
      setIsAuthenticated(false);
      message.info('Đã đăng xuất');
    }
  };

  const handleChangePassword = async () => {
    try {
      const values = await changePwdForm.validateFields();
      await authAPI.changePassword(values);
      message.success('Đổi mật khẩu thành công, vui lòng đăng nhập lại');
      setShowChangePassword(false);
      changePwdForm.resetFields();
      handleLogout();
    } catch (error) {
      if (!error?.errorFields) {
        message.error(error.response?.data?.detail || 'Đổi mật khẩu thất bại');
      }
    }
  };

  const notificationContent = (
    <div className="notification-panel">
      <div className="notification-panel-header">
        <span>Thông báo hệ thống</span>
        <Button type="link" size="small" onClick={clearNotificationHistory}>Xóa tất cả</Button>
      </div>
      <div className="notification-panel-list">
        {notifications.length === 0 ? (
          <div className="notification-empty">Chưa có thông báo mới</div>
        ) : (
          notifications.map(item => (
            <div key={item.id} className={`notification-item notification-item--${item.level} ${item.read ? 'is-read' : ''}`}>
              <div className="notification-item-text">{item.text}</div>
              <div className="notification-item-time">{dayjs(item.createdAt).format('HH:mm:ss DD/MM')}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );

  const activeGuide = HELP_GUIDES[activeTab] || HELP_GUIDES.dashboard;

  if (isAuthChecking) {
    return (
      <ConfigProvider locale={viVN} theme={{ algorithm: theme.darkAlgorithm }}>
        <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', color: '#e2e8f0' }}>
          Đang xác thực phiên đăng nhập...
        </div>
      </ConfigProvider>
    );
  }

  if (!isAuthenticated) {
    return (
      <ConfigProvider locale={viVN} theme={{ algorithm: theme.darkAlgorithm }}>
        <LoginPage onLoginSuccess={handleLoginSuccess} />
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider
      locale={viVN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#6366f1',
          colorBgBase: '#0f172a',
          colorBgContainer: '#1e293b',
          colorBgElevated: '#263348',
          colorBorder: 'rgba(148,163,184,0.15)',
          colorText: '#f8fafc',
          colorTextSecondary: '#cbd5e1',
          colorTextTertiary: '#64748b',
          borderRadius: 10,
          fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          fontSize: 14,
          lineHeight: 1.6,
        },
        components: {
          Menu: {
            darkItemBg: 'transparent',
            darkSubMenuItemBg: 'transparent',
            darkItemSelectedBg: 'rgba(99,102,241,0.15)',
            darkItemSelectedColor: '#818cf8',
            darkItemHoverBg: 'rgba(148,163,184,0.08)',
            darkItemHoverColor: '#f8fafc',
            itemHeight: 44,
          },
          Table: {
            headerBg: '#162032',
            rowHoverBg: 'rgba(99,102,241,0.06)',
          },
        },
      }}
    >
      <Layout className="app-layout">
        {/* Sidebar */}
        <Sider className="app-sidebar" width={260}>
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">
              <ThunderboltOutlined />
            </div>
            <div className="sidebar-logo-text">
              <span className="sidebar-logo-brand">Automation Marketing</span>
              <span className="sidebar-logo-sub">Hệ thống Automnation</span>
            </div>
          </div>

          <div className="sidebar-nav-label">ĐIỀU HƯỚNG</div>

          <Menu
            className="sidebar-menu"
            mode="inline"
            theme="dark"
            selectedKeys={[activeTab]}
            onClick={handleMenuClick}
            items={menuItems}
          />

          <div className="sidebar-footer">
            <div className="sidebar-version-badge">
              <span className="sidebar-version-dot"></span>
              <span>v2.0.0 — Web Edition</span>
            </div>
          </div>
        </Sider>

        {/* Main Content Area */}
        <div className="app-main">
          {/* Header */}
          <header className="app-header">
            <div className="header-left">
              <div className="header-breadcrumb">
                Pages / {pageTitles[activeTab]}
              </div>
              <h1 className="header-title">{pageTitles[activeTab]}</h1>
            </div>
            <div className="header-right">
              <div className="header-status-group">
                <Popover
                  trigger="click"
                  placement="bottomRight"
                  overlayClassName="notification-popover"
                  content={notificationContent}
                  open={isNotificationOpen}
                  onOpenChange={handleNotificationOpenChange}
                >
                  <Badge count={unreadCount} size="small" overflowCount={99}>
                    <Button className="notification-bell-btn" shape="circle" icon={<BellOutlined />} />
                  </Badge>
                </Popover>
                <Tooltip title={currentUser?.username || 'User'} placement="bottomRight">
                  <div className="status-pill status-pill--info" style={{ padding: '6px 10px', marginRight: 6 }}>
                    <span className="status-pill-icon"><UserOutlined /></span>
                  </div>
                </Tooltip>
                <Button size="small" onClick={() => setShowChangePassword(true)}>Đổi mật khẩu</Button>
                <Button size="small" danger onClick={handleLogout}>Đăng xuất</Button>
                {headerStats.map(stat => (
                  <Tooltip key={stat.key} title={<span><b>{stat.label}</b><br />{stat.value}</span>} placement="bottomRight">
                    <div className={`status-pill status-pill--${stat.iconClass}`}>
                      <span className="status-pill-icon">{stat.icon}</span>
                      <span className="status-pill-dot"></span>
                    </div>
                  </Tooltip>
                ))}
                {liveRpaStatus.is_running && (
                  <>
                    <div className="status-bar-divider" />
                    <Tooltip title={liveRpaStatus.is_paused ? 'Tiếp tục tác vụ' : 'Tạm dừng'} placement="bottomRight">
                      <Button size="small"
                        type={liveRpaStatus.is_paused ? 'primary' : 'default'}
                        icon={liveRpaStatus.is_paused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
                        onClick={handlePause} className="status-bar-ctrl-btn" />
                    </Tooltip>
                    <Tooltip title="Dừng hẳn" placement="bottomRight">
                      <Button size="small" danger icon={<StopOutlined />}
                        onClick={handleStop} className="status-bar-ctrl-btn" />
                    </Tooltip>
                  </>
                )}
                <div className="status-bar-divider" />
                <Tooltip title={headless ? 'Chạy ngầm: BẬT (trình duyệt ẩn)' : 'Chạy ngầm: TẮT (trình duyệt hiện)'} placement="bottomRight">
                  <div className="header-headless-wrap">
                    {headless ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                    <Switch size="small" checked={headless} onChange={handleHeadlessToggle} />
                  </div>
                </Tooltip>
              </div>
              <div className={`connection-status ${status}`}>
                <span className="status-dot"></span>
                <span className="status-text">
                  {status === 'connected' ? 'Backend Online' : status === 'connecting' ? 'Đang kết nối...' : 'Backend Offline'}
                </span>
              </div>
            </div>
          </header>

          {/* Content */}
          <Content className="app-content fade-in">
            <div style={{ display: activeTab === 'dashboard' ? 'block' : 'none' }}>
              {dashboardView}
            </div>
            <div style={{ display: activeTab === 'tasks' ? 'block' : 'none' }}>
              <Tasks taskStatus={taskStatus} progress={progress} userStorageKey={userStorageKey} />
            </div>
            <div style={{ display: activeTab === 'zalo' ? 'block' : 'none' }}>
              <Zalo taskStatus={taskStatus} logs={logs} progress={progress} userStorageKey={userStorageKey} />
            </div>
            <div style={{ display: activeTab === 'sms-gateway' ? 'block' : 'none' }}>
              <SmsGateway userStorageKey={userStorageKey} />
            </div>
            {isAdmin && (
              <div style={{ display: activeTab === 'admin-users' ? 'block' : 'none' }}>
                <AdminUsers currentUser={currentUser} />
              </div>
            )}
          </Content>

          {/* Footer */}
          <footer className="app-footer">
            <div>© 2026 Automation Marketing v2.0.0 - Web Edition</div>
            <div className="app-footer-credit">Trang web được phát triển bởi Huỳnh Hải Đăng</div>
          </footer>
        </div>

        {/* Mobile Bottom Navigation */}
        <nav className="mobile-nav">
          <div className="mobile-nav-items">
            {menuItems.map((item) => (
              <div
                key={item.key}
                className={`mobile-nav-item ${activeTab === item.key ? 'active' : ''}`}
                onClick={() => setActiveTab(item.key)}
              >
                {item.icon}
                <span>{item.label.split(' ')[0]}</span>
              </div>
            ))}
          </div>
        </nav>
      </Layout>

      <Tooltip title={`Hướng dẫn tab ${pageTitles[activeTab] || ''}`} placement="left">
        <Button
          className="help-float-btn"
          type="primary"
          shape="circle"
          size="large"
          icon={<BookOutlined />}
          onClick={() => setIsGuideOpen(true)}
        />
      </Tooltip>

      <Drawer
        title={activeGuide.title}
        placement="right"
        open={isGuideOpen}
        onClose={() => setIsGuideOpen(false)}
        width={420}
        className="help-guide-drawer"
      >
        <div className="help-guide-content">
          <p className="help-guide-summary">{activeGuide.summary}</p>
          <ol className="help-guide-list">
            {activeGuide.steps.map((step, idx) => (
              <li key={`${activeGuide.title}-${idx}`}>{step}</li>
            ))}
          </ol>
        </div>
      </Drawer>

      <Modal
        title="Đổi mật khẩu"
        open={showChangePassword}
        onOk={handleChangePassword}
        onCancel={() => {
          setShowChangePassword(false);
          changePwdForm.resetFields();
        }}
        okText="Lưu"
        cancelText="Hủy"
      >
        <Form layout="vertical" form={changePwdForm}>
          <Form.Item name="current_password" label="Mật khẩu hiện tại" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="new_password" label="Mật khẩu mới" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </ConfigProvider>
  );
}

export default App;
