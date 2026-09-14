import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Code2,
  Terminal,
  ShieldCheck,
  CheckCircle2,
  ArrowRight,
  Lock,
  Layers,
  Building2,
  GraduationCap,
  Award,
  Eye,
  FileCheck2,
  UserCheck,
  FileText,
  Mail,
  Copy,
  Check,
  Loader2
} from 'lucide-react';
import { Button } from '../../components/common/Button';
import { CONTACT_EMAIL, EXAMIO_CONTACT_MAILTO } from '../../constants/contact';

export const HomePage: React.FC = () => {
  const [activeShowcaseTab, setActiveShowcaseTab] = useState<
    'command-center' | 'candidate-env' | 'proctor-console' | 'verification'
  >('candidate-env');

  // Interactive state for hero preview run button
  const [testRunStatus, setTestRunStatus] = useState<'idle' | 'running' | 'completed'>('idle');
  const [emailCopied, setEmailCopied] = useState(false);

  // Smooth scroll handler on hash change or deep link mount
  useEffect(() => {
    if (window.location.hash) {
      const id = window.location.hash;
      const element = document.querySelector(id);
      if (element) {
        setTimeout(() => {
          element.scrollIntoView({ behavior: 'smooth' });
        }, 150);
      }
    }
  }, []);

  const handleRunHeroTests = () => {
    if (testRunStatus === 'running') return;
    setTestRunStatus('running');
    setTimeout(() => {
      setTestRunStatus('completed');
    }, 800);
  };

  const handleCopyEmail = () => {
    navigator.clipboard.writeText(CONTACT_EMAIL);
    setEmailCopied(true);
    setTimeout(() => setEmailCopied(false), 2500);
  };

  return (
    <div className="space-y-24 lg:space-y-32 pb-24 text-[#243247] selection:bg-[#2878D8]/20 selection:text-[#243247]">
      {/* =========================================================================
          1. PLATFORM / HERO SECTION & CONTROLLED PRODUCT PREVIEW
          ========================================================================= */}
      <section
        id="platform"
        className="relative pt-12 md:pt-20 lg:pt-24 border-b border-[#DDD8CE] bg-[#F4F1EA] scroll-mt-24"
        style={{
          backgroundImage: 'radial-gradient(#D9DDE3 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      >
        <div className="w-full px-4 sm:px-6 lg:px-8">
          <div className="max-w-4xl mx-auto text-center space-y-6">
            {/* Eyebrow badge */}
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#FAF9F6] text-[#243247] border border-[#DDD8CE] text-xs font-mono font-medium shadow-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2878D8]"></span>
              <span>EXAMIIO ASSESSMENT PLATFORM</span>
            </div>

            {/* Main Headline */}
            <h1 className="text-3xl sm:text-5xl lg:text-6xl font-black text-[#243247] tracking-tight font-sans leading-[1.12]">
              Technical assessments, <br className="hidden sm:inline" />
              <span className="text-[#2878D8]">engineered for trust.</span>
            </h1>

            {/* Supporting Copy */}
            <p className="text-base sm:text-lg text-[#5E6B7D] max-w-2xl mx-auto leading-relaxed">
              ExamIIO is a technical assessment platform designed to help institutions and organizations create, conduct, evaluate, and verify programming and technical examinations through one controlled environment.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <a
                href="#solutions"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[#2878D8] hover:bg-[#2065B8] active:bg-[#18539C] text-white text-sm font-semibold transition-all shadow-xs"
              >
                <span>Explore Platform</span>
                <ArrowRight className="w-4 h-4" />
              </a>
              <a
                href={EXAMIO_CONTACT_MAILTO}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[#FAF9F6] hover:bg-[#EDE9E1] active:bg-[#DDD8CE] text-[#243247] border border-[#DDD8CE] text-sm font-semibold transition-colors shadow-xs"
              >
                <Mail className="w-4 h-4 text-[#2878D8]" />
                <span>Contact Us</span>
              </a>
            </div>

            {/* Value Highlights Strip */}
            <div className="pt-6 grid grid-cols-2 md:grid-cols-4 gap-3 text-left max-w-3xl mx-auto">
              <div className="p-3.5 bg-[#FAF9F6] rounded-xl border border-[#DDD8CE] shadow-xs">
                <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">Deterministic</div>
                <div className="text-xs font-semibold text-[#243247] mt-1">Automated Evaluation</div>
              </div>
              <div className="p-3.5 bg-[#FAF9F6] rounded-xl border border-[#DDD8CE] shadow-xs">
                <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">Controlled</div>
                <div className="text-xs font-semibold text-[#243247] mt-1">Session Boundaries</div>
              </div>
              <div className="p-3.5 bg-[#FAF9F6] rounded-xl border border-[#DDD8CE] shadow-xs">
                <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">Observable</div>
                <div className="text-xs font-semibold text-[#243247] mt-1">Real-Time Supervision</div>
              </div>
              <div className="p-3.5 bg-[#FAF9F6] rounded-xl border border-[#DDD8CE] shadow-xs">
                <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">Verifiable</div>
                <div className="text-xs font-semibold text-[#243247] mt-1">Public Credential IDs</div>
              </div>
            </div>
          </div>

          {/* Controlled Hero Product Visualization */}
          <div className="mt-12 lg:mt-16 max-w-5xl mx-auto">
            <div className="rounded-2xl border border-[#DDD8CE] bg-[#FAF9F6] shadow-md overflow-hidden">
              {/* Window Titlebar */}
              <div className="flex items-center justify-between px-4 py-2.5 bg-[#EDE9E1] border-b border-[#DDD8CE] text-xs font-mono text-[#5E6B7D]">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#D9DDE3]"></div>
                  <div className="w-2.5 h-2.5 rounded-full bg-[#D9DDE3]"></div>
                  <div className="w-2.5 h-2.5 rounded-full bg-[#D9DDE3]"></div>
                  <span className="ml-2 text-[#243247] font-semibold">ExamIIO Controlled Assessment Workspace</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1.5 text-[#2FA878]">
                    <span className="w-2 h-2 rounded-full bg-[#2FA878] animate-pulse"></span>
                    Supervision Active
                  </span>
                  <span className="text-[#DDD8CE]">|</span>
                  <span className="text-[#5E6B7D]">Timer: 48:12</span>
                </div>
              </div>

              {/* Assessment Preview Body */}
              <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-[#DDD8CE]">
                {/* Left: Problem & Test Specs (5 cols) */}
                <div className="lg:col-span-5 p-5 space-y-4 bg-[#FAF9F6] text-xs text-[#243247]">
                  <div className="flex items-center justify-between text-[11px] font-mono border-b border-[#DDD8CE] pb-2">
                    <span className="text-[#2878D8] font-bold">QUESTION 02 OF 04</span>
                    <span className="px-2 py-0.5 rounded bg-[#EDE9E1] text-[#243247] font-semibold border border-[#DDD8CE]">15 Points</span>
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[#243247] tracking-tight">Two-Sum Optimization</h3>
                    <p className="text-[#5E6B7D] text-xs mt-1.5 leading-relaxed">
                      Given an integer array and a target sum, return indices of the two numbers such that they add up to target. Execution limit: 2.0s.
                    </p>
                  </div>

                  <div className="space-y-2 pt-2">
                    <span className="text-[11px] font-mono text-[#5E6B7D] uppercase tracking-wider">Evaluation Test Suite:</span>
                    <div className="p-2.5 rounded-lg bg-[#EDE9E1] border border-[#DDD8CE] font-mono text-[11px] space-y-1.5">
                      <div className="flex items-center justify-between text-[#2FA878]">
                        <span>&bull; Public Case 1: [2, 7, 11, 15], target=9</span>
                        <span className="font-bold">PASSED</span>
                      </div>
                      <div className="flex items-center justify-between text-[#2FA878]">
                        <span>&bull; Public Case 2: [3, 2, 4], target=6</span>
                        <span className="font-bold">PASSED</span>
                      </div>
                      <div className="flex items-center justify-between text-[#2878D8]">
                        <span>&bull; Hidden Suite: 8 Verification Tests</span>
                        <span className="font-bold">
                          {testRunStatus === 'running'
                            ? 'RUNNING...'
                            : testRunStatus === 'completed'
                            ? 'ALL 8 PASSED'
                            : 'DETERMINISTIC'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right: Code Environment (7 cols - light institutional IDE preview) */}
                <div className="lg:col-span-7 p-5 bg-[#F1F4F7] text-[#334155] space-y-3 font-mono text-xs border-t lg:border-t-0 lg:border-l border-[#D8DEE6]">
                  <div className="flex items-center justify-between text-[11px] text-[#64748B] border-b border-[#D8DEE6] pb-2">
                    <span className="text-[#26364A] font-semibold flex items-center gap-1.5">
                      <Code2 className="w-3.5 h-3.5 text-[#2878D8]" />
                      solution.py
                    </span>
                    <span className="px-2 py-0.5 rounded bg-[#FAF9F6] text-[#64748B] border border-[#D8DEE6]">
                      Python 3.12 (Isolated Sandbox)
                    </span>
                  </div>

                  <pre className="text-[#334155] text-[11px] leading-relaxed overflow-x-auto font-mono">
<span className="text-[#2878D8]">def</span> <span className="text-[#26364A] font-semibold">two_sum</span>(nums: <span className="text-[#38A6A0]">list</span>[<span className="text-[#38A6A0]">int</span>], target: <span className="text-[#38A6A0]">int</span>) -&gt; <span className="text-[#38A6A0]">list</span>[<span className="text-[#38A6A0]">int</span>]:
    lookup = {'{}'}
    <span className="text-[#2878D8]">for</span> idx, num <span className="text-[#2878D8]">in</span> enumerate(nums):
        complement = target - num
        <span className="text-[#2878D8]">if</span> complement <span className="text-[#2878D8]">in</span> lookup:
            <span className="text-[#2878D8]">return</span> [lookup[complement], idx]
        lookup[num] = idx
    <span className="text-[#2878D8]">return</span> []
                  </pre>

                  <div className="pt-3 border-t border-[#D8DEE6] flex items-center justify-between">
                    <div className="text-[11px] text-[#64748B] flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-[#2FA878]" />
                      <span>Syntax Validated &bull; Sandbox Bound</span>
                    </div>
                    <button
                      type="button"
                      onClick={handleRunHeroTests}
                      disabled={testRunStatus === 'running'}
                      className="px-3.5 py-1.5 rounded bg-[#2878D8] hover:bg-[#2168C0] active:bg-[#18539C] disabled:opacity-75 text-white font-sans font-semibold text-xs shadow-xs transition-colors flex items-center gap-1.5"
                    >
                      {testRunStatus === 'running' ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Executing...</span>
                        </>
                      ) : testRunStatus === 'completed' ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-white" />
                          <span>Passed (10/10)</span>
                        </>
                      ) : (
                        <span>Run Test Cases</span>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div className="text-center mt-3 text-[11px] font-mono text-[#5E6B7D]">
              Illustrative platform preview &bull; Technical assessment execution environment
            </div>
          </div>
        </div>

        {/* Capability / Trust Strip */}
        <div className="border-t border-[#DDD8CE] bg-[#EDE9E1] py-5 mt-16">
          <div className="w-full px-4 sm:px-6 lg:px-8">
            <div className="flex flex-wrap items-center justify-around gap-6 md:gap-8 text-xs font-mono font-bold text-[#243247] tracking-wider">
              <span className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-[#2878D8]" />
                TECHNICAL ASSESSMENT
              </span>
              <span className="hidden sm:inline text-[#DDD8CE]">&bull;</span>
              <span className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#2878D8]" />
                AUTOMATED EVALUATION
              </span>
              <span className="hidden sm:inline text-[#DDD8CE]">&bull;</span>
              <span className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-[#2878D8]" />
                EXAMINATION INTEGRITY
              </span>
              <span className="hidden sm:inline text-[#DDD8CE]">&bull;</span>
              <span className="flex items-center gap-2">
                <Eye className="w-4 h-4 text-[#2878D8]" />
                REAL-TIME SUPERVISION
              </span>
              <span className="hidden sm:inline text-[#DDD8CE]">&bull;</span>
              <span className="flex items-center gap-2">
                <FileCheck2 className="w-4 h-4 text-[#2878D8]" />
                VERIFIABLE RESULTS
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Core Platform Capabilities */}
      <section className="w-full px-4 sm:px-6 lg:px-8 space-y-12">
        <div className="max-w-2xl mx-auto text-center space-y-3">
          <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">
            Capabilities
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-[#243247] tracking-tight">
            Built around the complete assessment lifecycle.
          </h2>
          <p className="text-xs sm:text-sm text-[#5E6B7D]">
            Engineered capabilities designed for rigorous academic and commercial evaluation.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Pillar 1 */}
          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#D9DDE3] shadow-xs space-y-3">
            <div className="w-10 h-10 rounded-xl bg-[#EAF2FC] text-[#2878D8] flex items-center justify-center font-bold border border-[#D9DDE3]">
              <FileText className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#243247]">Assessment Authoring</h3>
            <p className="text-xs text-[#5E6B7D] leading-relaxed">
              Author single-choice, multiple-choice, and programming questions. Points invariants guarantee point totals match exam configurations with frozen snapshot locking upon publish.
            </p>
          </div>

          {/* Pillar 2 */}
          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#D9DDE3] shadow-xs space-y-3">
            <div className="w-10 h-10 rounded-xl bg-[#EAF2FC] text-[#2878D8] flex items-center justify-center font-bold border border-[#D9DDE3]">
              <UserCheck className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#243247]">Candidate Management</h3>
            <p className="text-xs text-[#5E6B7D] leading-relaxed">
              Target entire institutional cohorts or choose specific candidate rosters. Assignments are synchronized idempotently to grant authoritative exam access upon publication.
            </p>
          </div>

          {/* Pillar 3 */}
          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#D9DDE3] shadow-xs space-y-3">
            <div className="w-10 h-10 rounded-xl bg-[#EAF2FC] text-[#2878D8] flex items-center justify-center font-bold border border-[#D9DDE3]">
              <Code2 className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#243247]">Coding Evaluation</h3>
            <p className="text-xs text-[#5E6B7D] leading-relaxed">
              Execute candidate submissions across Python, C, C++, and Java in isolated sandboxes. Automated test suites evaluate stdout, execution timing, and edge-case accuracy.
            </p>
          </div>

          {/* Pillar 4 */}
          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#D9DDE3] shadow-xs space-y-3">
            <div className="w-10 h-10 rounded-xl bg-[#EAF2FC] text-[#2878D8] flex items-center justify-center font-bold border border-[#D9DDE3]">
              <Eye className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#243247]">Examination Supervision</h3>
            <p className="text-xs text-[#5E6B7D] leading-relaxed">
              Real-time focus and fullscreen status monitoring with automated warning acknowledgment workflows. Authorized proctors can supervise multiple active sessions simultaneously.
            </p>
          </div>

          {/* Pillar 5 */}
          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#D9DDE3] shadow-xs space-y-3">
            <div className="w-10 h-10 rounded-xl bg-[#EAF2FC] text-[#2878D8] flex items-center justify-center font-bold border border-[#D9DDE3]">
              <Layers className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#243247]">Results &amp; Analytics</h3>
            <p className="text-xs text-[#5E6B7D] leading-relaxed">
              Deterministic scoring compiles instant score distributions, attendance summaries, and question-level telemetry with structured audit logs for administrative review.
            </p>
          </div>

          {/* Pillar 6 */}
          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#D9DDE3] shadow-xs space-y-3">
            <div className="w-10 h-10 rounded-xl bg-[#EAF2FC] text-[#2878D8] flex items-center justify-center font-bold border border-[#D9DDE3]">
              <Award className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#243247]">Certificate Verification</h3>
            <p className="text-xs text-[#5E6B7D] leading-relaxed">
              Issue verifiable examination certificates with unique certificate IDs. Third parties can authenticate outcomes via the public verification portal.
            </p>
          </div>
        </div>
      </section>

      {/* Interactive Product Showcase (Presentation-Only) */}
      <section className="w-full px-4 sm:px-6 lg:px-8 space-y-8">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-[#DDD8CE] pb-5">
          <div>
            <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">
              Product Showcase
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-[#243247] tracking-tight mt-1">
              Platform Experience in Action
            </h2>
          </div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#FAF9F6] border border-[#DDD8CE] text-[#5E6B7D] text-xs font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-[#2878D8]"></span>
            <span>Illustrative platform preview</span>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setActiveShowcaseTab('command-center')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeShowcaseTab === 'command-center'
                ? 'bg-[#2878D8] text-white shadow-xs'
                : 'bg-[#FAF9F6] text-[#64748B] hover:bg-[#F3F5F7] border border-[#D8DEE6]'
            }`}
          >
            01 Assessment Command Center
          </button>
          <button
            type="button"
            onClick={() => setActiveShowcaseTab('candidate-env')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeShowcaseTab === 'candidate-env'
                ? 'bg-[#2878D8] text-white shadow-xs'
                : 'bg-[#FAF9F6] text-[#64748B] hover:bg-[#F3F5F7] border border-[#D8DEE6]'
            }`}
          >
            02 Candidate Exam Workspace
          </button>
          <button
            type="button"
            onClick={() => setActiveShowcaseTab('proctor-console')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeShowcaseTab === 'proctor-console'
                ? 'bg-[#2878D8] text-white shadow-xs'
                : 'bg-[#FAF9F6] text-[#64748B] hover:bg-[#F3F5F7] border border-[#D8DEE6]'
            }`}
          >
            03 Proctor Supervision Console
          </button>
          <button
            type="button"
            onClick={() => setActiveShowcaseTab('verification')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeShowcaseTab === 'verification'
                ? 'bg-[#2878D8] text-white shadow-xs'
                : 'bg-[#FAF9F6] text-[#64748B] hover:bg-[#F3F5F7] border border-[#D8DEE6]'
            }`}
          >
            04 Results &amp; Verification
          </button>
        </div>

        {/* Tab Content Display */}
        <div className="bg-[#FAF9F6] rounded-2xl border border-[#D8DEE6] shadow-xs p-6 sm:p-8">
          {activeShowcaseTab === 'command-center' && (
            <div className="space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#D8DEE6] pb-4">
                <div>
                  <span className="text-[11px] font-mono font-bold text-[#2878D8] uppercase">Assessment Config</span>
                  <h3 className="text-lg font-bold text-[#26364A]">CS-301: Advanced Algorithms Examination</h3>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="px-2.5 py-1 rounded-md bg-[#E8F5F3] text-[#2FA878] font-bold border border-[#2FA878]/30">
                    Status: Scheduled
                  </span>
                  <span className="px-2.5 py-1 rounded-md bg-[#F3F5F7] text-[#26364A] font-mono border border-[#D8DEE6]">
                    24 Candidates
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
                <div className="p-3.5 rounded-xl bg-[#F3F5F7] border border-[#D8DEE6]">
                  <div className="text-[#64748B] text-[11px]">CONFIGURATION</div>
                  <div className="text-[#26364A] font-bold mt-1 text-sm">4 Questions &bull; 100 Points</div>
                  <div className="text-[#64748B] text-[11px] mt-0.5">Points Invariant Verified</div>
                </div>
                <div className="p-3.5 rounded-xl bg-[#F3F5F7] border border-[#D8DEE6]">
                  <div className="text-[#64748B] text-[11px]">EXAM WINDOW</div>
                  <div className="text-[#26364A] font-bold mt-1 text-sm">90 Minutes Duration</div>
                  <div className="text-[#64748B] text-[11px] mt-0.5">Strict Expiry Bounds</div>
                </div>
                <div className="p-3.5 rounded-xl bg-[#F3F5F7] border border-[#D8DEE6]">
                  <div className="text-[#64748B] text-[11px]">AUDIENCE POLICY</div>
                  <div className="text-[#26364A] font-bold mt-1 text-sm">All Students Targeted</div>
                  <div className="text-[#64748B] text-[11px] mt-0.5">Idempotent Access Control</div>
                </div>
              </div>
            </div>
          )}

          {activeShowcaseTab === 'candidate-env' && (
            <div className="space-y-4 font-mono text-xs">
              <div className="flex items-center justify-between border-b border-[#D8DEE6] pb-3 font-sans">
                <div>
                  <h3 className="text-sm font-bold text-[#26364A]">Candidate Examination Environment</h3>
                  <p className="text-xs text-[#64748B] font-mono mt-0.5">Focus Tracking Active &bull; No External Extension Needed</p>
                </div>
                <div className="px-3 py-1 rounded bg-[#F3F5F7] text-[#26364A] font-mono text-xs font-bold border border-[#D8DEE6]">
                  Time Remaining: 01:14:22
                </div>
              </div>

              <div className="p-4 rounded-xl bg-[#F1F4F7] text-[#334155] space-y-3 border border-[#D8DEE6]">
                <div className="flex items-center justify-between text-[11px] text-[#64748B] border-b border-[#D8DEE6] pb-2">
                  <span>Language: Python 3.12 (Isolated Sandbox)</span>
                  <span className="text-[#38A6A0] font-semibold flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#38A6A0]"></span>
                    Environment Ready
                  </span>
                </div>
                <pre className="text-[#334155] text-xs leading-relaxed overflow-x-auto font-mono">
<span className="text-[#2878D8]">class</span> <span className="text-[#26364A] font-semibold">GraphTraversal</span>:
    <span className="text-[#2878D8]">def</span> <span className="text-[#26364A] font-semibold">breadth_first_search</span>(self, graph, start_node):
        visited = set([start_node])
        queue = [start_node]
        order = []
        <span className="text-[#2878D8]">while</span> queue:
            vertex = queue.pop(0)
            order.append(vertex)
            <span className="text-[#2878D8]">for</span> neighbor <span className="text-[#2878D8]">in</span> graph.get(vertex, []):
                <span className="text-[#2878D8]">if</span> neighbor <span className="text-[#2878D8]">not in</span> visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        <span className="text-[#2878D8]">return</span> order
                </pre>
              </div>

              <div className="p-3 rounded-lg bg-[#E8F5F3] border border-[#2FA878]/30 text-[#26364A] flex items-center justify-between text-xs">
                <span className="text-[#26364A] font-medium">&check; 3 Public Test Cases Evaluated (Execution: 0.18s)</span>
                <span className="font-bold text-[#2FA878]">ALL PASS</span>
              </div>
            </div>
          )}

          {activeShowcaseTab === 'proctor-console' && (
            <div className="space-y-5 text-xs">
              <div className="flex items-center justify-between border-b border-[#D8DEE6] pb-3">
                <div>
                  <h3 className="text-sm font-bold text-[#26364A]">Proctor Supervision Console</h3>
                  <p className="text-xs text-[#64748B]">Live multi-candidate examination telemetry</p>
                </div>
                <span className="px-2.5 py-1 rounded-full bg-[#EAF2FC] text-[#2878D8] border border-[#2878D8]/20 font-mono font-bold text-[11px]">
                  WebSocket Stream Active
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-[11px]">
                <div className="p-4 rounded-xl bg-[#F3F5F7] border border-[#D8DEE6] space-y-2">
                  <div className="font-bold text-[#26364A]">CANDIDATE: BETN1AI25079</div>
                  <div className="text-[#64748B]">Status: In Progress &bull; Q03</div>
                  <div className="text-[#2FA878] font-bold">&bull; Fullscreen &amp; Tab Focus Stable</div>
                  <div className="text-[#64748B]">Last Telemetry Ping: 2s ago</div>
                </div>

                <div className="p-4 rounded-xl bg-[#F3F5F7] border border-[#D8DEE6] space-y-2">
                  <div className="font-bold text-[#26364A]">CANDIDATE: BETN1AI25076</div>
                  <div className="text-[#64748B]">Status: In Progress &bull; Q02</div>
                  <div className="text-[#C98A2E] font-bold">&bull; Advisory Warning Acknowledged</div>
                  <div className="text-[#64748B]">Proctor Intervention Available</div>
                </div>
              </div>
            </div>
          )}

          {activeShowcaseTab === 'verification' && (
            <div className="space-y-5 text-xs">
              <div className="flex items-center justify-between border-b border-[#D8DEE6] pb-3">
                <div>
                  <h3 className="text-sm font-bold text-[#26364A]">Result Summary &amp; Certificate Verification</h3>
                  <p className="text-xs text-[#64748B]">Public credential lookup and outcome validation</p>
                </div>
                <span className="px-2.5 py-1 rounded-md bg-[#E8F5F3] text-[#2FA878] font-bold text-xs border border-[#2FA878]/30">
                  Certificate Verified
                </span>
              </div>

              <div className="p-4 rounded-xl bg-[#F3F5F7] border border-[#D8DEE6] space-y-3 font-mono">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#64748B]">Certificate ID:</span>
                  <span className="font-bold text-[#26364A]">EXAMPLE-CS301-2026</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#64748B]">Examination:</span>
                  <span className="text-[#26364A]">Advanced Algorithms Examination</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#64748B]">Score Earned:</span>
                  <span className="text-[#26364A] font-bold">95 / 100 (95%)</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-[#64748B]">Integrity Outcome:</span>
                  <span className="text-[#2FA878] font-bold">Completed &bull; Supervision Approved</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* =========================================================================
          2. SOLUTIONS: TARGET ORGANIZATIONS
          ========================================================================= */}
      <section id="solutions" className="w-full px-4 sm:px-6 lg:px-8 space-y-10 scroll-mt-24">
        <div className="max-w-2xl mx-auto text-center space-y-3">
          <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">
            Target Organizations
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-[#243247] tracking-tight">
            Built for organizations that evaluate technical capability.
          </h2>
          <p className="text-xs sm:text-sm text-[#5E6B7D]">
            Tailored assessment delivery across academic, certification, and commercial engineering environments.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#DDD8CE] shadow-xs space-y-3">
            <GraduationCap className="w-6 h-6 text-[#2878D8]" />
            <h3 className="text-sm font-bold text-[#243247]">Universities &amp; Colleges</h3>
            <p className="text-xs text-[#5E6B7D] leading-relaxed">
              Conduct midterm, final, and practical programming examinations with automated evaluation and proctor supervision.
            </p>
          </div>

          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#DDD8CE] shadow-xs space-y-3">
            <Award className="w-6 h-6 text-[#2878D8]" />
            <h3 className="text-sm font-bold text-[#243247]">Certification Bodies</h3>
            <p className="text-xs text-[#5E6B7D] leading-relaxed">
              Administer standardized technical certification tests with verifiable credential IDs and consistent grading.
            </p>
          </div>

          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#DDD8CE] shadow-xs space-y-3">
            <Building2 className="w-6 h-6 text-[#2878D8]" />
            <h3 className="text-sm font-bold text-[#243247]">Training Institutions</h3>
            <p className="text-xs text-[#5E6B7D] leading-relaxed">
              Evaluate coding bootcamps and vocational technical programs with automated test suites and progress telemetry.
            </p>
          </div>

          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#DDD8CE] shadow-xs space-y-3">
            <Terminal className="w-6 h-6 text-[#2878D8]" />
            <h3 className="text-sm font-bold text-[#243247]">Engineering &amp; Hiring</h3>
            <p className="text-xs text-[#5E6B7D] leading-relaxed">
              Assess programming proficiency using practical real-world problem sets in standard language environments.
            </p>
          </div>
        </div>
      </section>

      {/* =========================================================================
          3. HOW IT WORKS: PROBLEM & THE ExamIIO OPERATIONAL MODEL
          ========================================================================= */}
      <section id="how-it-works" className="w-full px-4 sm:px-6 lg:px-8 space-y-16 scroll-mt-24">
        {/* The Problem & Unified Platform */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-5 space-y-4">
            <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">
              The Architecture Problem
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-[#243247] tracking-tight leading-tight">
              Technical assessment is still fragmented.
            </h2>
            <p className="text-sm text-[#5E6B7D] leading-relaxed">
              Institutions often depend on disconnected tools: one system for authoring questions, another for delivering tests, an external tool for code grading, separate software for webcam supervision, and spreadsheets for compiling grades.
            </p>
            <p className="text-sm font-semibold text-[#243247] border-l-2 border-[#2878D8] pl-3">
              This fragmentation causes grading inconsistencies, supervision blind spots, and administrative overhead.
            </p>
          </div>

          <div className="lg:col-span-7 p-6 sm:p-8 bg-[#FAF9F6] rounded-2xl border border-[#DDD8CE] shadow-xs space-y-4">
            <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">
              The ExamIIO Approach
            </div>
            <h3 className="text-lg font-bold text-[#243247]">
              Single Controlled Assessment Infrastructure
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-3 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE]">
                <span className="font-bold text-[#243247] block mb-1">Authoritative Snapshot</span>
                <span className="text-[#5E6B7D]">Frozen configuration ensures candidate evaluation is point-invariant.</span>
              </div>
              <div className="p-3 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE]">
                <span className="font-bold text-[#243247] block mb-1">Bounded Sandbox</span>
                <span className="text-[#5E6B7D]">Submissions run in isolated containers with strict CPU/memory boundaries.</span>
              </div>
              <div className="p-3 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE]">
                <span className="font-bold text-[#243247] block mb-1">Live Human Oversight</span>
                <span className="text-[#5E6B7D]">Structured supervision signals equip proctors to intervene authoritatively.</span>
              </div>
              <div className="p-3 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE]">
                <span className="font-bold text-[#243247] block mb-1">Verifiable Credentials</span>
                <span className="text-[#5E6B7D]">Permanent credential identifiers enable instant public validation.</span>
              </div>
            </div>
            <p className="text-xs text-[#5E6B7D] pt-2">
              ExamIIO replaces disconnected workflows with one integrated platform from authoring to certification.
            </p>
          </div>
        </div>

        {/* The 4-Stage Operational Model */}
        <div className="space-y-10 pt-4 border-t border-[#DDD8CE]">
          <div className="max-w-2xl mx-auto text-center space-y-3">
            <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">
              Operational Model
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-[#243247] tracking-tight">
              One assessment. One controlled environment.
            </h2>
            <p className="text-xs sm:text-sm text-[#5E6B7D]">
              Four sequential phases designed to maintain structural assessment integrity.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-5 bg-[#FAF9F6] rounded-xl border border-[#D9DDE3] shadow-xs space-y-3 relative">
              <div className="text-xs font-mono font-bold text-[#2878D8]">STAGE 01</div>
              <h3 className="text-base font-bold text-[#243247]">CREATE</h3>
              <p className="text-xs text-[#5E6B7D] leading-relaxed">
                Build structured technical assessments with multi-format questions, points invariants, and locked snapshots.
              </p>
            </div>

            <div className="p-5 bg-[#FAF9F6] rounded-xl border border-[#D9DDE3] shadow-xs space-y-3 relative">
              <div className="text-xs font-mono font-bold text-[#2878D8]">STAGE 02</div>
              <h3 className="text-base font-bold text-[#243247]">CONDUCT</h3>
              <p className="text-xs text-[#5E6B7D] leading-relaxed">
                Deliver controlled examinations to eligible candidates with session timeouts, focus tracking, and supervision signals.
              </p>
            </div>

            <div className="p-5 bg-[#FAF9F6] rounded-xl border border-[#D9DDE3] shadow-xs space-y-3 relative">
              <div className="text-xs font-mono font-bold text-[#2878D8]">STAGE 03</div>
              <h3 className="text-base font-bold text-[#243247]">EVALUATE</h3>
              <p className="text-xs text-[#5E6B7D] leading-relaxed">
                Execute programming code in sandboxed environments with automated deterministic scoring against test cases.
              </p>
            </div>

            <div className="p-5 bg-[#FAF9F6] rounded-xl border border-[#D9DDE3] shadow-xs space-y-3 relative">
              <div className="text-xs font-mono font-bold text-[#2878D8]">STAGE 04</div>
              <h3 className="text-base font-bold text-[#243247]">VERIFY</h3>
              <p className="text-xs text-[#5E6B7D] leading-relaxed">
                Review examination integrity records, generate final score reports, and issue publicly verifiable certificate IDs.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          4. TECHNOLOGY: ARCHITECTURE & PROCESSING PIPELINE
          ========================================================================= */}
      <section id="technology" className="w-full px-4 sm:px-6 lg:px-8 space-y-12 scroll-mt-24">
        <div className="max-w-2xl mx-auto text-center space-y-3">
          <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">
            Architecture
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-[#243247] tracking-tight">
            Engineered for deterministic assessment.
          </h2>
          <p className="text-xs sm:text-sm text-[#5E6B7D]">
            A linear, auditable processing pipeline ensuring consistent execution for every candidate.
          </p>
        </div>

        {/* Pipeline Architecture Diagram */}
        <div className="p-6 sm:p-8 bg-[#FAF9F6] rounded-2xl border border-[#DDD8CE] shadow-xs space-y-6">
          <div className="text-xs font-mono font-bold text-[#243247] uppercase tracking-wider text-center">
            Assessment Processing Pipeline
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-center text-xs font-mono">
            <div className="p-3 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE] space-y-1">
              <div className="text-[#2878D8] font-bold">01 LAYER</div>
              <div className="font-bold text-[#243247]">Assessment Layer</div>
              <div className="text-[10px] text-[#5E6B7D]">Question Versioning</div>
            </div>

            <div className="p-3 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE] space-y-1">
              <div className="text-[#2878D8] font-bold">02 ENGINE</div>
              <div className="font-bold text-[#243247]">Evaluation Engine</div>
              <div className="text-[10px] text-[#5E6B7D]">Test Case Suites</div>
            </div>

            <div className="p-3 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE] space-y-1">
              <div className="text-[#2878D8] font-bold">03 RUNTIME</div>
              <div className="font-bold text-[#243247]">Isolated Sandbox</div>
              <div className="text-[10px] text-[#5E6B7D]">Container Execution</div>
            </div>

            <div className="p-3 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE] space-y-1">
              <div className="text-[#2878D8] font-bold">04 RESULTS</div>
              <div className="font-bold text-[#243247]">Result Engine</div>
              <div className="text-[10px] text-[#5E6B7D]">Deterministic Scoring</div>
            </div>

            <div className="p-3 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE] space-y-1">
              <div className="text-[#2878D8] font-bold">05 TRUST</div>
              <div className="font-bold text-[#243247]">Integrity Layer</div>
              <div className="text-[10px] text-[#5E6B7D]">Supervision Signals</div>
            </div>

            <div className="p-3 bg-[#EDE9E1] rounded-xl border border-[#DDD8CE] space-y-1">
              <div className="text-[#2878D8] font-bold">06 OUTCOME</div>
              <div className="font-bold text-[#243247]">Reporting Portal</div>
              <div className="text-[10px] text-[#5E6B7D]">Certificate IDs</div>
            </div>
          </div>
        </div>

        {/* Core Philosophy / Why ExamIIO */}
        <div className="p-8 sm:p-12 bg-[#FAF9F6] rounded-3xl border border-[#DDD8CE] space-y-8 shadow-xs">
          <div className="max-w-2xl space-y-3">
            <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">
              Core Philosophy
            </div>
            <h2 className="text-2xl sm:text-3xl font-black text-[#243247] tracking-tight">
              Assessment should measure capability &mdash; not technical friction.
            </h2>
            <p className="text-[#5E6B7D] text-xs sm:text-sm leading-relaxed">
              Four architectural principles guide every aspect of ExamIIO development.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-[#EDE9E1] border border-[#DDD8CE] space-y-2">
              <div className="font-mono font-bold text-[#2878D8]">01 DETERMINISTIC</div>
              <p className="text-[#5E6B7D] leading-relaxed">
                Consistent evaluation across submissions. The same valid code produces identical results every time.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#EDE9E1] border border-[#DDD8CE] space-y-2">
              <div className="font-mono font-bold text-[#2878D8]">02 CONTROLLED</div>
              <p className="text-[#5E6B7D] leading-relaxed">
                Explicit examination boundaries, locked snapshots, and immutable versioning prevent assessment ambiguity.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#EDE9E1] border border-[#DDD8CE] space-y-2">
              <div className="font-mono font-bold text-[#2878D8]">03 OBSERVABLE</div>
              <p className="text-[#5E6B7D] leading-relaxed">
                Authorized human supervisors monitor live candidate activity with structured signals, not opaque heuristics.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#EDE9E1] border border-[#DDD8CE] space-y-2">
              <div className="font-mono font-bold text-[#2878D8]">04 VERIFIABLE</div>
              <p className="text-[#5E6B7D] leading-relaxed">
                Outcomes and certificates can be authenticated via the public verification portal using permanent certificate IDs.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          5. SECURITY & INTEGRITY
          ========================================================================= */}
      <section id="security" className="w-full px-4 sm:px-6 lg:px-8 space-y-8 scroll-mt-24">
        <div className="max-w-2xl mx-auto text-center space-y-3">
          <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">
            Integrity Controls
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-[#243247] tracking-tight">
            Security engineered for academic trust.
          </h2>
          <p className="text-xs sm:text-sm text-[#5E6B7D]">
            Rigorous session isolation and transparent proctor signals protect examination validity.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#DDD8CE] shadow-xs space-y-3">
            <h3 className="text-sm font-bold text-[#243247] flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[#2878D8]" />
              Examination Integrity Controls
            </h3>
            <p className="text-[#5E6B7D] leading-relaxed">
              Assessment sessions enforce strict boundary controls: focus state monitoring, fullscreen tracking, and real-time supervision signals. Rather than relying on black-box heuristics, authorized human proctors review structured signals to make authoritative decisions.
            </p>
          </div>

          <div className="p-6 bg-[#FAF9F6] rounded-2xl border border-[#DDD8CE] shadow-xs space-y-3">
            <h3 className="text-sm font-bold text-[#243247] flex items-center gap-2">
              <Lock className="w-4 h-4 text-[#2878D8]" />
              Structured Audit Records &amp; Sandboxing
            </h3>
            <p className="text-[#5E6B7D] leading-relaxed">
              Administrative actions, question modifications, and student submissions generate structured audit trails. Candidate code executes strictly within isolated sandboxes without access to the host file system or network sockets.
            </p>
          </div>
        </div>
      </section>

      {/* =========================================================================
          6. ABOUT ExamIIO & FOUNDER PROFILE
          ========================================================================= */}
      <section id="about" className="w-full px-4 sm:px-6 lg:px-8 space-y-8 scroll-mt-24">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
          {/* About Narrative (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">
              About ExamIIO
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-[#243247] tracking-tight">
              Building better infrastructure for technical assessment.
            </h2>
            <p className="text-xs sm:text-sm text-[#5E6B7D] leading-relaxed">
              ExamIIO was designed from first principles to address the reliability gap in technical examinations. Traditional online test platforms often compromise between usability and examination integrity, resulting in brittle grading pipelines and superficial proctoring tools.
            </p>
            <p className="text-xs sm:text-sm text-[#5E6B7D] leading-relaxed">
              Our engineering mission is to deliver dependable, deterministic assessment infrastructure where administrators author with confidence, candidates write code in realistic environments, and institutions issue trustworthy credentials.
            </p>
          </div>

          {/* Founder Profile (5 cols) */}
          <div id="founder" className="lg:col-span-5 p-6 bg-[#FAF9F6] rounded-2xl border border-[#DDD8CE] shadow-xs space-y-4">
            <div className="text-xs font-mono font-bold text-[#2878D8] uppercase tracking-wider">
              Engineering Leadership
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-bold text-[#243247]">Gaurav Agarwal</h3>
              <div className="text-xs font-semibold text-[#5E6B7D]">Founder &amp; Lead Developer</div>
            </div>
            <p className="text-xs text-[#5E6B7D] leading-relaxed">
              Leading the architectural design and full-stack development of ExamIIO, focusing on deterministic code evaluation, exam snapshot immutability, and high-trust assessment workflows.
            </p>
            <div className="pt-2 border-t border-[#DDD8CE] flex items-center justify-between text-xs font-mono text-[#5E6B7D]">
              <a
                href={EXAMIO_CONTACT_MAILTO}
                className="flex items-center gap-2 hover:text-[#2878D8] transition-colors"
                title="Contact Gaurav Agarwal via email"
              >
                <Mail className="w-3.5 h-3.5 text-[#2878D8]" />
                <span>{CONTACT_EMAIL}</span>
              </a>
            </div>
          </div>
        </div>

        {/* Technology & Intellectual Property */}
        <div id="ip" className="p-6 sm:p-8 bg-[#EDE9E1] rounded-2xl border border-[#DDD8CE] space-y-3 text-xs">
          <div className="text-[11px] font-mono font-bold text-[#2878D8] uppercase tracking-wider">
            Proprietary Development
          </div>
          <h3 className="text-base font-bold text-[#243247]">Technology &amp; Intellectual Property</h3>
          <p className="text-[#5E6B7D] leading-relaxed">
            ExamIIO comprises proprietary platform architecture developed specifically for deterministic technical examinations: including our point-invariant assessment authoring system, multi-language sandbox execution contract, and authoritative student eligibility pipeline. All design elements, architecture specifications, and software implementations are proprietary intellectual property of ExamIIO.
          </p>
        </div>
      </section>

      {/* =========================================================================
          7. DEDICATED CONTACT SECTION (REPLACES OLD CONFIDENCE CTA)
          ========================================================================= */}
      <section id="contact" className="w-full px-4 sm:px-6 lg:px-8 scroll-mt-24">
        <div className="rounded-3xl bg-[#FAF9F6] border border-[#DDD8CE] p-8 sm:p-12 shadow-xs text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#EDE9E1] text-[#243247] border border-[#DDD8CE] text-xs font-mono font-semibold">
            <Mail className="w-3.5 h-3.5 text-[#2878D8]" />
            <span>CONTACT ExamIIO</span>
          </div>

          <h2 className="text-2xl sm:text-4xl font-black text-[#243247] tracking-tight">
            Let&apos;s build better technical assessments.
          </h2>

          <p className="text-xs sm:text-sm text-[#5E6B7D] max-w-xl mx-auto leading-relaxed">
            Institutions, educators, certification bodies, and engineering organizations can contact ExamIIO directly regarding the platform, architecture evaluations, and technical integrations.
          </p>

          {/* Contact Details Card */}
          <div className="max-w-md mx-auto p-5 rounded-2xl bg-[#EDE9E1] border border-[#DDD8CE] text-left space-y-3">
            <div className="flex items-center justify-between border-b border-[#DDD8CE] pb-2 text-xs">
              <span className="font-mono text-[#5E6B7D]">Direct Developer Contact</span>
              <span className="font-mono text-[#2FA878] font-semibold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#2FA878]"></span>
                Available
              </span>
            </div>
            <div>
              <div className="font-bold text-sm text-[#243247]">Gaurav Agarwal</div>
              <div className="text-xs text-[#5E6B7D]">Founder &amp; Lead Developer</div>
            </div>
            <div className="text-xs font-mono text-[#243247] flex items-center justify-between bg-[#FAF9F6] p-2.5 rounded-lg border border-[#DDD8CE]">
              <a
                href={EXAMIO_CONTACT_MAILTO}
                className="truncate hover:text-[#2878D8] transition-colors"
                title="Send email inquiry to ExamIIO"
              >
                {CONTACT_EMAIL}
              </a>
              <button
                type="button"
                onClick={handleCopyEmail}
                className="ml-2 px-2 py-1 rounded hover:bg-[#EDE9E1] text-[#2878D8] transition text-[11px] font-sans font-semibold flex items-center gap-1 shrink-0"
                title="Copy email address"
              >
                {emailCopied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-[#2FA878]" />
                    <span className="text-[#2FA878]">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <a
              href={EXAMIO_CONTACT_MAILTO}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[#2878D8] hover:bg-[#2065B8] active:bg-[#18539C] text-white text-xs sm:text-sm font-semibold transition-all shadow-xs"
            >
              <Mail className="w-4 h-4" />
              <span>Get in Touch</span>
            </a>
            <Link to="/login">
              <Button
                variant="secondary"
                size="md"
                className="px-6 text-xs sm:text-sm font-semibold border-[#DDD8CE] text-[#243247] bg-[#FAF9F6] hover:bg-[#EDE9E1]"
              >
                Platform Sign In &rarr;
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
