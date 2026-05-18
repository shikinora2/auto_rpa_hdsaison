import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import App from '../App';
import { authAPI, zaloAPI } from '../services/api';

let mockTaskStatus = null;

vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    logs: [],
    status: 'connected',
    progress: null,
    taskStatus: mockTaskStatus,
    qrImage: null,
  }),
}));

vi.mock('../pages/Dashboard', () => ({
  default: () => <div>Dashboard</div>,
}));

vi.mock('../pages/Tasks', () => ({
  default: () => <div>Tasks</div>,
}));

vi.mock('../pages/Zalo', () => ({
  default: () => <div>Zalo</div>,
}));

vi.mock('../pages/SmsGateway', () => ({
  default: () => <div>SmsGateway</div>,
}));

vi.mock('../pages/AdminUsers', () => ({
  default: () => <div>AdminUsers</div>,
}));

vi.mock('../services/api', () => ({
  authAPI: {
    me: vi.fn(),
    logout: vi.fn(),
    changePassword: vi.fn(),
  },
  configAPI: {
    get: vi.fn(),
    update: vi.fn(),
  },
  rpaAPI: {
    getStatus: vi.fn(),
    checkSession: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    stop: vi.fn(),
    verifySession: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
  zaloAPI: {
    pause: vi.fn(),
    resume: vi.fn(),
    stop: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
  adminCleanupAPI: {
    resetRuntime: vi.fn(),
  },
}));

describe('App Zalo controls', () => {
  beforeEach(() => {
    mockTaskStatus = null;
    authAPI.me.mockResolvedValue({
      data: { user: { id: 7, username: 'user1', role: 'user' } },
    });
    authAPI.logout.mockResolvedValue({});
    zaloAPI.pause.mockResolvedValue({});
    zaloAPI.resume.mockResolvedValue({});
    zaloAPI.stop.mockResolvedValue({});
  });

  it('calls Zalo pause when task is running', async () => {
    mockTaskStatus = { status: 'running', data: { task: 'send_messages' } };

    render(<App />);

    await screen.findByRole('button', { name: 'Đăng xuất' });

    await userEvent.click(screen.getByRole('button', { name: 'Tạm dừng tác vụ' }));

    await waitFor(() => {
      expect(zaloAPI.pause).toHaveBeenCalled();
    });
  });

  it('calls Zalo resume when task is paused', async () => {
    mockTaskStatus = { status: 'paused', data: { task: 'send_messages' } };

    render(<App />);

    await screen.findByRole('button', { name: 'Đăng xuất' });

    await userEvent.click(screen.getByRole('button', { name: 'Tiếp tục tác vụ' }));

    await waitFor(() => {
      expect(zaloAPI.resume).toHaveBeenCalled();
    });
  });

  it('calls Zalo stop when task is running', async () => {
    mockTaskStatus = { status: 'running', data: { task: 'send_messages' } };

    render(<App />);

    await screen.findByRole('button', { name: 'Đăng xuất' });

    await userEvent.click(screen.getByRole('button', { name: 'Dừng hẳn' }));

    await waitFor(() => {
      expect(zaloAPI.stop).toHaveBeenCalled();
    });
  });

  it('logs out from header', async () => {
    mockTaskStatus = null;

    render(<App />);

    const logoutButton = await screen.findByRole('button', { name: 'Đăng xuất' });
    await userEvent.click(logoutButton);

    await waitFor(() => {
      expect(authAPI.logout).toHaveBeenCalled();
    });
  });
});
