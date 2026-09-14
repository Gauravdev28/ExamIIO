import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Mail } from 'lucide-react';
import { ExamIIOLogo } from '../common/ExamIIOLogo';
import { EXAMIO_CONTACT_MAILTO } from '../../constants/contact';

export const PublicFooter: React.FC = () => {
  const handleAnchorClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    if (window.location.pathname === '/') {
      e.preventDefault();
      const target = document.querySelector(href);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  return (
    <footer className="border-t border-[#DDD8CE] bg-[#E8E4DC] text-[#5E6B7D] text-xs w-full">
      <div className="w-full px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-10 lg:gap-12 mb-12">
          {/* Brand Column (2 cols wide on desktop) */}
          <div className="space-y-4 md:col-span-2">
            <Link
              to="/"
              onClick={(e) => {
                if (window.location.pathname === '/') {
                  e.preventDefault();
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }
              }}
              className="inline-block"
            >
              <ExamIIOLogo variant="full" size="md" />
            </Link>
            <p className="text-[#5E6B7D] max-w-sm leading-relaxed text-xs">
              ExamIIO provides technical assessment infrastructure engineered for trust. Enabling universities, certification authorities, and engineering teams to author, deliver, evaluate, and verify programming examinations in one controlled environment.
            </p>
            <div className="pt-2 flex items-center gap-2 text-[11px] text-[#5E6B7D] font-mono">
              <span className="inline-block w-2 h-2 rounded-full bg-[#2FA878]"></span>
              <span>Architecture Active &bull; Deterministic Evaluation</span>
            </div>
          </div>

          {/* Navigation Column 1: Platform */}
          <div className="space-y-3">
            <h4 className="text-[11px] font-bold uppercase tracking-wider text-[#243247] font-mono">
              Platform
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <a
                  href="#platform"
                  onClick={(e) => handleAnchorClick(e, '#platform')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Assessment Authoring
                </a>
              </li>
              <li>
                <a
                  href="#platform"
                  onClick={(e) => handleAnchorClick(e, '#platform')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Candidate Management
                </a>
              </li>
              <li>
                <a
                  href="#platform"
                  onClick={(e) => handleAnchorClick(e, '#platform')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Coding Evaluation
                </a>
              </li>
              <li>
                <a
                  href="#platform"
                  onClick={(e) => handleAnchorClick(e, '#platform')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Examination Supervision
                </a>
              </li>
              <li>
                <a
                  href="#platform"
                  onClick={(e) => handleAnchorClick(e, '#platform')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Results & Analytics
                </a>
              </li>
              <li>
                <a
                  href="#platform"
                  onClick={(e) => handleAnchorClick(e, '#platform')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Certificate Verification
                </a>
              </li>
            </ul>
          </div>

          {/* Navigation Column 2: Architecture & Trust */}
          <div className="space-y-3">
            <h4 className="text-[11px] font-bold uppercase tracking-wider text-[#243247] font-mono">
              Architecture
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <a
                  href="#technology"
                  onClick={(e) => handleAnchorClick(e, '#technology')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Deterministic Pipeline
                </a>
              </li>
              <li>
                <a
                  href="#technology"
                  onClick={(e) => handleAnchorClick(e, '#technology')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Isolated Execution
                </a>
              </li>
              <li>
                <a
                  href="#security"
                  onClick={(e) => handleAnchorClick(e, '#security')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Integrity Controls
                </a>
              </li>
              <li>
                <a
                  href="#security"
                  onClick={(e) => handleAnchorClick(e, '#security')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Audit Trails
                </a>
              </li>
              <li>
                <Link to="/health" className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors">
                  System Diagnostics
                </Link>
              </li>
            </ul>
          </div>

          {/* Navigation Column 3: Coordination */}
          <div className="space-y-3">
            <h4 className="text-[11px] font-bold uppercase tracking-wider text-[#243247] font-mono">
              Coordination
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <a
                  href="#about"
                  onClick={(e) => handleAnchorClick(e, '#about')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  About ExamIIO
                </a>
              </li>
              <li>
                <a
                  href="#about"
                  onClick={(e) => handleAnchorClick(e, '#about')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Engineering Leadership
                </a>
              </li>
              <li>
                <a
                  href="#about"
                  onClick={(e) => handleAnchorClick(e, '#about')}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors"
                >
                  Technology &amp; IP
                </a>
              </li>
              <li>
                <Link to="/login" className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors">
                  Workspace Sign In
                </Link>
              </li>
              <li>
                <a
                  href={EXAMIO_CONTACT_MAILTO}
                  className="text-[#5E6B7D] hover:text-[#2878D8] transition-colors flex items-center gap-1"
                >
                  <Mail className="w-3.5 h-3.5 text-[#2878D8]" />
                  <span>Direct Contact</span>
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-[#DDD8CE] flex flex-col sm:flex-row items-center justify-between gap-4 text-[#5E6B7D] text-[11px]">
          <div>
            &copy; 2026 ExamIIO. All rights reserved.
          </div>
          <div className="flex items-center gap-6">
            <span className="flex items-center gap-1.5 text-[#5E6B7D]">
              <ShieldCheck className="w-3.5 h-3.5 text-[#2878D8]" />
              <span>Institutional Light Theme Architecture</span>
            </span>
            <span className="text-[#DDD8CE]">|</span>
            <span className="text-[#5E6B7D]">
              Lead Engineering:{' '}
              <a
                href={EXAMIO_CONTACT_MAILTO}
                className="hover:text-[#2878D8] transition-colors underline decoration-[#DDD8CE] underline-offset-2"
              >
                Gaurav Agarwal
              </a>
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default PublicFooter;
