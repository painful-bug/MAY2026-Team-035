import React, { useMemo, useState } from 'react';
import {
  ChevronDown,
  CircleHelp,
  MessageSquare,
  Search,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { residentFaqs } from '../../data/residentFaqs.js';

const categories = [
  'All',
  ...new Set(residentFaqs.map((item) => item.category)),
];

export default function Faq() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [openFaqId, setOpenFaqId] = useState(residentFaqs[0]?.id ?? null);

  const filteredFaqs = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    return residentFaqs.filter((item) => {
      const matchesCategory =
        selectedCategory === 'All' || item.category === selectedCategory;
      const matchesSearch =
        !query ||
        item.question.toLowerCase().includes(query) ||
        item.answer.toLowerCase().includes(query) ||
        item.category.toLowerCase().includes(query);
      return matchesCategory && matchesSearch;
    });
  }, [searchTerm, selectedCategory]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
          Help &amp; FAQ
        </h1>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          Find quick answers about visitors, complaints, payments, amenities,
          and your account.
        </p>
      </div>

      <div className="rounded-2xl border border-indigo-100 bg-indigo-50/60 p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white">
            <CircleHelp className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-sm font-extrabold text-indigo-950">
              How can we help?
            </h2>
            <p className="mt-0.5 text-[11px] font-semibold text-indigo-700/70">
              Search by a task, issue, or feature.
            </p>
          </div>
        </div>
        <div className="relative mt-4">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-indigo-400" />
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="e.g. reopen complaint, amenity approval..."
            className="w-full rounded-xl border border-indigo-100 bg-white py-3 pl-10 pr-4 text-xs font-semibold text-slate-700 shadow-sm placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none"
          />
        </div>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-1">
        {categories.map((category) => (
          <button
            type="button"
            key={category}
            onClick={() => setSelectedCategory(category)}
            className={`shrink-0 rounded-xl px-3 py-2 text-[10px] font-bold transition-colors ${
              selectedCategory === category
                ? 'bg-indigo-600 text-white'
                : 'border border-slate-200 bg-white text-slate-600 hover:border-indigo-200'
            }`}
          >
            {category}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {filteredFaqs.length === 0 ? (
          <div className="rounded-2xl border border-slate-100 bg-white py-14 text-center">
            <CircleHelp className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-3 text-sm font-extrabold text-slate-700">
              No matching answers
            </p>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              Try a different search or category.
            </p>
          </div>
        ) : (
          filteredFaqs.map((item) => {
            const isOpen = openFaqId === item.id;
            return (
              <div
                key={item.id}
                className="overflow-hidden rounded-2xl border border-slate-100 bg-white"
              >
                <button
                  type="button"
                  onClick={() => setOpenFaqId(isOpen ? null : item.id)}
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
                  aria-expanded={isOpen}
                >
                  <div>
                    <span className="text-[9px] font-extrabold uppercase tracking-wider text-indigo-500">
                      {item.category}
                    </span>
                    <h2 className="mt-1 text-sm font-extrabold text-slate-800">
                      {item.question}
                    </h2>
                  </div>
                  <ChevronDown
                    className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${
                      isOpen ? 'rotate-180' : ''
                    }`}
                  />
                </button>
                {isOpen && (
                  <div className="border-t border-slate-50 px-5 py-4">
                    <p className="text-xs font-semibold leading-6 text-slate-500">
                      {item.answer}
                    </p>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <div className="flex flex-col justify-between gap-4 rounded-2xl border border-slate-100 bg-white p-5 sm:flex-row sm:items-center">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
            <MessageSquare className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-extrabold text-slate-800">
              Still need help?
            </h2>
            <p className="mt-1 text-[11px] font-semibold text-slate-400">
              Raise a complaint for a trackable non-emergency issue.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => navigate('/resident/complaints')}
          className="rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-indigo-700"
        >
          Go to Complaints
        </button>
      </div>
    </div>
  );
}
