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

import { useEffect, useMemo, useState } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AppContext, useApp } from './AppContext.jsx';
import { getConfig, getSession } from './api.js';
import Layout from './components/Layout.jsx';
import Consent from './pages/Consent.jsx';
import Home from './pages/Home.jsx';
import Login from './pages/Login.jsx';
import Signup from './pages/Signup.jsx';

const platformStyles = import.meta.glob('./platform/*.css');

/** Signed-in users only; everybody else goes to the login page. */
function Private({ children }) {
  const { session } = useApp();
  const { search } = useLocation();
  if (!session) {
    return <Navigate to={`/login${search}`} replace />;
  }
  return children;
}

/** Visitors only; a signed-in user goes to the home page. */
function Public({ children }) {
  const { session } = useApp();
  const { search } = useLocation();
  if (!session) {
    return children;
  }
  // a login that is part of an oauth flow continues on the consent form
  const oauth = new URLSearchParams(search).get('response_type') === 'code';
  return <Navigate to={oauth ? `/consent${search}` : '/home'} replace />;
}

/** "/" is the home page for a signed-in user and the login page for everybody else. */
function Root({ home }) {
  const { session } = useApp();
  return session ? home : <Login />;
}

export default function App({ flash: initialFlash = null }) {
  const [config, setConfig] = useState(null);
  const [session, setSession] = useState(undefined);
  const [failed, setFailed] = useState(false);
  // the message of a failed form post, until the home page has shown it
  const [flash, setFlash] = useState(initialFlash);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getConfig(),
      getSession().catch((err) => {
        if (err.status === 401) {
          return null;
        }
        throw err;
      }),
    ]).then(
      ([loadedConfig, loadedSession]) => {
        if (!cancelled) {
          setConfig(loadedConfig);
          setSession(loadedSession);
        }
      },
      () => {
        if (!cancelled) {
          setFailed(true);
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!config) {
      return;
    }
    document.title = config.cymbal_logo ? 'CymbalBank' : config.bank_name;
    const load = platformStyles[`./platform/${config.platform}.css`];
    if (load) {
      load();
    }
  }, [config]);

  const value = useMemo(() => ({ config, session, setSession }), [config, session]);

  if (failed) {
    return (
      <main className="container">
        <div className="alert alert-danger mt-5" role="alert">
          The bank is not available right now. Please try again later.
        </div>
      </main>
    );
  }
  if (!config || session === undefined) {
    return null;
  }

  const home = <Home flash={flash} onFlashShown={() => setFlash(null)} />;

  return (
    <AppContext.Provider value={value}>
      <Layout>
        <Routes>
          <Route path="/" element={<Root home={home} />} />
          <Route path="/home" element={<Private>{home}</Private>} />
          <Route path="/login" element={<Public><Login /></Public>} />
          <Route path="/signup" element={<Public><Signup /></Public>} />
          <Route path="/consent" element={<Private><Consent /></Private>} />
          {/* a failed form post answers at /payment or /deposit with the app and a message */}
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
      </Layout>
    </AppContext.Provider>
  );
}
