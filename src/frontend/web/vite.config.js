// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// The Flask service serves the build from static/dist, so the assets are
// requested under /static/dist/.
export default defineConfig({
  plugins: [react()],
  base: '/static/dist/',
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  },
  server: {
    // `npm run dev` with the Flask service running on :8080
    proxy: {
      '/api': 'http://localhost:8080',
      '/payment': 'http://localhost:8080',
      '/deposit': 'http://localhost:8080',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    globals: true,
  },
});
