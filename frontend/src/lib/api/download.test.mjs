import assert from 'node:assert/strict';

// `download()` is the one path in the client that does not parse JSON, and the
// two things worth pinning are the two a reader would get wrong: the filename
// comes from the server's own `Content-Disposition`, and a failure still raises
// an `ApiError` carrying the server's code — because the error body IS json even
// when the success body is not.

globalThis.document = {
  cookie: '',
  body: { appendChild() {} },
  createElement: () => ({
    click() {
      clicked = true;
    },
    remove() {},
  }),
};
globalThis.URL.createObjectURL = () => 'blob:fake';
globalThis.URL.revokeObjectURL = () => {};

let clicked = false;
let anchor;
document.createElement = () => {
  anchor = {
    click() {
      clicked = true;
    },
    remove() {},
  };
  return anchor;
};

globalThis.fetch = async (url) => {
  if (url.includes('incidents')) {
    return new Response('{"error":{"code":"unknown_dataset","message":"Not one of the four."}}', {
      status: 422,
      headers: { 'Content-Type': 'application/json' },
    });
  }
  return new Response('Recorded at,Direction\n2026-08-10,inward\n', {
    status: 200,
    headers: {
      'Content-Type': 'text/csv',
      'Content-Disposition': 'attachment; filename="material-movements.csv"',
    },
  });
};

const { download, filenameFrom, ApiError } = await import('./client.js');

await download('/security/exports/material-movements');
assert.equal(clicked, true, 'the anchor is clicked, which is what downloads the file');
assert.equal(anchor.download, 'material-movements.csv', 'the server names the file');

assert.equal(
  filenameFrom(
    new Response('', { headers: { 'Content-Disposition': "attachment; filename*=UTF-8''shifts.csv" } })
  ),
  'shifts.csv',
  'the RFC 5987 form is honoured too'
);

await assert.rejects(
  () => download('/security/exports/incidents'),
  (error) =>
    error instanceof ApiError && error.status === 422 && error.code === 'unknown_dataset',
  'a refusal keeps the server code so the button can render it'
);
