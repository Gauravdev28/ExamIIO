import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Menu, X, ArrowRight, LogOut, LayoutDashboard } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { getDashboardPath } from '../common/ProtectedRoute';
import { ExamIIOLogo } from '../common/ExamIIOLogo';
import { EXAMIO_CONTACT_MAILTO } from '../../constants/contact';

export const PublicNavbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { label: 'Platform', href: '#platform' },
    { label: 'Solutions', href: '#solutions' },
    { label: 'How It Works', href: '#how-it-works' },
    { label: 'Technology', href: '#technology' },
    { label: 'Security', href: '#security' },
    { label: 'About', href: '#about' },
    { label: 'Contact', href: EXAMIO_CONTACT_MAILTO, isMailto: true },
  ];

  const handleNavClick = (
    e: React.MouseEvent<HTMLAnchorElement>,
    link: { label: string; href: string; isMailto?: boolean }
  ) => {
    if (link.isMailto) {
      return;
    }
    e.preventDefault();
    setMobileMenuOpen(false);

    if (location.pathname !== '/') {
      navigate('/' + link.href);
      return;
    }

    const targetElement = document.querySelector(link.href);
    if (targetElement) {
      targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleAnchorClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    e.preventDefault();
    if (location.pathname === '/') {
      const target = document.querySelector(href);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth' });
      }
    } else {
      navigate(`/${href}`);
    }
    setMobileMenuOpen(false);
  };

  const handleLogoClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (location.pathname === '/') {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const dashboardPath = getDashboardPath(user?.role);

  return (
    <nav className="sticky top-0 z-40 backdrop-blur-md bg-[#F4F1EA]/95 border-b border-[#DDD8CE] transition-all">
      <div className="w-full px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <Link
            to="/"
            onClick={handleLogoClick}
            className="flex items-center group py-1"
            aria-label="ExamIIO Home"
          >
            <ExamIIOLogo variant="full" size="md" />
          </Link>

          {/* Desktop Navigation Links */}
          <div className="hidden lg:flex items-center gap-1">
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={link.isMailto ? undefined : (e) => handleNavClick(e, link)}
                className="px-2.5 py-1.5 rounded-lg text-xs lg:text-sm font-medium text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1]/80 transition-colors"
              >
                {link.label}
              </a>
            ))}
          </div>

          {/* Desktop Action Buttons */}
          <div className="hidden md:flex items-center gap-2.5">
            {isAuthenticated && user ? (
              <div className="flex items-center gap-2">
                <div className="text-right mr-1">
                  <div className="text-xs font-semibold text-[#243247] truncate max-w-[140px]">
                    {user.email}
                  </div>
                  <Badge variant={user.role === 'ADMIN' ? 'info' : user.role === 'PROCTOR' ? 'warning' : 'success'} size="sm">
                    {user.role}
                  </Badge>
                </div>
                <Link to={dashboardPath}>
                  <Button variant="primary" size="sm" className="bg-[#2878D8] hover:bg-[#2065B8] active:bg-[#18539C] text-white flex items-center gap-1.5 shadow-xs">
                    <LayoutDashboard className="w-3.5 h-3.5" />
                    <span>Dashboard</span>
                  </Button>
                </Link>
                <Button variant="ghost" size="sm" onClick={logout} title="Sign Out">
                  <LogOut className="w-4 h-4 text-[#5E6B7D] hover:text-[#243247]" />
                </Button>
              </div>
            ) : (
              <>
                <Link to="/login">
                  <button
                    type="button"
                    className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-[#243247] bg-[#FAF9F6] hover:bg-[#EDE9E1] border border-[#DDD8CE] transition-colors"
                  >
                    Sign In
                  </button>
                </Link>
                <a
                  href="#solutions"
                  onClick={(e) => handleAnchorClick(e, '#solutions')}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#2878D8] hover:bg-[#2065B8] active:bg-[#18539C] text-white text-xs font-semibold shadow-xs transition-all"
                >
                  <span>Explore Platform</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </a>
              </>
            )}
          </div>

          {/* Mobile menu toggle */}
          <div className="flex lg:hidden items-center gap-2">
            {!isAuthenticated && (
              <Link to="/login">
                <button
                  type="button"
                  className="px-2.5 py-1 rounded-md bg-[#FAF9F6] text-[#243247] text-xs font-semibold border border-[#DDD8CE]"
                >
                  Sign In
                </button>
              </Link>
            )}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1] transition-colors"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-b border-[#DDD8CE] bg-[#F4F1EA] px-4 pt-2 pb-5 space-y-2 shadow-sm animate-fadeIn">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              onClick={
                link.isMailto
                  ? () => {
                      setTimeout(() => setMobileMenuOpen(false), 100);
                    }
                  : (e) => handleNavClick(e, link)
              }
              className="block px-3 py-2 rounded-lg text-sm font-medium text-[#5E6B7D] hover:text-[#243247] hover:bg-[#EDE9E1] transition-colors"
            >
              {link.label}
            </a>
          ))}

          <div className="pt-3 border-t border-[#DDD8CE] flex flex-col gap-2">
            {isAuthenticated && user ? (
              <>
                <div className="flex items-center justify-between px-3 py-1 text-xs">
                  <span className="text-[#5E6B7D] truncate">{user.email}</span>
                  <Badge variant={user.role === 'ADMIN' ? 'info' : user.role === 'PROCTOR' ? 'warning' : 'success'} size="sm">
                    {user.role}
                  </Badge>
                </div>
                <Link to={dashboardPath} onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="primary" size="md" className="w-full bg-[#2878D8] hover:bg-[#2065B8] text-white flex items-center justify-center gap-1.5">
                    <LayoutDashboard className="w-4 h-4" />
                    <span>Go to Dashboard</span>
                  </Button>
                </Link>
                <Button variant="outline" size="sm" onClick={() => { logout(); setMobileMenuOpen(false); }} className="w-full border-[#DDD8CE] text-[#243247] bg-[#FAF9F6] hover:bg-[#EDE9E1]">
                  Sign Out
                </Button>
              </>
            ) : (
              <>
                <a
                  href="#solutions"
                  onClick={(e) => handleAnchorClick(e, '#solutions')}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[#2878D8] hover:bg-[#2065B8] text-white text-xs font-semibold transition-colors shadow-xs"
                >
                  <span>Explore Platform</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </a>
                <Link to="/login" onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="secondary" size="md" className="w-full flex items-center justify-center gap-1.5 text-xs font-semibold bg-[#FAF9F6] hover:bg-[#EDE9E1] text-[#243247] border-[#DDD8CE]">
                    <span>Sign In to Platform</span>
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};

export default PublicNavbar;
