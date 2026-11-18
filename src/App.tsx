import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Upload,
  Check,
  X,
  ArrowRight,
  Download,
  Terminal,
  Plus,
  RotateCcw,
  ChevronRight,
  Sliders,
  FileText,
  Printer,
  Code2,
} from 'lucide-react';

interface CheckItem {
  id: string;
  passed: boolean;
  detail: string;
}

interface WorkspaceSnapshot {
  config: any;
  state: any;
  finalPlan: any;
  lastTrace: string;
  sessionTrace: string;
  reportHtml: string;
  terminalOutput?: string;
  commandExecuted?: string;
  executionSeconds?: number;
}

type DetailModalType =
  | null
  | 'venue'
  | 'food'
  | 'budget'
  | 'schedule'
  | 'judging'
  | 'new_input';

const ROUTER_PREVIEW_RULES = [
  {
    keyPattern: 'budget.committed.*, budget.cap',
    example: 'Finance line item bill update or budget cap adjustment',
    areas: ['budget'],
  },
  {
    keyPattern: 'food.option.*, food.quantity',
    example: 'Caterer per-head price change or meal quantity override',
    areas: ['food', 'budget'],
  },
  {
    keyPattern: 'venue.option.*, constraint.venue.*',
    example: 'New venue quote or required hall feature (e.g. generator)',
    areas: ['venue', 'budget'],
  },
  {
    keyPattern: 'event.duration_minutes, constraint.schedule.*',
    example: 'Added break block or schedule duration change',
    areas: ['schedule'],
  },
  {
    keyPattern: 'judging.confirmed, judging.engaged',
    example: 'Confirmed judge count changed (cascades to total headcount)',
    areas: ['judging', 'venue', 'food', 'schedule', 'budget'],
  },
  {
    keyPattern: 'event.students, event.team_size',
    example: 'Student count or team size changed (cascades to all 5 areas)',
    areas: ['judging', 'venue', 'food', 'schedule', 'budget'],
  },
];

function formatDurationLabel(minutes: number): string {
  if (!minutes) return '0 Hours';
  if (minutes % 60 === 0) {
    const hrs = minutes / 60;
    return hrs === 1 ? '1 Hour' : `${hrs} Hours`;
  }
  return `${minutes} Min`;
}

export default function App() {
  const [snapshot, setSnapshot] = useState<WorkspaceSnapshot | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [running, setRunning] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'activity' | 'judge' | 'developer'>(
    'overview'
  );
  const [activitySubView, setActivitySubView] = useState<'feed' | 'trace' | 'slip'>('feed');
  const [showJudgeTrace, setShowJudgeTrace] = useState<boolean>(false);
  const [showHomeInput, setShowHomeInput] = useState<boolean>(false);
  const [detailModal, setDetailModal] = useState<DetailModalType>(null);
  const [selectedCheckId, setSelectedCheckId] = useState<string | null>(null);
  const [expandedActivityKey, setExpandedActivityKey] = useState<string | null>(null);
  const [customText, setCustomText] = useState<string>('');
  const [customFilename, setCustomFilename] = useState<string>('custom_pack.txt');
  const [devSection, setDevSection] = useState<
    'trace' | 'prompt' | 'json' | 'router' | 'config' | 'report'
  >('trace');
  const [selectedRuleIdx, setSelectedRuleIdx] = useState<number>(0);

  const fetchSnapshot = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/state');
      const data = await res.json();
      setSnapshot(data);
      if (!data?.finalPlan) {
        setShowHomeInput(true);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSnapshot();
  }, []);

  const runPackPath = async (packPath: string) => {
    setRunning(true);
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ packPath }),
      });
      const data = await res.json();
      setSnapshot(data);
      setShowHomeInput(false);
      setDetailModal(null);
      setCustomText('');
    } catch (e) {
      console.error(e);
    } finally {
      setRunning(false);
    }
  };

  const handleGeneratePlan = async () => {
    if (customText.trim()) {
      setRunning(true);
      try {
        const res = await fetch('/api/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ customContent: customText, customFilename }),
        });
        const data = await res.json();
        setSnapshot(data);
        setShowHomeInput(false);
        setDetailModal(null);
        setCustomText('');
      } catch (e) {
        console.error(e);
      } finally {
        setRunning(false);
      }
      return;
    }

    await runPackPath('tests/packs/sample_pack.txt');
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setCustomFilename(file.name);
    const reader = new FileReader();
    reader.onload = (ev) => {
      setCustomText(String(ev.target?.result || ''));
    };
    reader.readAsText(file);
  };

  const handleReset = async () => {
    setRunning(true);
    try {
      const res = await fetch('/api/reset', { method: 'POST' });
      const data = await res.json();
      setSnapshot(data);
      setCustomText('');
      setShowHomeInput(true);
      setActiveTab('overview');
    } catch (e) {
      console.error(e);
    } finally {
      setRunning(false);
    }
  };

  const handleUpdateConfig = async (provider: string, model: string, judgesPolicy: string) => {
    setRunning(true);
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          llm: { provider, model },
          policy: { judges_engaged: judgesPolicy },
        }),
      });
      const data = await res.json();
      setSnapshot(data);
    } catch (e) {
      console.error(e);
    } finally {
      setRunning(false);
    }
  };

  const downloadFile = (filename: string, content: string, mimeType = 'text/plain') => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleExport = () => {
    if (!snapshot) return;
    if (snapshot.finalPlan) {
      downloadFile(
        'final_plan.json',
        JSON.stringify(snapshot.finalPlan, null, 2),
        'application/json'
      );
    }
    if (snapshot.sessionTrace) {
      downloadFile('session_trace.txt', snapshot.sessionTrace, 'text/plain');
    }
  };

  const plan = snapshot?.finalPlan;
  const state = snapshot?.state;
  const config = snapshot?.config;
  const hc = plan?.headcount || { students: 0, staff: 0, judges: 0, total: 0 };
  const venue = plan?.venue || {};
  const food = plan?.food || {};
  const judging = plan?.judging || {};
  const schedule = plan?.schedule || {};
  const budget = plan?.budget || {};
  const checks: CheckItem[] = plan?.checks || [];
  const rejections: any[] = plan?.rejections || [];
  const excluded: any[] = plan?.excluded_requests || [];
  const recomputedAreas: string[] = plan?.recomputed_areas || [];
  const tokens = plan?.tokens || { last_run: 0, session: 0 };
  const stateMessages: any[] = state?.messages || [];
  const stateFacts: any[] = state?.facts || [];
  const traceHistory: any[] = state?.trace_history || [];

  const cap = Number(budget.cap || 1);
  const spent = Number(budget.total || 0);
  const budgetPct = cap > 0 ? Math.min(100, Math.round((spent / cap) * 100)) : 0;

  // Map validator checks into the 6 official Brief checks
  const findCheck = (id: string) => checks.find((c) => c.id === id);
  const systemChecks = [
    {
      id: 'budget',
      label: 'Budget',
      passed: findCheck('budget')?.passed ?? false,
      explanation:
        findCheck('budget')?.detail ||
        `Total Rs ${spent.toLocaleString()} within cap Rs ${cap.toLocaleString()}`,
    },
    {
      id: 'capacity',
      label: 'Capacity',
      passed: findCheck('venue_fit')?.passed ?? false,
      explanation:
        findCheck('venue_fit')?.detail ||
        `${venue.name || 'Venue'} seats ${venue.capacity || 0} for ${hc.total} attendees`,
    },
    {
      id: 'food',
      label: 'Food',
      passed: (findCheck('floors')?.passed ?? true) && food.status === 'ok',
      explanation: `${food.quantity || 0} meals ordered for ${hc.total} attendees (Rs ${Number(food.cost || 0).toLocaleString()})`,
    },
    {
      id: 'judges',
      label: 'Judges',
      passed: findCheck('judges')?.passed ?? false,
      explanation:
        findCheck('judges')?.detail ||
        `${judging.engaged || 0} judges assigned across ${judging.teams || 0} teams`,
    },
    {
      id: 'schedule',
      label: 'Schedule',
      passed: findCheck('schedule')?.passed ?? false,
      explanation:
        findCheck('schedule')?.detail ||
        `${(schedule.blocks || []).length} blocks totaling ${schedule.duration_minutes || 0} minutes`,
    },
    {
      id: 'rules',
      label: 'Rules',
      passed:
        (findCheck('constraints')?.passed ?? true) &&
        (findCheck('figures')?.passed ?? true) &&
        (findCheck('coverage')?.passed ?? true),
      explanation:
        findCheck('constraints')?.detail || 'All 5 areas covered and figures verified',
    },
  ];
  const passedSystemChecks = systemChecks.filter((c) => c.passed).length;

  // Build unified GitHub-style activity feed from real state (most recent/important first)
  interface ActivityItem {
    id: string;
    status: 'success' | 'rejected' | 'excluded' | 'ignored';
    title: string;
    detail: string;
    rawText?: string;
    sender?: string;
    date?: string;
  }

  const activityFeed: ActivityItem[] = [];

  // 1. Rejections (highest priority for judges)
  [...rejections].reverse().forEach((rej, idx) => {
    activityFeed.push({
      id: `rej-${rej.seq}-${idx}`,
      status: 'rejected',
      title: `${rej.sender} update rejected`,
      detail: `Reason: ${rej.reason.replace('Rejected: ', '')} Plan unchanged.`,
      rawText: rej.text,
      sender: rej.sender,
    });
  });

  // 2. Fact overrides / updates (e.g. printing cost updated, lunch box price updated)
  const resolvedFacts = stateFacts.filter((f) => f.superseded_by !== null);
  [...resolvedFacts].reverse().forEach((oldFact, idx) => {
    const newerFact = stateFacts.find(
      (f) => f.key === oldFact.key && f.seq === oldFact.superseded_by
    );
    if (newerFact) {
      const shortKey = oldFact.key.split('.').pop()?.replace(/_/g, ' ');
      activityFeed.push({
        id: `res-${idx}`,
        status: 'success',
        title: `${newerFact.sender || 'Update'} updated ${shortKey}`,
        detail: `Rs ${Number(oldFact.value || 0).toLocaleString()} → Rs ${Number(newerFact.value || 0).toLocaleString()} (newer message applied)`,
        sender: newerFact.sender,
        date: newerFact.date,
      });
    }
  });

  // 3. Excluded unapproved requests
  excluded.forEach((ex, idx) => {
    activityFeed.push({
      id: `ex-${idx}`,
      status: 'excluded',
      title: `${ex.item} request excluded (Rs ${Number(ex.amount || 0).toLocaleString()})`,
      detail: `Reason: ${ex.reason}`,
    });
  });

  // 4. Applied messages
  [...stateMessages]
    .filter((m) => m.status === 'applied')
    .reverse()
    .forEach((m) => {
      const sender = m.meta?.sender || 'Source';
      const reason = m.meta?.reason || 'Applied to plan';
      activityFeed.push({
        id: `msg-${m.seq}`,
        status: 'success',
        title: `${sender} — ${reason}`,
        detail: `Message #${m.seq} applied`,
        rawText: m.text,
        sender,
        date: m.resolved_date,
      });
    });

  // 5. Ignored messages
  stateMessages
    .filter((m) => m.status === 'ignored')
    .forEach((m) => {
      activityFeed.push({
        id: `ig-${m.seq}`,
        status: 'ignored',
        title: `${m.meta?.sender || 'Message'} note ignored`,
        detail: m.meta?.reason || 'No planning impact',
        rawText: m.text,
        sender: m.meta?.sender,
      });
    });

  // Dynamic Judge Mode plain-English reasoning bullets (strictly derived from state/plan)
  const judgeReasons: string[] = [];
  if (venue.name) {
    const firstRejVenue = (venue.rejected_options || [])[0];
    if (firstRejVenue) {
      judgeReasons.push(
        `Venue selected: ${venue.name} (${venue.capacity} seats, Rs ${Number(venue.price || 0).toLocaleString()}) because ${firstRejVenue.name} (${firstRejVenue.reason}) cannot fit ${hc.total} people.`
      );
    } else {
      judgeReasons.push(
        `Venue selected: ${venue.name} as the lowest-cost venue fitting ${hc.total} people (Rs ${Number(venue.price || 0).toLocaleString()}).`
      );
    }
  }
  if (food.name || food.option) {
    judgeReasons.push(
      `Food kept at ${food.quantity} ${food.name || food.option} boxes (Rs ${Number(food.unit_price || 0).toLocaleString()}/head) to feed all ${hc.total} attendees.`
    );
  }
  if (excluded.length > 0) {
    excluded.forEach((ex) => {
      judgeReasons.push(
        `${ex.item} request (Rs ${Number(ex.amount || 0).toLocaleString()}) ignored because ${ex.reason}.`
      );
    });
  }
  const latestUpdateTrace = [...traceHistory].reverse().find((t) => t.mode === 'update');
  if (latestUpdateTrace && stateFacts.some((f) => f.superseded_by !== null)) {
    const latestAppliedFact = [...stateFacts]
      .reverse()
      .find((f) => f.superseded_by === null && f.key.startsWith('budget.'));
    if (latestAppliedFact) {
      const label = latestAppliedFact.key.split('.').pop()?.replace(/_/g, ' ');
      judgeReasons.push(
        `${label} updated to Rs ${Number(latestAppliedFact.value || 0).toLocaleString()} (only [${recomputedAreas.join(', ') || 'budget'}] recomputed).`
      );
    }
  }
  if (rejections.length > 0) {
    rejections.forEach((rej) => {
      judgeReasons.push(
        `Rejected ${rej.sender} change: ${rej.reason.replace('Rejected: ', '')} (plan kept valid).`
      );
    });
  }

  // Extract latest prompt from trace history
  const latestModelCall =
    traceHistory.length > 0 && traceHistory[traceHistory.length - 1].model_calls?.length > 0
      ? traceHistory[traceHistory.length - 1].model_calls[
          traceHistory[traceHistory.length - 1].model_calls.length - 1
        ]
      : null;

  // Page 1: Clean Home Input View
  if (!loading && (showHomeInput || !plan)) {
    return (
      <div className="min-h-screen bg-[#F8FAFC] text-[#0F172A] flex flex-col">
        <div className="h-1 w-full bg-gradient-to-r from-[#0F172A] via-[#2563EB] to-[#F97316]" />
        <header className="flex items-center justify-between px-8 py-5 bg-white border-b border-slate-200">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#2563EB]" />
            <span className="text-lg font-bold tracking-tight text-[#0F172A] font-display whitespace-nowrap">
              EventOS AI
            </span>
          </div>
          {plan && (
            <button
              onClick={() => setShowHomeInput(false)}
              className="text-sm font-medium text-[#2563EB] hover:text-blue-700 whitespace-nowrap"
            >
              Back to Overview →
            </button>
          )}
        </header>

        <main className="flex-1 flex items-center justify-center p-6">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18 }}
            className="w-full max-w-lg bg-white border border-slate-200 rounded-2xl p-8 md:p-10 shadow-sm space-y-6"
          >
            <div className="text-center space-y-1">
              <h1 className="text-2xl font-bold tracking-tight text-[#0F172A] font-display">
                EventOS AI
              </h1>
              <p className="text-sm text-[#64748B]">AI-Powered Event Planning System</p>
            </div>

            <div className="border-t border-slate-100 pt-6 space-y-4">
              <label className="flex items-center justify-center gap-2.5 w-full py-3.5 px-5 bg-[#F8FAFC] hover:bg-slate-100 border border-slate-200 rounded-xl cursor-pointer transition-colors text-sm font-medium text-[#0F172A]">
                <Upload className="w-4 h-4 text-[#2563EB]" />
                <span>
                  {customText && customFilename !== 'custom_pack.txt'
                    ? `Loaded: ${customFilename}`
                    : 'Upload Message Pack'}
                </span>
                <input
                  type="file"
                  accept=".txt,.md"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>

              <div className="flex items-center gap-3 text-xs text-[#64748B]">
                <div className="flex-1 h-px bg-slate-200" />
                <span>or</span>
                <div className="flex-1 h-px bg-slate-200" />
              </div>

              <textarea
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                rows={4}
                placeholder="Paste new message or pack..."
                className="w-full px-4 py-3 text-sm bg-[#F8FAFC] border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] transition-colors text-[#0F172A] placeholder:text-[#64748B]"
              />
            </div>

            <div className="space-y-3">
              <button
                onClick={handleGeneratePlan}
                disabled={running}
                className="w-full py-3.5 px-6 bg-[#0F172A] hover:bg-slate-800 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-colors flex items-center justify-center gap-2"
              >
                <span>{running ? 'Generating Plan...' : 'Generate Plan'}</span>
                {!running && <ArrowRight className="w-4 h-4 text-[#F97316]" />}
              </button>

              <div className="flex items-center justify-center gap-4 text-xs text-[#64748B] pt-1">
                <button
                  type="button"
                  onClick={() => runPackPath('tests/packs/sample_pack.txt')}
                  disabled={running}
                  className="text-[#2563EB] hover:underline font-medium"
                >
                  Use Sample Pack
                </button>
              </div>
            </div>
          </motion.div>
        </main>
      </div>
    );
  }

  // Screen 3 (Presentation): Judge Mode — pure executive brief + 1-click trace toggle
  if (activeTab === 'judge' && plan) {
    return (
      <div className="min-h-screen bg-[#F8FAFC] text-[#0F172A] flex flex-col justify-center p-6 md:p-10">
        <div className="max-w-3xl w-full mx-auto bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
          <div className="h-1.5 w-full bg-gradient-to-r from-[#0F172A] via-[#2563EB] to-[#F97316]" />
          <div className="p-8 md:p-10 space-y-7">
            {/* Plan Status */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-5">
              <div>
                <div className="text-xs font-medium text-[#64748B]">Event Summary</div>
                <h1 className="text-2xl font-bold tracking-tight text-[#0F172A] font-display mt-0.5">
                  EventOS AI
                </h1>
              </div>
              <div
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-semibold ${
                  plan.valid
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                    : 'bg-orange-50 border-[#F97316]/40 text-orange-800'
                }`}
              >
                {plan.valid ? (
                  <Check className="w-4 h-4 text-emerald-600" />
                ) : (
                  <X className="w-4 h-4 text-[#F97316]" />
                )}
                <span>{plan.valid ? 'VALID' : 'INVALID'}</span>
              </div>
            </div>

            {/* Event Key Facts (Covers all 5 areas + Tokens) */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-5">
              <div>
                <div className="text-xs text-[#64748B]">Event &amp; Venue</div>
                <div className="text-base font-bold text-[#0F172A] mt-0.5">
                  {hc.total} Participants
                </div>
                <div className="text-sm text-[#64748B]">
                  {venue.name} ({venue.capacity} seats)
                </div>
              </div>
              <div>
                <div className="text-xs text-[#64748B]">Budget</div>
                <div className="text-base font-bold font-mono tabular-nums text-[#0F172A] mt-0.5">
                  Rs {spent.toLocaleString()}
                </div>
                <div className="text-xs text-[#2563EB] font-mono">
                  Rs {Number(budget.remaining || 0).toLocaleString()} remaining
                </div>
              </div>
              <div>
                <div className="text-xs text-[#64748B]">Food</div>
                <div className="text-base font-bold text-[#0F172A] mt-0.5">
                  {food.quantity} Lunch Boxes
                </div>
                <div className="text-xs text-[#64748B]">{food.name || food.option}</div>
              </div>
              <div>
                <div className="text-xs text-[#64748B]">Judges</div>
                <div className="text-base font-bold font-mono tabular-nums text-[#0F172A] mt-0.5">
                  {judging.engaged} Assigned
                </div>
                <div className="text-xs text-[#64748B]">{judging.teams} teams total</div>
              </div>
              <div>
                <div className="text-xs text-[#64748B]">Duration</div>
                <div className="text-base font-bold font-mono tabular-nums text-[#0F172A] mt-0.5">
                  {schedule.duration_minutes} min
                </div>
                <div className="text-xs text-[#64748B]">
                  {formatDurationLabel(schedule.duration_minutes || 0)}
                </div>
              </div>
              <div>
                <div className="text-xs text-[#64748B]">Trace &amp; Tokens</div>
                <div className="text-base font-bold font-mono tabular-nums text-[#0F172A] mt-0.5 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#F97316]" />
                  <span>{Number(tokens.last_run || 0).toLocaleString()} Tokens</span>
                </div>
                <div className="text-xs text-[#64748B] font-mono">
                  Session: {Number(tokens.session || 0).toLocaleString()} · 1 call
                </div>
              </div>
            </div>

            {/* AI Decisions (Plain-English Reasoning) */}
            <div className="border-t border-slate-100 pt-6 space-y-2.5">
              <div className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                AI Decisions
              </div>
              <ul className="space-y-2 text-sm text-[#0F172A] leading-relaxed">
                {judgeReasons.map((line, i) => (
                  <li key={i} className="flex items-start gap-2.5">
                    <span className="text-[#2563EB] font-bold mt-0.5">·</span>
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Rejected Updates Callout (Required by Brief when conflicts occur) */}
            {rejections.length > 0 && (
              <div className="border-t border-slate-100 pt-6 space-y-2.5">
                <div className="text-xs font-semibold text-[#F97316] uppercase tracking-wider">
                  Rejected Updates ({rejections.length})
                </div>
                <div className="space-y-2">
                  {rejections.map((rej, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 bg-orange-50/70 border border-[#F97316]/30 rounded-xl text-xs text-[#0F172A] space-y-1"
                    >
                      <div className="font-semibold text-orange-950">
                        ✗ {rej.sender}: &ldquo;{rej.text}&rdquo;
                      </div>
                      <div className="text-orange-800">
                        Reason: {rej.reason.replace('Rejected: ', '')} — Plan kept valid.
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Validation */}
            <div className="border-t border-slate-100 pt-6 space-y-3">
              <div className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                Validation (6 Official Checks)
              </div>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm font-medium">
                {systemChecks.map((chk) => (
                  <span
                    key={chk.id}
                    className={`inline-flex items-center gap-1.5 ${
                      chk.passed ? 'text-[#0F172A]' : 'text-[#F97316]'
                    }`}
                  >
                    {chk.passed ? (
                      <Check className="w-4 h-4 text-[#2563EB]" />
                    ) : (
                      <X className="w-4 h-4 text-[#F97316]" />
                    )}
                    <span>{chk.label}</span>
                  </span>
                ))}
              </div>
            </div>

            {/* Optional Expandable Trace for Judge Walkthrough */}
            {showJudgeTrace && (
              <div className="border-t border-slate-100 pt-5 space-y-2">
                <div className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                  Printed Execution Trace
                </div>
                <pre className="bg-[#0F172A] text-slate-100 p-4 rounded-xl text-xs font-mono overflow-x-auto whitespace-pre-wrap max-h-80 overflow-y-auto">
                  {snapshot?.sessionTrace || snapshot?.lastTrace}
                </pre>
              </div>
            )}

            {/* Bottom Export PDF Action */}
            <div className="border-t border-slate-100 pt-5 flex flex-wrap items-center justify-between gap-4 no-print">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setActiveTab('overview')}
                  className="text-xs font-medium text-[#64748B] hover:text-[#0F172A]"
                >
                  ← Back to Overview
                </button>
                <button
                  onClick={() => setShowJudgeTrace(!showJudgeTrace)}
                  className="text-xs font-medium text-[#2563EB] hover:text-blue-700"
                >
                  {showJudgeTrace ? 'Hide Trace' : 'Show Printed Trace'}
                </button>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleExport}
                  className="px-4 py-2 text-xs font-medium text-[#0F172A] bg-white border border-slate-200 rounded-lg hover:bg-slate-50"
                >
                  Export JSON &amp; Trace
                </button>
                <button
                  onClick={() => window.print()}
                  className="inline-flex items-center gap-2 px-5 py-2.5 text-xs font-semibold text-white bg-[#2563EB] rounded-xl hover:bg-blue-700"
                >
                  <Printer className="w-3.5 h-3.5" />
                  <span>Export PDF</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#0F172A] flex flex-col">
      <div className="h-1 w-full bg-gradient-to-r from-[#0F172A] via-[#2563EB] to-[#F97316] no-print" />
      {/* Top Navigation: Overview | Activity | Judge | Export */}
      <header className="flex items-center justify-between gap-8 px-6 py-3.5 bg-white border-b border-slate-200 no-print">
        <button
          onClick={() => setActiveTab('overview')}
          className="inline-flex items-center gap-2.5 text-lg font-bold tracking-tight text-[#0F172A] font-display whitespace-nowrap shrink-0"
        >
          <span className="w-2.5 h-2.5 rounded-sm bg-[#2563EB]" />
          <span>EventOS AI</span>
        </button>

        <nav className="flex items-center gap-7 text-sm font-medium text-[#64748B]">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-1 border-b-2 transition-colors whitespace-nowrap shrink-0 ${
              activeTab === 'overview'
                ? 'border-[#2563EB] text-[#0F172A] font-semibold'
                : 'border-transparent hover:text-[#0F172A]'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('activity')}
            className={`py-1 border-b-2 transition-colors whitespace-nowrap shrink-0 ${
              activeTab === 'activity'
                ? 'border-[#2563EB] text-[#0F172A] font-semibold'
                : 'border-transparent hover:text-[#0F172A]'
            }`}
          >
            Activity
          </button>
          <button
            onClick={() => setActiveTab('judge')}
            className={`py-1 border-b-2 transition-colors whitespace-nowrap shrink-0 ${
              activeTab === 'judge'
                ? 'border-[#2563EB] text-[#0F172A] font-semibold'
                : 'border-transparent hover:text-[#0F172A]'
            }`}
          >
            Judge
          </button>
        </nav>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={handleExport}
            disabled={!plan}
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-[#0F172A] rounded-lg hover:bg-slate-800 disabled:opacity-40 transition-colors whitespace-nowrap shrink-0"
          >
            <Download className="w-3.5 h-3.5 text-[#F97316]" />
            <span>Export</span>
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-8 space-y-6">
        {loading && !plan ? (
          <div className="bg-white border border-slate-200 rounded-2xl p-10 text-center text-sm text-[#64748B]">
            Loading plan...
          </div>
        ) : activeTab === 'overview' && plan ? (
          <>
            {/* Overview Action Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs text-[#64748B] flex items-center gap-2">
                <span>Mind to Machine Hackathon · Plan v{plan.version}</span>
                <span>·</span>
                <span className="inline-flex items-center gap-1.5 font-mono text-[#0F172A] font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#F97316]" />
                  {Number(tokens.last_run || 0).toLocaleString()} run tokens
                </span>
                <span>({Number(tokens.session || 0).toLocaleString()} session)</span>
              </div>
              <div className="flex items-center gap-2.5">
                <button
                  onClick={() => setDetailModal('new_input')}
                  disabled={running}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-[#2563EB] rounded-lg hover:bg-blue-700 disabled:opacity-50 whitespace-nowrap"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Message</span>
                </button>
                <button
                  onClick={handleReset}
                  disabled={running}
                  className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-[#0F172A] bg-white border border-slate-200 rounded-lg hover:bg-slate-50 whitespace-nowrap"
                >
                  <RotateCcw className="w-3.5 h-3.5 text-[#64748B]" />
                  <span>Reset</span>
                </button>
              </div>
            </div>

            {/* 4 Big Summary Cards */}
            <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* 1. Plan Ready */}
              <div className="bg-white border border-slate-200 rounded-2xl p-5 flex flex-col justify-between">
                <div className="flex items-center gap-1.5 text-xs font-bold tracking-wide">
                  {plan.valid ? (
                    <Check className="w-4 h-4 text-[#2563EB]" />
                  ) : (
                    <X className="w-4 h-4 text-[#F97316]" />
                  )}
                  <span className={plan.valid ? 'text-[#2563EB]' : 'text-[#F97316]'}>
                    {plan.valid ? 'PLAN READY' : 'PLAN INVALID'}
                  </span>
                </div>
                <div className="mt-3">
                  <div className="text-2xl font-bold text-[#0F172A] font-display tabular-nums">
                    {hc.total} People
                  </div>
                  <div className="text-sm text-[#64748B] mt-0.5">{venue.name || 'No Venue'}</div>
                </div>
              </div>

              {/* 2. Budget */}
              <div className="bg-white border border-slate-200 rounded-2xl p-5 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs font-semibold text-[#64748B]">
                  <span>Budget</span>
                  <span className="font-mono text-[#0F172A]">{budgetPct}%</span>
                </div>
                <div className="mt-3">
                  <div className="text-2xl font-bold text-[#0F172A] font-mono tabular-nums">
                    Rs {spent.toLocaleString()}
                  </div>
                  <div className="text-sm text-[#2563EB] font-mono tabular-nums mt-0.5">
                    Rs {Number(budget.remaining || 0).toLocaleString()} Left
                  </div>
                </div>
              </div>

              {/* 3. Schedule */}
              <div className="bg-white border border-slate-200 rounded-2xl p-5 flex flex-col justify-between">
                <div className="text-xs font-semibold text-[#64748B]">Schedule</div>
                <div className="mt-3">
                  <div className="text-2xl font-bold text-[#0F172A] font-display">
                    {formatDurationLabel(schedule.duration_minutes || 0)}
                  </div>
                  <div className="text-sm text-[#64748B] mt-0.5">
                    {(schedule.blocks || []).length} Timed Sessions
                  </div>
                </div>
              </div>

              {/* 4. Status */}
              <div className="bg-white border border-slate-200 rounded-2xl p-5 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs font-semibold text-[#64748B]">
                  <span>Status</span>
                  <span className="font-mono text-[#F97316] font-semibold">
                    {Number(tokens.last_run || 0).toLocaleString()} tok
                  </span>
                </div>
                <div className="mt-3">
                  <div className="text-2xl font-bold text-[#0F172A] font-mono tabular-nums">
                    {passedSystemChecks}/6
                  </div>
                  <div className="text-sm text-[#64748B] mt-0.5">Checks Passed</div>
                </div>
              </div>
            </section>

            {/* AI Decisions (All 5 required Brief areas as 1-line rows with View Details) */}
            <section className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h2 className="text-sm font-bold text-[#0F172A] font-display">AI Selected</h2>
                <span className="text-xs text-[#64748B]">5 Required Areas</span>
              </div>
              <div className="divide-y divide-slate-100">
                {/* 1. Venue */}
                <div className="py-3 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 text-sm">
                    <Check className="w-4 h-4 text-[#2563EB] shrink-0" />
                    <span className="font-semibold text-[#0F172A]">{venue.name || 'Venue'}</span>
                    <span className="text-[#64748B]">
                      {venue.capacity} seats · Rs {Number(venue.price || 0).toLocaleString()}
                    </span>
                  </div>
                  <button
                    onClick={() => setDetailModal('venue')}
                    className="inline-flex items-center gap-1 text-xs font-medium text-[#2563EB] hover:text-blue-700 shrink-0"
                  >
                    <span>View Details</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* 2. Food */}
                <div className="py-3 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 text-sm">
                    <Check className="w-4 h-4 text-[#2563EB] shrink-0" />
                    <span className="font-semibold text-[#0F172A]">
                      {food.name || food.option || 'Meal Plan'}
                    </span>
                    <span className="text-[#64748B]">
                      {food.quantity} meals · Rs {Number(food.cost || 0).toLocaleString()}
                    </span>
                  </div>
                  <button
                    onClick={() => setDetailModal('food')}
                    className="inline-flex items-center gap-1 text-xs font-medium text-[#2563EB] hover:text-blue-700 shrink-0"
                  >
                    <span>View Details</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* 3. Judging */}
                <div className="py-3 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 text-sm">
                    <Check className="w-4 h-4 text-[#2563EB] shrink-0" />
                    <span className="font-semibold text-[#0F172A]">
                      {judging.engaged} Judges
                    </span>
                    <span className="text-[#64748B]">
                      {judging.teams} teams · Rs{' '}
                      {Number(judging.honorarium_total || 0).toLocaleString()}
                    </span>
                  </div>
                  <button
                    onClick={() => setDetailModal('judging')}
                    className="inline-flex items-center gap-1 text-xs font-medium text-[#2563EB] hover:text-blue-700 shrink-0"
                  >
                    <span>View Details</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* 4. Schedule */}
                <div className="py-3 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 text-sm">
                    <Check className="w-4 h-4 text-[#2563EB] shrink-0" />
                    <span className="font-semibold text-[#0F172A]">
                      {schedule.duration_minutes} Minute Schedule
                    </span>
                    <span className="text-[#64748B]">
                      {(schedule.blocks || [])
                        .map((b: any) => b.name.replace(' Break', ''))
                        .join(' · ')}
                    </span>
                  </div>
                  <button
                    onClick={() => setDetailModal('schedule')}
                    className="inline-flex items-center gap-1 text-xs font-medium text-[#2563EB] hover:text-blue-700 shrink-0"
                  >
                    <span>View Details</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* 5. Budget */}
                <div className="py-3 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 text-sm">
                    <Check className="w-4 h-4 text-[#2563EB] shrink-0" />
                    <span className="font-semibold text-[#0F172A]">
                      Rs {spent.toLocaleString()} Total Budget
                    </span>
                    <span className="text-[#64748B]">
                      Rs {Number(budget.remaining || 0).toLocaleString()} left of Rs{' '}
                      {cap.toLocaleString()}
                    </span>
                  </div>
                  <button
                    onClick={() => setDetailModal('budget')}
                    className="inline-flex items-center gap-1 text-xs font-medium text-[#2563EB] hover:text-blue-700 shrink-0"
                  >
                    <span>View Details</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </section>

            {/* Latest Activity + System Checks (2 clean columns) */}
            <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Latest Activity (GitHub-style feed) */}
              <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <h2 className="text-sm font-bold text-[#0F172A] font-display">Latest Activity</h2>
                  <button
                    onClick={() => {
                      setActivitySubView('feed');
                      setActiveTab('activity');
                    }}
                    className="text-xs font-semibold text-[#2563EB] hover:text-blue-700"
                  >
                    View All &amp; Trace →
                  </button>
                </div>

                <div className="space-y-3">
                  {activityFeed.slice(0, 4).map((item) => (
                    <div
                      key={item.id}
                      onClick={() =>
                        setExpandedActivityKey(
                          expandedActivityKey === item.id ? null : item.id
                        )
                      }
                      className="flex items-start gap-3 text-sm cursor-pointer hover:bg-[#F8FAFC] p-2 -mx-2 rounded-xl transition-colors"
                    >
                      {item.status === 'rejected' ? (
                        <X className="w-4 h-4 text-[#F97316] mt-0.5 shrink-0" />
                      ) : (
                        <Check
                          className={`w-4 h-4 mt-0.5 shrink-0 ${
                            item.status === 'success' ? 'text-[#2563EB]' : 'text-[#F97316]'
                          }`}
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <div
                          className={`font-medium ${
                            item.status === 'rejected' ? 'text-[#F97316]' : 'text-[#0F172A]'
                          }`}
                        >
                          {item.title}
                        </div>
                        <div className="text-xs text-[#64748B] mt-0.5">{item.detail}</div>
                        {expandedActivityKey === item.id && item.rawText && (
                          <div className="mt-2 p-2.5 bg-slate-100 rounded-lg text-xs text-[#0F172A] italic">
                            &ldquo;{item.rawText}&rdquo;
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* System Checks (6 clean checks, click to inspect explanation) */}
              <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <h2 className="text-sm font-bold text-[#0F172A] font-display">System Checks</h2>
                  <span className="text-xs text-[#64748B]">Click any check</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                  {systemChecks.map((chk) => (
                    <button
                      key={chk.id}
                      onClick={() =>
                        setSelectedCheckId(selectedCheckId === chk.id ? null : chk.id)
                      }
                      className={`flex items-center gap-2 px-3.5 py-2.5 rounded-xl border text-sm font-medium transition-colors text-left ${
                        selectedCheckId === chk.id
                          ? 'border-[#2563EB] bg-blue-50 text-[#0F172A]'
                          : 'border-slate-200 bg-[#F8FAFC] hover:bg-slate-100 text-[#0F172A]'
                      }`}
                    >
                      {chk.passed ? (
                        <Check className="w-4 h-4 text-[#2563EB] shrink-0" />
                      ) : (
                        <X className="w-4 h-4 text-[#F97316] shrink-0" />
                      )}
                      <span>{chk.label}</span>
                    </button>
                  ))}
                </div>

                {selectedCheckId && (
                  <div className="p-3.5 bg-[#F8FAFC] border border-slate-200 rounded-xl text-xs text-[#64748B]">
                    <span className="font-semibold text-[#0F172A]">
                      {systemChecks.find((c) => c.id === selectedCheckId)?.label}:{' '}
                    </span>
                    {systemChecks.find((c) => c.id === selectedCheckId)?.explanation}
                  </div>
                )}

                {/* Quick Demo Controls for Incremental Test */}
                <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs text-[#64748B]">Test practice messages:</span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => runPackPath('tests/packs/practice_change.txt')}
                      disabled={running}
                      className="px-2.5 py-1 text-xs font-medium text-[#0F172A] bg-slate-100 hover:bg-blue-50 hover:text-[#2563EB] rounded-lg disabled:opacity-50 transition-colors"
                    >
                      + Valid Change
                    </button>
                    <button
                      onClick={() => runPackPath('tests/packs/practice_wrong.txt')}
                      disabled={running}
                      className="px-2.5 py-1 text-xs font-medium text-[#F97316] bg-orange-50 hover:bg-orange-100 border border-[#F97316]/25 rounded-lg disabled:opacity-50 transition-colors"
                    >
                      + Wrong Message
                    </button>
                  </div>
                </div>
              </div>
            </section>
          </>
        ) : activeTab === 'activity' ? (
          /* Screen 2: Activity (Updates & Rejections | Execution Trace | Prediction Slip) */
          <div className="space-y-5">
            <div className="bg-white border border-slate-200 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setActivitySubView('feed')}
                  className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                    activitySubView === 'feed'
                      ? 'bg-[#0F172A] text-white'
                      : 'bg-slate-100 text-[#64748B] hover:text-[#0F172A]'
                  }`}
                >
                  Updates &amp; Rejections
                </button>
                <button
                  onClick={() => setActivitySubView('trace')}
                  className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                    activitySubView === 'trace'
                      ? 'bg-[#0F172A] text-white'
                      : 'bg-slate-100 text-[#64748B] hover:text-[#0F172A]'
                  }`}
                >
                  Execution Trace
                </button>
                <button
                  onClick={() => setActivitySubView('slip')}
                  className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                    activitySubView === 'slip'
                      ? 'bg-[#0F172A] text-white'
                      : 'bg-slate-100 text-[#64748B] hover:text-[#0F172A]'
                  }`}
                >
                  Prediction Slip
                </button>
              </div>
              <button
                onClick={() => setDetailModal('new_input')}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-[#2563EB] rounded-lg hover:bg-blue-700"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Message</span>
              </button>
            </div>

            {activitySubView === 'feed' && (
              <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4">
                <div className="border-b border-slate-100 pb-3 flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-bold text-[#0F172A] font-display">
                      Activity &amp; Rejected Messages
                    </h2>
                    <p className="text-xs text-[#64748B] mt-0.5">
                      Last run recomputed:{' '}
                      <span className="font-mono font-semibold text-[#0F172A]">
                        {recomputedAreas.length > 0 ? recomputedAreas.join(', ') : 'none (rejected)'}
                      </span>
                    </p>
                  </div>
                </div>

                <div className="divide-y divide-slate-100">
                  {activityFeed.map((item) => (
                    <div key={item.id} className="py-3.5 flex items-start gap-3.5">
                      {item.status === 'rejected' ? (
                        <div className="w-6 h-6 rounded-full bg-orange-50 border border-[#F97316]/30 flex items-center justify-center shrink-0 mt-0.5">
                          <X className="w-3.5 h-3.5 text-[#F97316]" />
                        </div>
                      ) : item.status === 'success' ? (
                        <div className="w-6 h-6 rounded-full bg-blue-50 border border-[#2563EB]/30 flex items-center justify-center shrink-0 mt-0.5">
                          <Check className="w-3.5 h-3.5 text-[#2563EB]" />
                        </div>
                      ) : (
                        <div className="w-6 h-6 rounded-full bg-orange-50 border border-[#F97316]/30 flex items-center justify-center shrink-0 mt-0.5">
                          <span className="text-xs font-bold text-[#F97316]">–</span>
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span
                            className={`text-sm font-semibold ${
                              item.status === 'rejected' ? 'text-[#F97316]' : 'text-[#0F172A]'
                            }`}
                          >
                            {item.title}
                          </span>
                          {item.date && (
                            <span className="text-xs font-mono text-[#64748B]">{item.date}</span>
                          )}
                        </div>
                        <div className="text-xs text-[#64748B] mt-0.5">{item.detail}</div>
                        {item.rawText && (
                          <div className="mt-2 p-2.5 bg-[#F8FAFC] border border-slate-200 rounded-lg text-xs text-[#64748B] italic">
                            &ldquo;{item.rawText}&rdquo;
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activitySubView === 'trace' && (
              <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
                  <div>
                    <h2 className="text-base font-bold text-[#0F172A] font-display">
                      Printed Execution Trace
                    </h2>
                    <p className="text-xs text-[#64748B] mt-0.5">
                      Run: <span className="font-mono font-semibold text-[#F97316]">{Number(tokens.last_run || 0).toLocaleString()}</span> · Session total:{' '}
                      <span className="font-mono font-semibold text-[#0F172A]">{Number(tokens.session || 0).toLocaleString()}</span> tokens
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      downloadFile(
                        'session_trace.txt',
                        snapshot?.sessionTrace || '',
                        'text/plain'
                      )
                    }
                    className="px-3 py-1.5 text-xs font-medium text-[#0F172A] border border-slate-200 rounded-lg hover:bg-slate-50"
                  >
                    Download Trace
                  </button>
                </div>
                <pre className="bg-[#0F172A] text-slate-100 p-4 rounded-xl text-xs font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-[600px] overflow-y-auto">
                  {snapshot?.sessionTrace || snapshot?.lastTrace || 'No trace recorded yet.'}
                </pre>
              </div>
            )}

            {activitySubView === 'slip' && (
              <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4">
                <div>
                  <h2 className="text-base font-bold text-[#0F172A] font-display">
                    Volunteer Prediction Slip Helper
                  </h2>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    Select the type of incoming message to see which areas make model calls vs
                    Python recomputation.
                  </p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    {ROUTER_PREVIEW_RULES.map((rule, idx) => (
                      <button
                        key={idx}
                        onClick={() => setSelectedRuleIdx(idx)}
                        className={`w-full text-left p-3 rounded-xl border text-xs transition-colors ${
                          selectedRuleIdx === idx
                            ? 'border-[#2563EB] bg-blue-50 text-[#0F172A]'
                            : 'border-slate-200 bg-[#F8FAFC] text-[#0F172A] hover:bg-slate-100'
                        }`}
                      >
                        <div className="font-mono font-semibold">{rule.keyPattern}</div>
                        <div className="text-[#64748B] mt-0.5">{rule.example}</div>
                      </button>
                    ))}
                  </div>
                  <div className="bg-[#F8FAFC] border border-slate-200 rounded-xl p-5 flex flex-col justify-center space-y-3">
                    <div className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                      Write on Volunteer Slip:
                    </div>
                    <div className="bg-white border border-slate-200 rounded-xl p-4 font-mono text-sm text-[#0F172A] space-y-2">
                      <div>
                        Model calls: <strong className="text-[#2563EB]">reading</strong> (1 call)
                      </div>
                      <div>
                        Affected areas (Python-only):{' '}
                        <strong className="text-[#F97316]">{ROUTER_PREVIEW_RULES[selectedRuleIdx].areas.join(', ')}</strong>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : activeTab === 'developer' ? (
          /* Hidden Developer Mode: Trace, Prompt, JSON, Router, Config, HTML Report */
          <div className="space-y-5">
            <div className="bg-white border border-slate-200 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-1.5">
                {(
                  [
                    ['trace', 'Execution Trace'],
                    ['prompt', 'Prompt'],
                    ['json', 'JSON'],
                    ['router', 'Router'],
                    ['config', 'Config'],
                    ['report', 'HTML Report'],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setDevSection(key)}
                    className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                      devSection === key
                        ? 'bg-[#0F172A] text-white'
                        : 'bg-slate-100 text-[#64748B] hover:text-[#0F172A]'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setActiveTab('overview')}
                className="text-xs font-medium text-[#64748B] hover:text-[#0F172A]"
              >
                Exit Developer Mode
              </button>
            </div>

            {devSection === 'trace' && (
              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-bold text-[#0F172A]">
                    <Terminal className="w-4 h-4 text-[#2563EB]" />
                    <span>Execution Trace (out/session_trace.txt)</span>
                  </div>
                  <button
                    onClick={() =>
                      downloadFile(
                        'session_trace.txt',
                        snapshot?.sessionTrace || '',
                        'text/plain'
                      )
                    }
                    className="px-3 py-1.5 text-xs font-medium text-[#0F172A] border border-slate-200 rounded-lg hover:bg-slate-50"
                  >
                    Download Trace
                  </button>
                </div>
                <pre className="bg-[#0F172A] text-slate-100 p-4 rounded-xl text-xs font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-[600px] overflow-y-auto">
                  {snapshot?.sessionTrace || snapshot?.lastTrace || 'No trace recorded yet.'}
                </pre>
              </div>
            )}

            {devSection === 'prompt' && (
              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                <div className="text-sm font-bold text-[#0F172A]">
                  Latest Extractor Prompt &amp; Raw Model Output
                </div>
                {latestModelCall ? (
                  <div className="space-y-3 text-xs font-mono">
                    <div className="text-[#64748B]">
                      Model: {latestModelCall.model} · Area: {latestModelCall.area} · Tokens:{' '}
                      <span className="text-[#F97316] font-semibold">{latestModelCall.total_tokens}</span>
                    </div>
                    <pre className="bg-[#0F172A] text-slate-100 p-4 rounded-xl overflow-x-auto whitespace-pre-wrap max-h-80 overflow-y-auto">
                      {latestModelCall.input}
                    </pre>
                    <div className="font-sans text-xs font-semibold text-[#0F172A]">
                      Raw Output:
                    </div>
                    <pre className="bg-[#0F172A] text-blue-200 p-4 rounded-xl overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
                      {latestModelCall.output}
                    </pre>
                  </div>
                ) : (
                  <div className="text-xs text-[#64748B]">No model call recorded yet.</div>
                )}
              </div>
            )}

            {devSection === 'json' && (
              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-bold text-[#0F172A]">out/final_plan.json</div>
                  <button
                    onClick={() =>
                      downloadFile(
                        'final_plan.json',
                        JSON.stringify(plan || {}, null, 2),
                        'application/json'
                      )
                    }
                    className="px-3 py-1.5 text-xs font-medium text-[#0F172A] border border-slate-200 rounded-lg hover:bg-slate-50"
                  >
                    Download JSON
                  </button>
                </div>
                <pre className="bg-[#0F172A] text-slate-100 p-4 rounded-xl text-xs font-mono overflow-x-auto max-h-[600px] overflow-y-auto">
                  {JSON.stringify(plan || {}, null, 2)}
                </pre>
              </div>
            )}

            {devSection === 'router' && (
              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                <div className="text-sm font-bold text-slate-900">
                  Router Dependency Table &amp; Prediction Slip
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    {ROUTER_PREVIEW_RULES.map((rule, idx) => (
                      <button
                        key={idx}
                        onClick={() => setSelectedRuleIdx(idx)}
                        className={`w-full text-left p-2.5 rounded-xl border text-xs transition-colors ${
                          selectedRuleIdx === idx
                            ? 'border-blue-600 bg-blue-50 text-slate-900'
                            : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
                        }`}
                      >
                        <div className="font-mono font-semibold">{rule.keyPattern}</div>
                        <div className="text-slate-500 mt-0.5">{rule.example}</div>
                      </button>
                    ))}
                  </div>
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex flex-col justify-center">
                    <div className="text-xs font-semibold text-slate-500 mb-2">
                      Volunteer Prediction Slip:
                    </div>
                    <div className="bg-white border border-slate-200 rounded-lg p-3.5 font-mono text-sm text-slate-900">
                      Model calls will be: <strong>reading</strong> (1 call).
                      <br />
                      Python-only recompute:{' '}
                      <strong>{ROUTER_PREVIEW_RULES[selectedRuleIdx].areas.join(', ')}</strong>.
                    </div>
                  </div>
                </div>
              </div>
            )}

            {devSection === 'config' && (
              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                <div className="flex items-center gap-2 text-sm font-bold text-[#0F172A]">
                  <Sliders className="w-4 h-4 text-[#2563EB]" />
                  <span>Model &amp; Policy Config (config.json)</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-[#64748B] mb-1">
                      Provider
                    </label>
                    <select
                      defaultValue={config?.llm?.provider || 'gemini'}
                      id="cfg-provider"
                      className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-white font-mono text-[#0F172A]"
                    >
                      <option value="gemini">gemini</option>
                      <option value="ollama">ollama</option>
                      <option value="openai_compatible">openai_compatible</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[#64748B] mb-1">
                      Model Name
                    </label>
                    <input
                      type="text"
                      defaultValue={config?.llm?.model || 'gemini-3.1-flash-lite'}
                      id="cfg-model"
                      className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-white font-mono text-[#0F172A]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[#64748B] mb-1">
                      Judges Policy
                    </label>
                    <select
                      defaultValue={config?.policy?.judges_engaged || 'minimum_required'}
                      id="cfg-judges"
                      className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-white font-mono text-[#0F172A]"
                    >
                      <option value="minimum_required">minimum_required</option>
                      <option value="all_confirmed">all_confirmed</option>
                    </select>
                  </div>
                </div>
                <button
                  onClick={() => {
                    const prov = (
                      document.getElementById('cfg-provider') as HTMLSelectElement
                    ).value;
                    const mod = (document.getElementById('cfg-model') as HTMLInputElement).value;
                    const jpol = (
                      document.getElementById('cfg-judges') as HTMLSelectElement
                    ).value;
                    handleUpdateConfig(prov, mod, jpol);
                  }}
                  className="px-4 py-2 text-xs font-semibold bg-[#2563EB] text-white rounded-lg hover:bg-blue-700"
                >
                  Save Configuration
                </button>
              </div>
            )}

            {devSection === 'report' && (
              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-bold text-[#0F172A]">
                    <FileText className="w-4 h-4 text-[#2563EB]" />
                    <span>Static HTML Report (out/report.html)</span>
                  </div>
                  <button
                    onClick={() =>
                      downloadFile('report.html', snapshot?.reportHtml || '', 'text/html')
                    }
                    className="px-3 py-1.5 text-xs font-medium text-[#0F172A] border border-slate-200 rounded-lg hover:bg-slate-50"
                  >
                    Download report.html
                  </button>
                </div>
                <iframe
                  title="EventOS Static Report"
                  srcDoc={snapshot?.reportHtml || '<p>No report generated yet.</p>'}
                  className="w-full h-[600px] border border-slate-200 rounded-xl bg-white"
                />
              </div>
            )}
          </div>
        ) : null}
      </main>

      {/* Quiet Footer with Hidden Developer Mode Entry */}
      <footer className="max-w-5xl w-full mx-auto px-6 py-5 flex items-center justify-between text-xs text-[#64748B] no-print">
        <span>EventOS AI</span>
        <button
          onClick={() => setActiveTab(activeTab === 'developer' ? 'overview' : 'developer')}
          className="inline-flex items-center gap-1.5 text-[#64748B] hover:text-[#0F172A] transition-colors"
        >
          <Code2 className="w-3.5 h-3.5" />
          <span>{activeTab === 'developer' ? 'Exit Developer Mode' : 'Developer Mode'}</span>
        </button>
      </footer>

      {/* Level 2 Progressive Disclosure Modal */}
      <AnimatePresence>
        {detailModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => setDetailModal(null)}
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-[1px] z-50 flex items-center justify-center p-4 no-print"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.15 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white border border-slate-200 rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 shadow-xl space-y-5"
            >
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-base font-bold text-slate-900 font-display capitalize">
                  {detailModal === 'new_input'
                    ? 'Add Message or Pack'
                    : `${detailModal} Details`}
                </h3>
                <button
                  onClick={() => setDetailModal(null)}
                  className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {detailModal === 'venue' && plan && (
                <div className="space-y-4 text-sm">
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
                    <div className="font-bold text-slate-900">{venue.name}</div>
                    <div className="text-xs font-mono text-slate-600 mt-1">
                      Capacity: {venue.capacity} seats · Attendees: {hc.total} · Slack: +
                      {venue.slack} seats · Rs {Number(venue.price || 0).toLocaleString()}
                    </div>
                  </div>
                  {(venue.rejected_options || []).length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-slate-700">
                        Why other venues were skipped:
                      </div>
                      {venue.rejected_options.map((r: any, i: number) => (
                        <div
                          key={i}
                          className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono text-slate-700"
                        >
                          <strong>{r.name}</strong> ({r.capacity ?? 'N/A'} seats) — {r.reason}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {detailModal === 'food' && plan && (
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-1.5 text-sm">
                  <div className="font-bold text-slate-900">{food.name || food.option}</div>
                  <div className="text-xs font-mono text-slate-600">
                    {food.quantity} meals &times; Rs {Number(food.unit_price || 0).toLocaleString()}{' '}
                    + Rs {Number(food.delivery_fee || 0).toLocaleString()} delivery = Rs{' '}
                    {Number(food.cost || 0).toLocaleString()}
                  </div>
                </div>
              )}

              {detailModal === 'budget' && plan && (
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-xs text-[#64748B] mb-1.5 font-mono">
                      <span>Spent: Rs {spent.toLocaleString()}</span>
                      <span>Cap: Rs {cap.toLocaleString()}</span>
                    </div>
                    <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${budgetPct}%`,
                          backgroundColor: budgetPct > 90 ? '#F97316' : '#2563EB',
                        }}
                      />
                    </div>
                  </div>
                  <table className="w-full text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 text-slate-500">
                        <th className="py-2 text-left font-semibold">Item</th>
                        <th className="py-2 text-left font-semibold">Source</th>
                        <th className="py-2 text-right font-semibold font-mono">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {(budget.items || []).map((item: any, idx: number) => (
                        <tr key={idx}>
                          <td className="py-2 text-slate-800">{item.label}</td>
                          <td className="py-2 text-slate-500 font-mono">
                            Msg #{item.source_message}
                          </td>
                          <td className="py-2 text-right font-mono tabular-nums text-slate-900">
                            Rs {Number(item.amount || 0).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {detailModal === 'schedule' && plan && (
                <div className="space-y-2">
                  {(schedule.blocks || []).map((b: any, idx: number) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                    >
                      <span className="font-semibold text-slate-900">{b.name}</span>
                      <span className="font-mono text-slate-600 tabular-nums">
                        {b.minutes} min ({b.start}–{b.end}m)
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {detailModal === 'judging' && plan && (
                <div className="space-y-4">
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 text-xs font-mono text-slate-700">
                    {judging.engaged} engaged of {judging.confirmed} confirmed · {judging.teams}{' '}
                    teams · {judging.window_minutes} min window · Rs{' '}
                    {Number(judging.honorarium_total || 0).toLocaleString()}
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs font-mono">
                    {(judging.assignments || []).map((a: any) => (
                      <div
                        key={a.judge}
                        className="p-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-700"
                      >
                        Judge {a.judge}: T{(a.teams || []).join(', T')}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {detailModal === 'new_input' && (
                <div className="space-y-4">
                  <label className="flex items-center justify-center gap-2 w-full py-3 px-4 bg-[#F8FAFC] hover:bg-slate-100 border border-slate-200 rounded-xl cursor-pointer text-xs font-medium text-[#0F172A]">
                    <Upload className="w-4 h-4 text-[#2563EB]" />
                    <span>
                      {customText && customFilename !== 'custom_pack.txt'
                        ? `Loaded: ${customFilename}`
                        : 'Upload Message File (.txt)'}
                    </span>
                    <input
                      type="file"
                      accept=".txt,.md"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                  </label>
                  <textarea
                    value={customText}
                    onChange={(e) => setCustomText(e.target.value)}
                    rows={4}
                    placeholder="Paste a new message or pack..."
                    className="w-full px-3.5 py-2.5 text-sm bg-[#F8FAFC] border border-slate-200 rounded-xl focus:outline-none focus:border-[#2563EB] text-[#0F172A] placeholder:text-[#64748B]"
                  />
                  <div className="flex items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => runPackPath('tests/packs/unseen_pack.txt')}
                      disabled={running}
                      className="px-3 py-1.5 text-xs bg-slate-100 hover:bg-slate-200 rounded-lg text-[#0F172A]"
                    >
                      Run Unseen Pack
                    </button>
                    <button
                      onClick={handleGeneratePlan}
                      disabled={running || !customText.trim()}
                      className="px-5 py-2 text-xs font-semibold text-white bg-[#2563EB] hover:bg-blue-700 disabled:opacity-40 rounded-lg"
                    >
                      {running ? 'Running...' : 'Run Update'}
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
