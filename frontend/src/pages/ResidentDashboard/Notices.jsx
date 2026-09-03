import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Calendar, Megaphone } from 'lucide-react';
import { residentApi } from '../../features/resident/residentApi';
import { QUERY_POLICIES } from '../../lib/api/queryClient';

// Wired to `GET /api/v1/notices` (`docs/API.md` §14,
// `backend/app/api/v1/routers/resident_home.py`).
//
// **Shape change from the demo.** The mock's `urgency` was `High` / `Medium` /
// `Low`; the API's is `Info` | `Important` | `Urgent`, title-cased on the wire
// to match what this screen renders. The mock's `description` is the API's
// `body`; the mock's `date` + `timeAgo` is the API's single `publishedAt`.
// Drafts (no `publishedAt`) never reach this list — the API excludes them, so
// there is nothing to filter here.
const URGENCY_STYLES = {
  Urgent: { border: 'border-l-rose-500', badge: 'bg-rose-50 text-rose-700 border border-rose-100' },
  Important: { border: 'border-l-amber-500', badge: 'bg-amber-50 text-amber-700 border border-amber-100' },
  Info: { border: 'border-l-blue-500', badge: 'bg-blue-50 text-blue-700 border border-blue-100' },
};

const formatPublished = (iso) => {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
};

export default function Notices() {
  const noticesQuery = useQuery({
    queryKey: ['resident', 'notices'],
    queryFn: () => residentApi.notices(),
    ...QUERY_POLICIES.list,
  });

  const notices = noticesQuery.data?.items || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Society Notice Board</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Official circulars, facility maintenance updates, and celebration plans.</p>
      </div>

      {noticesQuery.isLoading ? (
        <div className="bg-white p-12 text-center text-xs text-slate-400 font-semibold border border-slate-100 rounded-2xl">
          Loading notices…
        </div>
      ) : noticesQuery.error ? (
        <div role="alert" className="bg-white p-6 text-center text-xs text-rose-600 font-semibold border border-rose-100 rounded-2xl">
          {noticesQuery.error.message || 'Could not load notices.'}
        </div>
      ) : notices.length === 0 ? (
        <div className="bg-white p-12 text-center text-xs text-slate-400 font-semibold border border-slate-100 rounded-2xl flex flex-col items-center gap-2">
          <Megaphone className="h-6 w-6 text-slate-300" />
          No notices have been published yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {notices.map((notice) => {
            const style = URGENCY_STYLES[notice.urgency] || URGENCY_STYLES.Info;

            return (
              <div
                key={notice.id}
                className={`bg-white border rounded-2xl p-6 shadow-sm flex flex-col justify-between gap-4 transition-all hover:shadow-md border-l-4 ${style.border}`}
              >
                <div className="space-y-3">
                  <div className="flex justify-between items-start gap-4">
                    <div className="space-y-0.5">
                      <span className="text-[9px] font-extrabold px-2 py-0.5 bg-slate-50 border border-slate-100 rounded text-slate-400 uppercase tracking-wider">
                        {notice.category}
                      </span>
                      <h3 className="text-base font-extrabold text-slate-805 pt-1.5 leading-tight">{notice.title}</h3>
                    </div>
                    <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full ${style.badge}`}>
                      {notice.urgency}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed font-semibold whitespace-pre-line">{notice.body}</p>
                </div>

                <div className="pt-3 border-t border-slate-50 flex items-center gap-1.5 text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  <span>
                    Posted: {formatPublished(notice.publishedAt)}
                    {notice.authorName ? ` · ${notice.authorName}` : ''}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
