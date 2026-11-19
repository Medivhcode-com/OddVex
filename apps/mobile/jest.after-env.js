/* eslint-env jest */
// Unsaved form input is held in a module (src/session/drafts.ts). Nothing kept by one test reaches the next.
afterEach(() => require('./src/session/drafts').dropDrafts());
