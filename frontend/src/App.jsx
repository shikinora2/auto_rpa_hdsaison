import { useState, useEffect } from 'react';
import { ConfigProvider, Layout, Menu, theme, Switch, Tooltip, Button, message } from 'antd';
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
} from '@ant-design/icons';

import { configAPI, rpaAPI, zaloAPI } from './services/api';
import Dashboard from './pages/Dashboard';
import Tasks from './pages/Tasks';
import Zalo from './pages/Zalo';
import SmsGateway from './pages/SmsGateway';
import ConsoleLog from './components/ConsoleLog';
import { useWebSocket } from './hooks/useWebSocket';

import './App.css';

dayjs.locale('vi');

const { Sider, Content } = Layout;

// Menu items configuration
const menuItems = [
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
};

const TASK_LABELS = {
  check_contracts: 'Kiểm tra HĐ',
  download_files: 'Tải file PDF/JSON',
  scrape_details: 'Cào chi tiết → Excel',
  login: 'Đăng nhập HPO',
  zalo_login: 'Login Zalo',
  send_messages: 'Gửi tin nhắn Zalo',
  add_friends: 'Kết bạn Zalo',
};

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const { logs, status, progress, taskStatus, qrImage, clearLogs } = useWebSocket();

  // System status — shared across header
  const [headless, setHeadless] = useState(false);
  const [sessionStatus, setSessionStatus] = useState({ is_logged_in: false, checking: true });
  const [rpaStatus, setRpaStatus] = useState({ is_running: false, is_paused: false });

  useEffect(() => {
    (async () => {
      try { const { data } = await configAPI.get(); setHeadless(data.headless || false); } catch {}
      try { const { data } = await rpaAPI.getStatus(); setRpaStatus(data); } catch {}
      try {
        const { data } = await rpaAPI.checkSession();
        setSessionStatus({ is_logged_in: data.is_logged_in, checking: false });
      } catch { setSessionStatus({ is_logged_in: false, checking: false }); }
    })();
  }, []);

  useEffect(() => {
    if (!taskStatus) return;
    const task = taskStatus.data?.task;
    const st = taskStatus.status;
    if (st === 'running' || st === 'paused') setRpaStatus({ is_running: true, is_paused: st === 'paused' });
    if (st === 'completed' || st === 'error' || st === 'stopping') setRpaStatus({ is_running: false, is_paused: false });
    if (task === 'login' && st === 'completed') setSessionStatus({ is_logged_in: true, checking: false });
  }, [taskStatus]);

  const handleHeadlessToggle = async (val) => {
    setHeadless(val);
    try { await configAPI.update({ headless: val }); } catch {}
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
        if (rpaStatus.is_paused) { await zaloAPI.resume(); message.info('Đã tiếp tục tác vụ Zalo'); }
        else { await zaloAPI.pause(); message.warning('Đã tạm dừng tác vụ Zalo'); }
        // rpaStatus được cập nhật tự động qua WebSocket broadcast từ backend
      } else {
        if (rpaStatus.is_paused) { await rpaAPI.resume(); message.info('Đã tiếp tục tác vụ'); }
        else { await rpaAPI.pause(); message.warning('Đã tạm dừng tác vụ'); }
        const { data } = await rpaAPI.getStatus();
        setRpaStatus(data);
      }
    } catch {}
  };

  const handleStop = async () => {
    try {
      if (isZaloTask) { await zaloAPI.stop(); message.warning('Đang dừng tác vụ Zalo...'); }
      else { await rpaAPI.stop(); message.warning('Đang dừng tác vụ...'); }
    } catch {}
  };

  const currentTaskName = TASK_LABELS[taskStatus?.data?.task] || null;
  const statusInfo = (() => {
    if (rpaStatus.is_running) {
      if (rpaStatus.is_paused) return { text: 'Tạm dừng' };
      return { text: 'Đang chạy' };
    }
    return { text: 'Sẵn sàng' };
  })();

  const headerStats = [
    {
      key: 'session',
      label: 'Phiên HPO',
      value: sessionStatus.checking ? 'Kiểm tra...' : sessionStatus.is_logged_in ? 'Đã đăng nhập' : 'Chưa đăng nhập',
      icon: <WifiOutlined />,
      iconClass: sessionStatus.checking ? 'warning' : sessionStatus.is_logged_in ? 'success' : 'error',
    },
    {
      key: 'rpa',
      label: 'RPA',
      value: statusInfo.text,
      icon: <RobotOutlined />,
      iconClass: rpaStatus.is_running ? (rpaStatus.is_paused ? 'warning' : 'success') : 'info',
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

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard
          taskStatus={taskStatus} wsStatus={status} progress={progress}
          headless={headless} onHeadlessChange={handleHeadlessToggle}
          sessionStatus={sessionStatus} onVerifySession={handleVerifySession}
          onSessionUpdate={setSessionStatus} rpaStatus={rpaStatus}
          qrImage={qrImage}
        />;
      case 'tasks':
        return <Tasks taskStatus={taskStatus} progress={progress} />;
      case 'zalo':
        return <Zalo taskStatus={taskStatus} />;
      case 'sms-gateway':
        return <SmsGateway />;
      default:
        return <Dashboard
          taskStatus={taskStatus} wsStatus={status} progress={progress}
          headless={headless} onHeadlessChange={handleHeadlessToggle}
          sessionStatus={sessionStatus} onVerifySession={handleVerifySession}
          onSessionUpdate={setSessionStatus} rpaStatus={rpaStatus}
          qrImage={qrImage}
        />;
    }
  };

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
              <RobotOutlined />
            </div>
            <div className="sidebar-logo-text">
              <span className="sidebar-logo-brand">HD SAISON</span>
              <span className="sidebar-logo-sub">RPA Automation</span>
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
                {headerStats.map(stat => (
                  <Tooltip key={stat.key} title={<span><b>{stat.label}</b><br />{stat.value}</span>} placement="bottomRight">
                    <div className={`status-pill status-pill--${stat.iconClass}`}>
                      <span className="status-pill-icon">{stat.icon}</span>
                      <span className="status-pill-dot"></span>
                    </div>
                  </Tooltip>
                ))}
                {rpaStatus.is_running && (
                  <>
                    <div className="status-bar-divider" />
                    <Tooltip title={rpaStatus.is_paused ? 'Tiếp tục tác vụ' : 'Tạm dừng'} placement="bottomRight">
                      <Button size="small"
                        type={rpaStatus.is_paused ? 'primary' : 'default'}
                        icon={rpaStatus.is_paused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
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
          <Content className="app-content fade-in" key={activeTab}>
            {renderContent()}
          </Content>

          {/* Console */}
          <div className="console-wrapper">
            <ConsoleLog
              logs={logs}
              status={status}
              progress={progress}
              onClear={clearLogs}
            />
          </div>

          {/* Footer */}
          <footer className="app-footer">
            © 2024 HD SAISON RPA Tool v2.0.0 - Web Edition
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
    </ConfigProvider>
  );
}

export default App;
