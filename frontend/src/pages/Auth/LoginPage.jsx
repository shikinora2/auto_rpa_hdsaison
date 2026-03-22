import { useState } from 'react';
import { Card, Tabs, Form, Input, Button, Alert, message } from 'antd';
import { LockOutlined, UserOutlined, MailOutlined } from '@ant-design/icons';

import { authAPI } from '../../services/api';

export default function LoginPage({ onLoginSuccess }) {
  const [loading, setLoading] = useState(false);
  const [resetToken, setResetToken] = useState('');
  const [forgotInfo, setForgotInfo] = useState('');

  const handleLogin = async (values) => {
    setLoading(true);
    try {
      const { data } = await authAPI.login(values);
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      localStorage.setItem('current_user', JSON.stringify(data.user || {}));
      message.success('Đăng nhập thành công');
      onLoginSuccess?.(data.user || null);
    } catch (error) {
      message.error(error.response?.data?.detail || 'Đăng nhập thất bại');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values) => {
    setLoading(true);
    try {
      await authAPI.register(values);
      message.success('Đăng ký thành công. Vui lòng đăng nhập.');
    } catch (error) {
      message.error(error.response?.data?.detail || 'Đăng ký thất bại');
    } finally {
      setLoading(false);
    }
  };

  const handleForgot = async (values) => {
    setLoading(true);
    try {
      const { data } = await authAPI.forgotPassword(values);
      if (data?.reset_token) {
        setResetToken(data.reset_token);
      }
      setForgotInfo(data?.message || 'Đã xử lý yêu cầu quên mật khẩu');
      message.success('Đã tạo token reset');
    } catch (error) {
      message.error(error.response?.data?.detail || 'Không thể xử lý quên mật khẩu');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (values) => {
    setLoading(true);
    try {
      await authAPI.resetPassword(values);
      message.success('Đặt lại mật khẩu thành công. Vui lòng đăng nhập lại.');
    } catch (error) {
      message.error(error.response?.data?.detail || 'Reset mật khẩu thất bại');
    } finally {
      setLoading(false);
    }
  };

  const items = [
    {
      key: 'login',
      label: 'Đăng nhập',
      children: (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="Tài khoản mặc định quản trị"
            description="username: admin | password: 123456"
          />
          <Form
            layout="vertical"
            onFinish={handleLogin}
            initialValues={{ username: 'admin', password: '123456' }}
          >
          <Form.Item name="username" label="Username hoặc Email" rules={[{ required: true }]}>
            <Input prefix={<UserOutlined />} />
          </Form.Item>
          <Form.Item name="password" label="Mật khẩu" rules={[{ required: true }]}>
            <Input.Password prefix={<LockOutlined />} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            Đăng nhập
          </Button>
          </Form>
        </>
      ),
    },
    {
      key: 'register',
      label: 'Đăng ký',
      children: (
        <Form layout="vertical" onFinish={handleRegister}>
          <Form.Item name="username" label="Username" rules={[{ required: true, min: 3 }]}>
            <Input prefix={<UserOutlined />} />
          </Form.Item>
          <Form.Item name="email" label="Email">
            <Input prefix={<MailOutlined />} />
          </Form.Item>
          <Form.Item name="password" label="Mật khẩu" rules={[{ required: true, min: 6 }]}>
            <Input.Password prefix={<LockOutlined />} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            Tạo tài khoản
          </Button>
        </Form>
      ),
    },
    {
      key: 'forgot',
      label: 'Quên mật khẩu',
      children: (
        <>
          {forgotInfo && <Alert type="info" showIcon message={forgotInfo} style={{ marginBottom: 12 }} />}
          {resetToken && <Alert type="warning" showIcon message={`Reset token (MVP): ${resetToken}`} style={{ marginBottom: 12 }} />}
          <Form layout="vertical" onFinish={handleForgot}>
            <Form.Item name="username_or_email" label="Username hoặc Email" rules={[{ required: true }]}>
              <Input prefix={<UserOutlined />} />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              Tạo token reset
            </Button>
          </Form>

          <div style={{ marginTop: 18 }}>
            <Form layout="vertical" onFinish={handleReset}>
              <Form.Item name="reset_token" label="Reset token" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name="new_password" label="Mật khẩu mới" rules={[{ required: true, min: 6 }]}>
                <Input.Password prefix={<LockOutlined />} />
              </Form.Item>
              <Button htmlType="submit" loading={loading} block>
                Đặt lại mật khẩu
              </Button>
            </Form>
          </div>
        </>
      ),
    },
  ];

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 20, background: 'radial-gradient(circle at top, #1e293b, #0f172a)' }}>
      <Card title="Automation Marketing - Hệ thống xác thực" style={{ width: 480, maxWidth: '100%', borderRadius: 12 }}>
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 12 }}
          message="Đăng nhập bắt buộc"
          description="Vui lòng đăng nhập để sử dụng toàn bộ chức năng hệ thống."
        />
        <Tabs items={items} />
      </Card>
    </div>
  );
}
