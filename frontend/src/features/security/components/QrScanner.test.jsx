import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import QrScanner from './QrScanner';

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

let detect;
let getUserMedia;
let track;
let stream;
let drawImage;

beforeEach(() => {
  track = new EventTarget();
  track.stop = vi.fn();
  stream = { getTracks: () => [track] };
  getUserMedia = vi.fn().mockResolvedValue(stream);
  vi.stubGlobal('navigator', Object.assign(Object.create(navigator), {
    mediaDevices: { getUserMedia },
  }));
  detect = vi.fn().mockResolvedValue([{ rawValue: 'visitor-credential' }]);
  vi.stubGlobal('BarcodeDetector', class { detect = detect; });
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
    configurable: true,
    value: vi.fn(function () { this.setAttribute('open', ''); }),
  });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', {
    configurable: true,
    value: vi.fn(function () { this.removeAttribute('open'); }),
  });
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, 'readyState', 'get').mockReturnValue(4);
  vi.spyOn(HTMLVideoElement.prototype, 'videoWidth', 'get').mockReturnValue(640);
  vi.spyOn(HTMLVideoElement.prototype, 'videoHeight', 'get').mockReturnValue(480);
  drawImage = vi.fn();
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  delete HTMLDialogElement.prototype.showModal;
  delete HTMLDialogElement.prototype.close;
});

async function openCamera() {
  await userEvent.click(screen.getByRole('button', { name: 'Start QR camera scanner' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Take picture' })).toBeEnabled());
}

describe('QR capture', () => {
  it('shows a popup preview and only decodes a frozen frame after Take picture', async () => {
    const onScan = vi.fn();
    const { container } = render(<QrScanner onScan={onScan} />);
    await openCamera();
    const dialog = screen.getByRole('dialog', { name: 'Scan visitor QR' });
    expect(container).not.toContainElement(dialog);
    const video = screen.getByLabelText('Live camera preview');
    expect(video.srcObject).toBe(stream);
    expect(getUserMedia).toHaveBeenCalledWith({ video: { facingMode: { ideal: 'environment' } }, audio: false });
    vi.useFakeTimers();
    await act(() => vi.advanceTimersByTimeAsync(1500));
    expect(detect).not.toHaveBeenCalled();
    expect(onScan).not.toHaveBeenCalled();
    vi.useRealTimers();
    await userEvent.click(screen.getByRole('button', { name: 'Take picture' }));
    expect(drawImage).toHaveBeenCalledWith(video, 0, 0, 640, 480);
    expect(detect.mock.calls[0][0]).toBeInstanceOf(HTMLCanvasElement);
    expect(onScan).toHaveBeenCalledExactlyOnceWith('visitor-credential');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(track.stop).toHaveBeenCalledOnce();
  });

  it('keeps capture disabled until a frame is available', async () => {
    vi.spyOn(HTMLMediaElement.prototype, 'readyState', 'get').mockReturnValue(0);
    render(<QrScanner onScan={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'Start QR camera scanner' }));
    expect(screen.getByRole('button', { name: 'Take picture' })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Starting camera');
    vi.spyOn(HTMLMediaElement.prototype, 'readyState', 'get').mockReturnValue(4);
    fireEvent.loadedData(screen.getByLabelText('Live camera preview'));
    expect(screen.getByRole('button', { name: 'Take picture' })).toBeEnabled();
  });

  it.each(['empty', 'error'])('allows another picture after an %s decode', async (failure) => {
    if (failure === 'empty') detect.mockResolvedValueOnce([]);
    else detect.mockRejectedValueOnce(new Error('decode failed'));
    const onScan = vi.fn();
    render(<QrScanner onScan={onScan} />);
    await openCamera();
    await userEvent.click(screen.getByRole('button', { name: 'Take picture' }));
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(track.stop).not.toHaveBeenCalled();
    expect(onScan).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Take picture' }));
    expect(onScan).toHaveBeenCalledOnce();
  });

  it.each(['close button', 'escape', 'backdrop', 'unmount'])('releases the camera on %s', async (method) => {
    const onScan = vi.fn();
    const { unmount } = render(<QrScanner onScan={onScan} />);
    await openCamera();
    if (method === 'unmount') unmount();
    else if (method === 'close button') await userEvent.click(screen.getByRole('button', { name: 'Close scanner' }));
    else if (method === 'escape') fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }));
    else fireEvent.click(screen.getByRole('dialog'));
    expect(track.stop).toHaveBeenCalledOnce();
    expect(onScan).not.toHaveBeenCalled();
    expect(document.body.style.overflow).not.toBe('hidden');
  });

  it('stops a late permission grant without disturbing a newly opened camera', async () => {
    const permission = deferred();
    const oldTrack = { stop: vi.fn() };
    getUserMedia.mockReturnValueOnce(permission.promise);
    render(<QrScanner onScan={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'Start QR camera scanner' }));
    await userEvent.click(screen.getByRole('button', { name: 'Close scanner' }));
    await openCamera();
    await act(async () => permission.resolve({ getTracks: () => [oldTrack] }));
    expect(oldTrack.stop).toHaveBeenCalledOnce();
    expect(track.stop).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Live camera preview').srcObject).toBe(stream);
  });

  it('ignores an in-flight decode after closing and prevents repeated capture', async () => {
    const decoding = deferred();
    detect.mockReturnValueOnce(decoding.promise);
    const onScan = vi.fn();
    render(<QrScanner onScan={onScan} />);
    await openCamera();
    await userEvent.dblClick(screen.getByRole('button', { name: 'Take picture' }));
    expect(detect).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Reading picture…' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Close scanner' }));
    await act(async () => decoding.resolve([{ rawValue: 'stale' }]));
    expect(onScan).not.toHaveBeenCalled();
  });

  it('blocks camera and manual submissions during verification, then allows retry on failure', async () => {
    const verification = deferred();
    const onScan = vi.fn().mockReturnValueOnce(verification.promise);
    render(<QrScanner onScan={onScan} />);
    await userEvent.type(screen.getByPlaceholderText('Security code'), '123456');
    await userEvent.dblClick(screen.getByRole('button', { name: 'Verify' }));
    expect(onScan).toHaveBeenCalledExactlyOnceWith('123456');
    expect(screen.getByRole('button', { name: 'Start QR camera scanner' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Checking…' })).toBeDisabled();
    await act(async () => verification.reject(new Error('offline cache unavailable')));
    expect(screen.getByText('The pass could not be verified. Please try again.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Verify' }));
    expect(onScan).toHaveBeenCalledTimes(2);
  });

  it('explains denied camera access and keeps manual entry available after closing', async () => {
    getUserMedia.mockRejectedValue(new DOMException('Denied', 'NotAllowedError'));
    render(<QrScanner onScan={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'Start QR camera scanner' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Camera access was denied');
    expect(screen.getByRole('button', { name: 'Take picture' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Close scanner' }));
    expect(screen.getByPlaceholderText('Security code')).toBeEnabled();
  });

  it('offers manual entry if the decoder is unavailable', async () => {
    vi.stubGlobal('BarcodeDetector', undefined);
    render(<QrScanner onScan={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'Start QR camera scanner' }));
    expect(screen.getByText(/This browser cannot scan QR codes/)).toBeInTheDocument();
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText('Security code')).toBeEnabled();
  });
});
