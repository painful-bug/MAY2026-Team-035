import { projectTracker } from './trackerProjection';

export function ComplaintTracker({ events = [] }) {
  const { nodes, annotations } = projectTracker(events);
  return (
    <section aria-label="Complaint progress" className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
      <h3 className="text-sm font-extrabold text-slate-800">Progress</h3>
      <ol className="mt-4 flex flex-col gap-3 md:flex-row md:items-start md:gap-0">
        {nodes.map((node, index) => (
          <li key={node.key} className="flex min-w-0 flex-1 items-start gap-2 md:block">
            <span className={`inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${node.state === 'done' ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-500'}`}>{index + 1}</span>
            <div className="min-w-0 md:mt-2">
              <p className="text-[11px] font-bold text-slate-700">{node.label}</p>
              {node.detail && <p className="text-[10px] text-slate-500">{node.detail}</p>}
              {node.unrated && <p className="text-[10px] text-slate-500">Closed without a rating</p>}
              {annotations.filter((item) => item.afterNode === node.key).map((item) => <p key={`${item.label}-${item.at}`} className="mt-1 text-[10px] font-semibold text-amber-700">{item.label}</p>)}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
