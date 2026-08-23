import { describe, expect, it } from 'vitest';
import {
  ACCEPTED_IMAGE_TYPES,
  MAX_IMAGE_BYTES,
  MAX_IMAGE_DATA_URL_LENGTH,
  dataUrlByteLength,
  downscaleImageFile,
  isSupportedImageType,
  isWithinImageBudget,
  pickOutputImageType,
  scaledDimensions,
} from './downscaleImage.js';

// The canvas half of this module cannot run here — jsdom ships no 2D context
// and no image encoder — so what is pinned is the arithmetic that decides
// whether a picture fits the `amenities.image_url` column, plus the guard that
// makes the canvas-less case an explained refusal rather than a blank image.

describe('image budget arithmetic', () => {
  it('agrees with the backend cap: 140000 data-URL chars, ~100KB of pixels', () => {
    expect(MAX_IMAGE_DATA_URL_LENGTH).toBe(140_000);
    expect(MAX_IMAGE_BYTES).toBe(102_400);
    // Base64 inflates by 4/3, so the byte budget must be spendable inside the
    // character budget rather than larger than it.
    expect(Math.ceil((MAX_IMAGE_BYTES * 4) / 3)).toBeLessThan(
      MAX_IMAGE_DATA_URL_LENGTH
    );
  });

  it('measures the decoded size of a data URL, padding included', () => {
    // "AAAA" is 3 bytes; each '=' is one byte of padding removed.
    expect(dataUrlByteLength('data:image/jpeg;base64,AAAA')).toBe(3);
    expect(dataUrlByteLength('data:image/jpeg;base64,AAA=')).toBe(2);
    expect(dataUrlByteLength('data:image/jpeg;base64,AA==')).toBe(1);
    expect(dataUrlByteLength('')).toBe(0);
    expect(dataUrlByteLength(null)).toBe(0);
  });

  it('accepts a picture inside both caps and rejects one over either', () => {
    const fits = `data:image/jpeg;base64,${'A'.repeat(1000)}`;
    const overLength = `data:image/jpeg;base64,${'A'.repeat(
      MAX_IMAGE_DATA_URL_LENGTH
    )}`;

    expect(isWithinImageBudget(fits)).toBe(true);
    expect(overLength.length).toBeGreaterThan(MAX_IMAGE_DATA_URL_LENGTH);
    expect(isWithinImageBudget(overLength)).toBe(false);
  });
});

describe('mime gating', () => {
  it('accepts exactly the browser image types the form advertises', () => {
    ACCEPTED_IMAGE_TYPES.forEach((type) => {
      expect(isSupportedImageType(type)).toBe(true);
    });
    expect(isSupportedImageType('IMAGE/PNG')).toBe(true);
    expect(isSupportedImageType('image/svg+xml')).toBe(false);
    expect(isSupportedImageType('application/pdf')).toBe(false);
    expect(isSupportedImageType(undefined)).toBe(false);
  });

  it('encodes to WebP where the canvas can, and JPEG where it cannot', () => {
    expect(pickOutputImageType('image/png', { supportsWebp: true })).toBe(
      'image/webp'
    );
    expect(pickOutputImageType('image/png', { supportsWebp: false })).toBe(
      'image/jpeg'
    );
    expect(pickOutputImageType('image/webp', { supportsWebp: true })).toBe(
      'image/webp'
    );
  });
});

describe('scaledDimensions', () => {
  it('caps the longest edge and keeps the aspect ratio', () => {
    expect(scaledDimensions(4000, 3000, 1280)).toEqual({
      width: 1280,
      height: 960,
    });
    expect(scaledDimensions(3000, 4000, 1280)).toEqual({
      width: 960,
      height: 1280,
    });
  });

  it('never enlarges a picture that already fits', () => {
    expect(scaledDimensions(200, 120, 1280)).toEqual({
      width: 200,
      height: 120,
    });
  });

  it('refuses a picture with no dimensions instead of returning 0x0', () => {
    expect(() => scaledDimensions(0, 0, 1280)).toThrow(
      'The image could not be read.'
    );
    expect(() => scaledDimensions(Number.NaN, 100, 1280)).toThrow(
      'The image could not be read.'
    );
  });
});

describe('downscaleImageFile guards', () => {
  it('rejects a non-image file with a message the form can show', async () => {
    await expect(
      downscaleImageFile({ type: 'application/pdf', name: 'plan.pdf' })
    ).rejects.toThrow('Choose a JPEG, PNG, WebP or GIF image.');
  });

  it('rejects when no file was chosen', async () => {
    await expect(downscaleImageFile(null)).rejects.toThrow(
      'Choose an image file.'
    );
  });

  it('explains a canvas-less browser rather than uploading nothing', async () => {
    await expect(
      downscaleImageFile(
        { type: 'image/png', name: 'pool.png' },
        { createCanvas: () => null }
      )
    ).rejects.toThrow(
      'This browser cannot resize images, so the picture cannot be uploaded.'
    );
  });
});
