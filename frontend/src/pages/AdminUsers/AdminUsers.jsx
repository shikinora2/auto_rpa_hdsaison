import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined, SafetyOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { authAPI } from '../../services/api';
import './AdminUsers.css';

export default function AdminUsers({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [openCreate, setOpenCreate] = useState(false);
  const [openEdit, setOpenEdit] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await authAPI.listUsers();
      setUsers(Array.isArray(data?.users) ? data.users : []);
    } catch (error) {
      message.error(error?.response?.data?.detail || 'Không tải được danh sách user');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const handleApprove = async (row) => {
    try {
      await authAPI.approveUser(row.id);
      message.success(`Đã phê duyệt tài khoản ${row.username}`);
      await loadUsers();
    } catch (error) {
      message.error(error?.response?.data?.detail || 'Không thể phê duyệt user');
    }
  };

  const handleDelete = async (row) => {
    try {
      await authAPI.deleteUser(row.id);
      message.success(`Đã xóa tài khoản ${row.username}`);
      await loadUsers();
    } catch (error) {
      message.error(error?.response?.data?.detail || 'Không thể xóa user');
    }
  };

  const openEditModal = (row) => {
    setEditingUser(row);
    editForm.setFieldsValue({
      username: row.username,
      email: row.email || '',
      role: row.role || 'user',
      is_active: Boolean(row.is_active),
      password: '',
    });
    setOpenEdit(true);
  };

  const submitCreate = async () => {
    try {
      const values = await createForm.validateFields();
      await authAPI.createUser({
        username: values.username,
        email: values.email || null,
        password: values.password,
        role: values.role,
        is_active: values.is_active,
        full_name: values.full_name || null,
      });
      message.success('Tạo user thành công');
      setOpenCreate(false);
      createForm.resetFields();
      await loadUsers();
    } catch (error) {
      if (error?.errorFields) return;
      message.error(error?.response?.data?.detail || 'Không thể tạo user');
    }
  };

  const submitEdit = async () => {
    if (!editingUser) return;
    try {
      const values = await editForm.validateFields();
      const payload = {
        username: values.username,
        email: values.email || null,
        role: values.role,
        is_active: values.is_active,
      };
      if (values.password) payload.password = values.password;
      await authAPI.updateUser(editingUser.id, payload);
      message.success('Cập nhật user thành công');
      setOpenEdit(false);
      setEditingUser(null);
      editForm.resetFields();
      await loadUsers();
    } catch (error) {
      if (error?.errorFields) return;
      message.error(error?.response?.data?.detail || 'Không thể cập nhật user');
    }
  };

  const columns = [
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
      width: 180,
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
      render: (value) => value || <span style={{ color: '#94a3b8' }}>Chưa có</span>,
    },
    {
      title: 'Vai trò',
      dataIndex: 'role',
      key: 'role',
      width: 110,
      render: (value) => <Tag color={value === 'admin' ? 'gold' : 'blue'}>{value || 'user'}</Tag>,
    },
    {
      title: 'Trạng thái',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 140,
      render: (active) => active ? <Tag color="green">Đã duyệt</Tag> : <Tag color="orange">Chờ duyệt</Tag>,
    },
    {
      title: 'Ngày tạo',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (value) => value ? dayjs(value).format('DD/MM/YYYY HH:mm') : '-',
    },
    {
      title: 'Thao tác',
      key: 'actions',
      width: 220,
      render: (_, row) => (
        <Space>
          {!row.is_active && (
            <Button size="small" type="primary" icon={<SafetyOutlined />} onClick={() => handleApprove(row)}>
              Duyệt
            </Button>
          )}
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditModal(row)}>
            Sửa
          </Button>
          <Popconfirm
            title={`Xóa user ${row.username}?`}
            okText="Xóa"
            cancelText="Hủy"
            okButtonProps={{ danger: true }}
            onConfirm={() => handleDelete(row)}
            disabled={row.id === currentUser?.id}
          >
            <Button size="small" danger icon={<DeleteOutlined />} disabled={row.id === currentUser?.id}>
              Xóa
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="admin-users-page">
      <div className="admin-users-toolbar">
        <div>
          <h3 className="admin-users-title">Quản lý tài khoản hệ thống</h3>
          <p className="admin-users-subtitle">Tạo, phê duyệt và phân quyền người dùng</p>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => void loadUsers()} loading={loading}>
            Tải lại
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpenCreate(true)}>
            Thêm user
          </Button>
        </Space>
      </div>

      <Alert
        type="info"
        showIcon
        message="Khuyến nghị"
        description="Tài khoản mới nên để trạng thái chờ duyệt, chỉ bật hoạt động khi đã xác minh thông tin."
      />

      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={users}
        className="admin-users-table"
        pagination={{ pageSize: 10, showSizeChanger: false }}
      />

      <Modal
        title="Tạo user mới"
        open={openCreate}
        onOk={submitCreate}
        onCancel={() => {
          setOpenCreate(false);
          createForm.resetFields();
        }}
        okText="Tạo"
        cancelText="Hủy"
      >
        <Form layout="vertical" form={createForm} initialValues={{ role: 'user', is_active: false }}>
          <Form.Item name="username" label="Username" rules={[{ required: true, min: 3 }]}>
            <Input />
          </Form.Item>
          <Form.Item name="full_name" label="Họ tên">
            <Input />
          </Form.Item>
          <Form.Item name="email" label="Email">
            <Input />
          </Form.Item>
          <Form.Item name="password" label="Mật khẩu" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="role" label="Vai trò" rules={[{ required: true }]}>
            <Select options={[{ label: 'User', value: 'user' }, { label: 'HDSaison', value: 'hdsaison' }, { label: 'Admin', value: 'admin' }]} />
          </Form.Item>
          <Form.Item name="is_active" label="Trạng thái" rules={[{ required: true }]}>
            <Select options={[{ label: 'Chờ duyệt', value: false }, { label: 'Đã duyệt', value: true }]} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`Cập nhật user: ${editingUser?.username || ''}`}
        open={openEdit}
        onOk={submitEdit}
        onCancel={() => {
          setOpenEdit(false);
          setEditingUser(null);
          editForm.resetFields();
        }}
        okText="Lưu"
        cancelText="Hủy"
      >
        <Form layout="vertical" form={editForm}>
          <Form.Item name="username" label="Username" rules={[{ required: true, min: 3 }]}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label="Email">
            <Input />
          </Form.Item>
          <Form.Item name="password" label="Mật khẩu mới (bỏ trống nếu không đổi)">
            <Input.Password />
          </Form.Item>
          <Form.Item name="role" label="Vai trò" rules={[{ required: true }]}>
            <Select options={[{ label: 'User', value: 'user' }, { label: 'HDSaison', value: 'hdsaison' }, { label: 'Admin', value: 'admin' }]} />
          </Form.Item>
          <Form.Item name="is_active" label="Trạng thái" rules={[{ required: true }]}>
            <Select options={[{ label: 'Chờ duyệt', value: false }, { label: 'Đã duyệt', value: true }]} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
