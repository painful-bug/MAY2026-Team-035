// Amenity photos travel as base64 data URLs inside `amenities.image_url`
// (issue #48, ruling 3 — no storage bucket), so the browser has to make the
// picture small enough to be a database column before it is ever sent.
//
// The backend's `AmenityWrite.image` accepts a data URL of at most
// `MAX_IMAGE_DATA_URL_LENGTH` characters and 422s anything larger. Base64
// inflates by 4/3, so the real budget is ~100KB of pixels. This module spends
// it: it shrinks the longest edge, then walks the JPEG/WebP quality down until
// the encoded result fits, and throws a sentence the form can show when even
// the smallest setting cannot make it.
//
// The pure halves — the size arithmetic, the mime gating, the ladders — are
// separated from the canvas so they can be unit tested; jsdom has no canvas
// encoder, so `downscaleImageFile` refuses with a clear error there rather
// than silently returning an empty picture.

/** The backend's cap on the whole `data:` URL, in characters. */
export const MAX_IMAGE_DATA_URL_LENGTH = 140_000;

/** The pixel budget the cap works out to, in bytes. */
export const MAX_IMAGE_BYTES = 100 * 1024;

/** Longest edge, in CSS pixels, of the picture we keep. */
export const MAX_IMAGE_EDGE = 1280;

/** What a browser file input may hand us. */
export const ACCEPTED_IMAGE_TYPES = Object.freeze([
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/webp',
  'image/gif',
]);

/** What we are willing to encode to. Anything else loses the size argument. */
export const OUTPUT_IMAGE_TYPES = Object.freeze(['image/webp', 'image/jpeg']);

const EDGE_LADDER = Object.freeze([MAX_IMAGE_EDGE, 1024, 800, 640, 480]);
const QUALITY_LADDER = Object.freeze([0.82, 0.7, 0.6, 0.5, 0.4, 0.3]);

export const isSupportedImageType = (type) =>
  ACCEPTED_IMAGE_TYPES.includes(String(type ?? '').toLowerCase());

/**
 * The output encoding for an input type. WebP is smaller at the same quality
 * and is the default; a browser whose canvas cannot encode it falls back to
 * JPEG. Transparency is lost either way — a JPEG has none and the amenity card
 * renders the picture on an opaque tile — so PNG is deliberately not an output.
 */
export const pickOutputImageType = (inputType, { supportsWebp = true } = {}) =>
  supportsWebp && isSupportedImageType(inputType) ? 'image/webp' : 'image/jpeg';

/** Decoded byte length of a `data:...;base64,...` URL, without decoding it. */
export const dataUrlByteLength = (dataUrl) => {
  const value = String(dataUrl ?? '');
  const commaIndex = value.indexOf(',');

  if (commaIndex === -1) {
    return 0;
  }

  const payload = value.slice(commaIndex + 1);
  const padding = payload.endsWith('==') ? 2 : payload.endsWith('=') ? 1 : 0;
  return Math.max(Math.floor((payload.length * 3) / 4) - padding, 0);
};

export const isWithinImageBudget = (dataUrl) =>
  String(dataUrl ?? '').length <= MAX_IMAGE_DATA_URL_LENGTH &&
  dataUrlByteLength(dataUrl) <= MAX_IMAGE_BYTES;

/**
 * The drawing size for a picture whose longest edge must not exceed `maxEdge`.
 * Never enlarges — a 200px thumbnail stays 200px rather than being blown up to
 * 1280 and re-encoded into something bigger than it started.
 */
export const scaledDimensions = (width, height, maxEdge = MAX_IMAGE_EDGE) => {
  const sourceWidth = Number(width);
  const sourceHeight = Number(height);

  if (
    !Number.isFinite(sourceWidth) ||
    !Number.isFinite(sourceHeight) ||
    sourceWidth <= 0 ||
    sourceHeight <= 0
  ) {
    throw new Error('The image could not be read.');
  }

  const longestEdge = Math.max(sourceWidth, sourceHeight);
  const scale = longestEdge > maxEdge ? maxEdge / longestEdge : 1;

  return {
    width: Math.max(Math.round(sourceWidth * scale), 1),
    height: Math.max(Math.round(sourceHeight * scale), 1),
  };
};

const TOO_BIG_MESSAGE =
  'This image is too detailed to store. Please choose a simpler or smaller picture.';

const NO_CANVAS_MESSAGE =
  'This browser cannot resize images, so the picture cannot be uploaded.';

const canvasSupportsWebp = (canvas) => {
  try {
    return canvas.toDataURL('image/webp').startsWith('data:image/webp');
  } catch {
    return false;
  }
};

const readFileAsDataURL = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener('load', () => resolve(String(reader.result)));
    reader.addEventListener('error', () =>
      reject(new Error('The image could not be read.'))
    );
    reader.readAsDataURL(file);
  });

const loadImage = (source) =>
  new Promise((resolve, reject) => {
    const image = new Image();
    image.addEventListener('load', () => resolve(image));
    image.addEventListener('error', () =>
      reject(new Error('The image could not be read.'))
    );
    image.src = source;
  });

/**
 * A picture the amenity write endpoint will accept, as a data URL.
 *
 * Throws — with a message meant for the admin, not for a log — when the file is
 * not an image we handle, when the browser has no canvas encoder, or when no
 * point on the size/quality ladder fits inside the column.
 */
export const downscaleImageFile = async (file, options = {}) => {
  if (!file) {
    throw new Error('Choose an image file.');
  }

  if (!isSupportedImageType(file.type)) {
    throw new Error('Choose a JPEG, PNG, WebP or GIF image.');
  }

  const maxEdge = options.maxEdge ?? MAX_IMAGE_EDGE;
  const createCanvas =
    options.createCanvas ??
    (() =>
      typeof document === 'undefined'
        ? null
        : document.createElement('canvas'));

  const canvas = createCanvas();
  const context = canvas?.getContext?.('2d');

  if (!canvas || !context || typeof canvas.toDataURL !== 'function') {
    throw new Error(NO_CANVAS_MESSAGE);
  }

  const source = await loadImage(await readFileAsDataURL(file));
  const outputType = pickOutputImageType(file.type, {
    supportsWebp: canvasSupportsWebp(canvas),
  });
  const edges = EDGE_LADDER.filter((edge) => edge <= maxEdge);

  for (const edge of edges.length > 0 ? edges : [maxEdge]) {
    const { width, height } = scaledDimensions(
      source.naturalWidth || source.width,
      source.naturalHeight || source.height,
      edge
    );
    canvas.width = width;
    canvas.height = height;
    context.clearRect(0, 0, width, height);
    // JPEG has no alpha; without a painted ground a transparent PNG encodes as
    // a black rectangle.
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, width, height);
    context.drawImage(source, 0, 0, width, height);

    for (const quality of QUALITY_LADDER) {
      const dataUrl = canvas.toDataURL(outputType, quality);

      if (!String(dataUrl).startsWith('data:image/')) {
        throw new Error(NO_CANVAS_MESSAGE);
      }

      if (isWithinImageBudget(dataUrl)) {
        return dataUrl;
      }
    }
  }

  throw new Error(TOO_BIG_MESSAGE);
};
