import { expect, test } from '@playwright/test';
import QRCode from 'qrcode';

test('security manager previews, dismisses, and explicitly captures a visitor QR', async ({ page }, testInfo) => {
  const qrImage = await QRCode.toDataURL('test-visitor-pass', { width: 240 });
  await page.addInitScript(({ qrImage }) => {
    window.__qrDecodes = 0;
    window.__cameraStreams = [];
    window.EventSource = class {
      addEventListener() {}
      close() {}
    };
    // Use a real video stream from a canvas, with deterministic camera/decoder
    // inputs. This exercises native dialog, media playback, and frame capture.
    navigator.mediaDevices.getUserMedia = async () => {
      const canvas = document.createElement('canvas');
      canvas.width = 640;
      canvas.height = 480;
      const context = canvas.getContext('2d');
      const picture = new Image();
      picture.src = qrImage;
      await picture.decode();
      context.fillStyle = '#cbd5e1';
      context.fillRect(0, 0, 640, 480);
      context.drawImage(picture, 200, 120);
      const stream = canvas.captureStream(10);
      window.__cameraStreams.push(stream);
      return stream;
    };
    window.BarcodeDetector = class {
      async detect(frame) {
        if (!(frame instanceof HTMLCanvasElement) || frame.width !== 640 || frame.height !== 480) {
          throw new Error('Expected a captured camera frame');
        }
        window.__qrDecodes += 1;
        return [{ rawValue: 'test-visitor-pass' }];
      }
    };
  }, { qrImage });
  const verifications = [];
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/session') return route.fulfill({ json: {
      identity: { id: 'manager-user', email: 'manager@example.test', full_name: 'Security manager' },
      membership: { id: 'membership-1', community_id: 'community-1', role: 'manager', department_id: 'security-1' },
      portal: 'security-manager', onboarding_eligible: false,
    } });
    if (path === '/api/v1/notifications') return route.fulfill({ json: { items: [], unread: 0 } });
    if (path.endsWith('/offline-bundle')) return route.fulfill({ json: { passes: [] } });
    if (path.endsWith('/gate/verify')) {
      verifications.push(route.request().postDataJSON());
      return route.fulfill({ json: { verdict: 'admitted', detail: 'Visitor verified from captured picture.' } });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto('/security-manager/gate');
  const start = page.getByRole('button', { name: 'Start QR camera scanner' });
  await start.click();
  const dialog = page.getByRole('dialog', { name: 'Scan visitor QR' });
  await expect(dialog).toBeVisible();
  await expect(page.getByRole('button', { name: 'Take picture' })).toBeEnabled();
  expect(await page.evaluate(() => window.__qrDecodes)).toBe(0);
  expect(verifications).toEqual([]);
  await page.keyboard.press('Tab');
  expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true);
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(start).toBeFocused();
  expect(await page.evaluate(() => window.__cameraStreams[0].getTracks()[0].readyState)).toBe('ended');

  await start.click();
  await expect(page.getByRole('button', { name: 'Take picture' })).toBeEnabled();
  const bounds = await dialog.boundingBox();
  const viewport = page.viewportSize();
  expect(bounds.x).toBeGreaterThanOrEqual(0);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(viewport.width);
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(viewport.height);
  await page.screenshot({ path: testInfo.outputPath('qr-live-preview.png') });
  await page.getByRole('button', { name: 'Take picture' }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText('Visitor verified from captured picture.')).toBeVisible();
  expect(verifications).toEqual([{ credential: 'test-visitor-pass' }]);
  expect(await page.evaluate(() => window.__qrDecodes)).toBe(1);
  expect(await page.evaluate(() => window.__cameraStreams.every((stream) =>
    stream.getTracks().every((track) => track.readyState === 'ended')))).toBe(true);
});
