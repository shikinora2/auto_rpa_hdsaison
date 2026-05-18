import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import Zalo from '../pages/Zalo/Zalo';
import { zaloAPI } from '../services/api';

vi.mock('../services/api', () => ({
  zaloAPI: {
    getSession: vi.fn(),
    sendMessages: vi.fn(),
    addFriends: vi.fn(),
  },
  filesAPI: {
    parseExcel: vi.fn(),
    upload: vi.fn(),
    templateUrl: vi.fn(),
  },
}));

describe('Zalo actions', () => {
  const userStorageKey = 'u_test';

  beforeEach(() => {
    localStorage.clear();
    zaloAPI.getSession.mockResolvedValue({ data: { is_active: true } });
    zaloAPI.sendMessages.mockResolvedValue({});
    zaloAPI.addFriends.mockResolvedValue({});

    localStorage.setItem(
      `auto_rpa:${userStorageKey}:zalo.customers`,
      JSON.stringify([
        { _key: 1, phone: '0901111222', name: 'Test User', contract_id: 'HD01' },
      ])
    );
    localStorage.setItem(
      `auto_rpa:${userStorageKey}:zalo.messageTemplate`,
      JSON.stringify('Xin chao {name}')
    );
    localStorage.setItem(
      `auto_rpa:${userStorageKey}:zalo.greetingTemplate`,
      JSON.stringify('Chao ban {name}')
    );
  });

  it('starts bulk send messages', async () => {
    render(
      <Zalo
        taskStatus={null}
        logs={[]}
        progress={null}
        userStorageKey={userStorageKey}
      />
    );

    await waitFor(() => {
      expect(zaloAPI.getSession).toHaveBeenCalled();
    });

    await userEvent.click(screen.getByRole('button', { name: /Gửi tin nhắn hàng loạt/i }));

    await waitFor(() => {
      expect(zaloAPI.sendMessages).toHaveBeenCalledWith({
        customers: [{ phone: '0901111222', name: 'Test User', contract_id: 'HD01' }],
        message_template: 'Xin chao {name}',
        check_friend_status: true,
        attachment_filename: null,
      });
    });
  });

  it('starts bulk add friends', async () => {
    render(
      <Zalo
        taskStatus={null}
        logs={[]}
        progress={null}
        userStorageKey={userStorageKey}
      />
    );

    await waitFor(() => {
      expect(zaloAPI.getSession).toHaveBeenCalled();
    });

    await userEvent.click(screen.getByRole('button', { name: /Kết bạn hàng loạt/i }));

    await waitFor(() => {
      expect(zaloAPI.addFriends).toHaveBeenCalledWith({
        customers: [{ phone: '0901111222', name: 'Test User', contract_id: 'HD01' }],
        greeting_template: 'Chao ban {name}',
      });
    });
  });
});
