import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import LoginPage from '../pages/Auth/LoginPage';
import { authAPI } from '../services/api';

vi.mock('../services/api', () => ({
  authAPI: {
    login: vi.fn(),
    register: vi.fn(),
    forgotPassword: vi.fn(),
    resetPassword: vi.fn(),
  },
}));

describe('LoginPage', () => {
  beforeEach(() => {
    authAPI.login.mockReset();
  });

  it('submits login and returns user', async () => {
    authAPI.login.mockResolvedValue({
      data: { user: { id: 1, username: 'tester' } },
    });
    const onLoginSuccess = vi.fn();

    render(<LoginPage onLoginSuccess={onLoginSuccess} />);

    const loginButton = screen.getByRole('button', { name: 'Đăng nhập' });
    const form = loginButton.closest('form');
    const formScope = within(form);

    await userEvent.clear(formScope.getByLabelText('Tên đăng nhập hoặc Email'));
    await userEvent.type(formScope.getByLabelText('Tên đăng nhập hoặc Email'), 'tester');
    await userEvent.clear(formScope.getByLabelText('Mật khẩu'));
    await userEvent.type(formScope.getByLabelText('Mật khẩu'), 'Pass@123');

    await userEvent.click(loginButton);

    await waitFor(() => {
      expect(authAPI.login).toHaveBeenCalledWith({ username: 'tester', password: 'Pass@123' });
    });
    expect(onLoginSuccess).toHaveBeenCalledWith({ id: 1, username: 'tester' });
  });
});
