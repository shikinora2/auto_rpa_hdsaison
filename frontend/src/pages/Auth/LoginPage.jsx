import { useState } from 'react';
import { Card, Tabs, Form, Input, Button, Alert, message, Typography, Space } from 'antd';
import { LockOutlined, UserOutlined, MailOutlined, SafetyCertificateOutlined } from '@ant-design/icons';

import { authAPI } from '../../services/api';
import './LoginPage.css';

const { Title, Text } = Typography;

function mapAuthError(error, fallback) {
  const detail = String(error?.response?.data?.detail || '').toLowerCase();

  if (detail.includes('invalid credentials')) return 'Thông tin đăng nhập không chính xác. Vui lòng kiểm tra lại.';
  if (detail.includes('pending approval')) return 'Tài khoản của bạn đang chờ quản trị viên phê duyệt.';
  if (detail.includes('too many failed')) return 'Bạn đã đăng nhập sai quá nhiều lần. Vui lòng thử lại sau ít phút.';
  if (detail.includes('username already exists')) return 'Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.';
  if (detail.includes('email already exists')) return 'Email đã được sử dụng. Vui lòng dùng email khác.';
  if (detail.includes('invalid or expired reset token')) return 'Mã đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.';

  return fallback;
}

export default function LoginPage({ onLoginSuccess }) {
  const [loading, setLoading] = useState(false);
  const [forgotInfo, setForgotInfo] = useState('');

  const handleLogin = async (values) => {
    setLoading(true);
    try {
      const { data } = await authAPI.login(values);
      message.success('Đăng nhập thành công. Chào mừng bạn quay lại.');
      onLoginSuccess?.(data.user || null);
    } catch (error) {
      message.error(mapAuthError(error, 'Không thể đăng nhập vào hệ thống. Vui lòng thử lại.'));
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values) => {
    setLoading(true);
    try {
      await authAPI.register(values);
      message.success('Đăng ký thành công. Tài khoản của bạn đang ở trạng thái chờ phê duyệt.');
    } catch (error) {
      message.error(mapAuthError(error, 'Không thể hoàn tất đăng ký. Vui lòng kiểm tra lại thông tin.'));
    } finally {
      setLoading(false);
    }
  };

  const handleForgot = async (values) => {
    setLoading(true);
    try {
      const { data } = await authAPI.forgotPassword(values);
      setForgotInfo(data?.message || 'Nếu tài khoản tồn tại, hệ thống đã ghi nhận yêu cầu đặt lại mật khẩu.');
      message.success('Yêu cầu đặt lại mật khẩu đã được ghi nhận.');
    } catch (error) {
      message.error(mapAuthError(error, 'Không thể xử lý yêu cầu quên mật khẩu. Vui lòng thử lại.'));
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (values) => {
    setLoading(true);
    try {
      await authAPI.resetPassword(values);
      message.success('Đặt lại mật khẩu thành công. Vui lòng đăng nhập lại bằng mật khẩu mới.');
    } catch (error) {
      message.error(mapAuthError(error, 'Không thể đặt lại mật khẩu. Vui lòng kiểm tra lại mã xác thực.'));
    } finally {
      setLoading(false);
    }
  };

  const items = [
    {
      key: 'login',
      label: 'Đăng nhập',
      children: (
        <div className="login-tab-content">
          <Alert
            type="info"
            showIcon
            className="login-admin-alert"
            title="Tài khoản quản trị để kiểm thử"
            description="admin / 123456"
          />
          <Form
            layout="vertical"
            onFinish={handleLogin}
            initialValues={{ username: 'admin', password: '123456' }}
            requiredMark={false}
          >
            <Form.Item name="username" label="Tên đăng nhập hoặc Email" rules={[{ required: true, message: 'Vui lòng nhập tài khoản' }]}>
              <Input prefix={<UserOutlined />} size="large" autoComplete="username" />
            </Form.Item>
            <Form.Item name="password" label="Mật khẩu" rules={[{ required: true, message: 'Vui lòng nhập mật khẩu' }]}>
              <Input.Password prefix={<LockOutlined />} size="large" autoComplete="current-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large" className="login-primary-btn">
              Đăng nhập
            </Button>
          </Form>
        </div>
      ),
    },
    {
      key: 'register',
      label: 'Đăng ký',
      children: (
        <div className="login-tab-content">
          <Alert
            type="warning"
            showIcon
            className="login-register-alert"
            title="Tài khoản mới cần phê duyệt"
            description="Sau khi đăng ký, bạn cần chờ quản trị viên phê duyệt trước khi đăng nhập."
          />
          <Form layout="vertical" onFinish={handleRegister} requiredMark={false}>
            <Form.Item name="username" label="Tên đăng nhập" rules={[{ required: true, min: 3, message: 'Tên đăng nhập tối thiểu 3 ký tự' }]}>
              <Input prefix={<UserOutlined />} size="large" />
            </Form.Item>
            <Form.Item name="email" label="Email">
              <Input prefix={<MailOutlined />} size="large" />
            </Form.Item>
            <Form.Item name="password" label="Mật khẩu" rules={[{ required: true, min: 6, message: 'Mật khẩu tối thiểu 6 ký tự' }]}>
              <Input.Password prefix={<LockOutlined />} size="large" />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large" className="login-primary-btn">
              Đăng ký tài khoản
            </Button>
          </Form>
        </div>
      ),
    },
    {
      key: 'forgot',
      label: 'Quên mật khẩu',
      children: (
        <div className="login-tab-content">
          {forgotInfo && <Alert type="info" showIcon title={forgotInfo} style={{ marginBottom: 12 }} />}
          <Form layout="vertical" onFinish={handleForgot} requiredMark={false}>
            <Form.Item name="username_or_email" label="Username hoặc Email" rules={[{ required: true }]}>
              <Input prefix={<UserOutlined />} size="large" />
            </Form.Item>
            <Button type="default" htmlType="submit" loading={loading} block size="large">
              Gửi yêu cầu đặt lại mật khẩu
            </Button>
          </Form>

          <div style={{ marginTop: 18 }}>
            <Form layout="vertical" onFinish={handleReset} requiredMark={false}>
              <Form.Item name="reset_token" label="Mã đặt lại mật khẩu" rules={[{ required: true, message: 'Vui lòng nhập mã xác thực' }]}>
                <Input size="large" />
              </Form.Item>
              <Form.Item name="new_password" label="Mật khẩu mới" rules={[{ required: true, min: 6, message: 'Mật khẩu tối thiểu 6 ký tự' }]}>
                <Input.Password prefix={<LockOutlined />} size="large" />
              </Form.Item>
              <Button htmlType="submit" loading={loading} block size="large" className="login-primary-btn" type="primary">
                Đặt lại mật khẩu
              </Button>
            </Form>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="login-page">
      <Card className="login-card" variant="borderless">
        <Space orientation="vertical" size={4} style={{ width: '100%', marginBottom: 16 }}>
          <Title level={3} className="login-title">Automation Marketing</Title>
          <Text className="login-subtitle">Nền tảng vận hành RPA và chăm sóc khách hàng</Text>
          <Space size={8} className="login-security-note">
            <SafetyCertificateOutlined />
            <Text>Phiên làm việc được bảo vệ bằng cookie phiên bảo mật.</Text>
          </Space>
        </Space>

        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 12 }}
          title="Vui lòng đăng nhập để tiếp tục"
          description="Chỉ tài khoản đã được duyệt mới có thể truy cập hệ thống."
        />

        <Tabs items={items} className="login-tabs" />
      </Card>
    </div>
  );
}
