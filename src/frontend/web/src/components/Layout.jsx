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

import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useApp } from '../AppContext.jsx';
import { logout } from '../api.js';
import cymbalLogo from '../assets/cymbal.svg';

function PlatformBanner() {
  const { config } = useApp();
  if (!config.platform) {
    return null;
  }
  return (
    <div className="platform-banner">
      <span className="platform-flag">{config.platform_display_name}</span>
    </div>
  );
}

function Navbar() {
  const { config, session, setSession } = useApp();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  async function signOut(event) {
    event.preventDefault();
    try {
      await logout();
    } catch {
      // the cookie may be gone already; leave the session either way
    }
    setDropdownOpen(false);
    setSession(null);
    navigate('/login');
  }

  return (
    <header>
      <nav className="navbar navbar-expand-lg navbar-top">
        <div className="container">
          {config.cymbal_logo ? (
            <div className="logo-container">
              <Link to="/"><img id="cymbal-logo" src={cymbalLogo} alt="CymbalBank" /></Link>
            </div>
          ) : (
            <a className="navbar-brand">{config.bank_name}</a>
          )}
          {session && (
            <>
              <button
                type="button"
                aria-controls="navbarNav"
                aria-expanded={menuOpen}
                aria-label="Toggle navigation"
                className="navbar-toggler navbar-toggler-right"
                onClick={() => setMenuOpen(!menuOpen)}
              >
                <span className="material-icons">menu</span>
              </button>
              <div
                className={`justify-content-end collapse navbar-collapse${menuOpen ? ' show' : ''}`}
                id="navbarNav"
              >
                <ul className="navbar-nav">
                  <li className={`nav-item dropdown${dropdownOpen ? ' show' : ''}`}>
                    <a
                      className="nav-link dropdown-toggle"
                      href="#"
                      id="accountDropdown"
                      role="button"
                      aria-haspopup="true"
                      aria-expanded={dropdownOpen}
                      onClick={(event) => {
                        event.preventDefault();
                        setDropdownOpen(!dropdownOpen);
                      }}
                    >
                      <span>
                        <span id="account-user-name">{session.name}</span>
                      </span>
                    </a>
                    <div
                      className={`dropdown-menu${dropdownOpen ? ' show' : ''}`}
                      aria-labelledby="accountDropdown"
                    >
                      <form id="logout-form" method="POST" action="/logout" onSubmit={signOut}>
                        <button type="submit" className="dropdown-item">
                          Sign out<i className="fa-icon-spacer fas fa-sign-out-alt"></i>
                        </button>
                      </form>
                    </div>
                  </li>
                </ul>
              </div>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}

function Footer() {
  const { config } = useApp();
  return (
    <footer className="footer">
      <div className="container">
        <div className="row mb-2">&copy; 2020-2024 Google LLC</div>
        <div className="row mb-3">
          <small>
            <b>Cluster: </b>{config.cluster_name}, <b>Pod: </b>{config.pod_name}<b>, Zone: </b>{config.pod_zone}
          </small>
        </div>
        <div className="row mb-3">
          <small>
            This website is hosted for demo purposes only. It is not an
            actual bank. This is not an official Google project.
          </small>
        </div>
      </div>
    </footer>
  );
}

/** What every page has around it: the platform banner, the navigation bar and the footer. */
export default function Layout({ children }) {
  return (
    <>
      <PlatformBanner />
      <Navbar />
      {children}
      <Footer />
    </>
  );
}
