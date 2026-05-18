import { test, expect } from '@playwright/test';

const QR_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII=';

async function mockApi(page) {
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        user: { id: 10, username: 'demo_user', role: 'user' },
      }),
    });
  });

  await page.route('**/api/zalo/session**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        is_active: false,
        is_running: false,
        current_task: null,
        zalo_name: '',
      }),
    });
  });

  await page.route('**/api/zalo/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'started',
        message: 'Đang khởi tạo đăng nhập Zalo chạy ngầm, vui lòng quét mã QR',
      }),
    });
  });

  await page.route('**/api/zalo/qr', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        qr_base64: QR_BASE64,
        is_running: true,
        current_task: 'zalo_login',
      }),
    });
  });
}

test('Hien thi QR khi dang nhap Zalo', async ({ page }) => {
  await page.addInitScript(() => {
    class MockWebSocket {
      constructor() {
        this.readyState = 1;
      }
      close() {}
      send() {}
      addEventListener() {}
      removeEventListener() {}
    }
    window.WebSocket = MockWebSocket;
  });

  await mockApi(page);

  await page.goto('/dashboard');

  await expect(page.getByText('Quản lý tài khoản Zalo')).toBeVisible();

  await page.getByRole('button', { name: 'Đăng nhập Zalo' }).click();

  const qrImage = page.getByAltText('Zalo QR Code');
  await expect(qrImage).toBeVisible();
  await expect(page.getByText('Quét mã QR bằng ứng dụng Zalo')).toBeVisible();
});
