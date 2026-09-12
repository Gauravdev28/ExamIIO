import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Code2,
  ListFilter,
  X,
  ArrowRight,
  Zap,
} from 'lucide-react';
import { QuestionType } from '../../types/question';

interface CreateQuestionModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface QuestionTypeCard {
  type: QuestionType;
  title: string;
  subtitle: string;
  description: string;
  icon: React.ReactNode;
  accentColor: string;
  badge: string;
  isPrimary?: boolean;
}

const SUPPORTED_TYPES: QuestionTypeCard[] = [
  {
    type: 'CODING',
    title: 'Coding Question',
    subtitle: 'Algorithms & Sandboxed Execution',
    description: 'Interactive single-page workspace with Monaco Editor, Judge0/Isolate verification, and test case management.',
    icon: <Code2 className="w-5 h-5 text-emerald-600" />,
    accentColor: 'border-emerald-300 hover:border-emerald-600 bg-emerald-50/30 hover:bg-emerald-50/80 ring-1 ring-emerald-500/20',
    badge: 'Single-Page Workspace',
    isPrimary: true,
  },
  {
    type: 'MCQ',
    title: 'Multiple Choice (MCQ)',
    subtitle: 'Single Answer',
    description: 'Standard multiple choice question with a single authoritative correct option and optional penalty points.',
    icon: <ListFilter className="w-5 h-5 text-purple-600" />,
    accentColor: 'border-slate-200 hover:border-purple-500 hover:bg-purple-50/40',
    badge: 'Single Choice',
  },
];

export const CreateQuestionModal: React.FC<CreateQuestionModalProps> = ({
  isOpen,
  onClose,
}) => {
  const navigate = useNavigate();

  if (!isOpen) return null;

  const handleSelectType = (type: QuestionType) => {
    onClose();
    navigate(`/admin/questions/create?type=${type}`);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-question-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-in fade-in duration-200"
    >
      <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 max-w-3xl w-full overflow-hidden text-slate-900">
        {/* Header */}
        <div className="px-6 py-5 bg-white border-b border-slate-200 text-slate-900 flex items-center justify-between">
          <div className="space-y-1">
            <h2 id="create-question-modal-title" className="text-lg font-bold tracking-tight flex items-center gap-2 text-slate-900">
              <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-200">
                <Zap className="w-4 h-4" />
              </div>
              Create Question
            </h2>
            <p className="text-xs text-slate-500">
              Select a question architecture to begin authoring. Coding questions launch directly into the single-page workspace.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-2 rounded-xl hover:bg-slate-100 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Compact Type Cards Grid */}
        <div className="p-6 max-h-[75vh] overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {SUPPORTED_TYPES.map((card) => (
              <button
                key={card.type}
                type="button"
                onClick={() => handleSelectType(card.type)}
                className={`text-left p-4 rounded-2xl border transition-all duration-200 flex flex-col justify-between group ${card.accentColor} hover:shadow-md cursor-pointer ${
                  card.isPrimary ? 'md:col-span-2' : ''
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-xl bg-white border border-slate-200 shadow-xs group-hover:scale-105 transition-transform">
                        {card.icon}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-bold text-slate-900 group-hover:text-emerald-700 transition-colors">
                            {card.title}
                          </h3>
                          {card.isPrimary && (
                            <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                              Primary Flow
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] font-semibold text-slate-500 font-mono">
                          {card.subtitle}
                        </p>
                      </div>
                    </div>
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                      {card.badge}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed mt-1">
                    {card.description}
                  </p>
                </div>

                <div className="mt-3 pt-2.5 border-t border-slate-200/60 flex items-center justify-between text-xs font-semibold text-slate-500 group-hover:text-emerald-700">
                  <span>{card.type === 'CODING' ? 'Open Coding Workspace' : 'Start Authoring'}</span>
                  <ArrowRight className="w-3.5 h-3.5 transform group-hover:translate-x-1 transition-transform" />
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CreateQuestionModal;
