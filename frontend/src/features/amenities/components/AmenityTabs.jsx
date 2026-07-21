import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  AMENITY_DETAIL_TABS,
  getAmenityTabPath,
} from '../constants/amenityRoutes.js';

export default function AmenityTabs({ amenityId }) {
  return (
    <nav
      aria-label="Amenity workspace"
      className="overflow-x-auto rounded-2xl border border-slate-100 bg-white p-1.5"
    >
      <div className="flex min-w-max gap-1">
        {AMENITY_DETAIL_TABS.map((tab) => (
          <NavLink
            key={tab.label}
            to={getAmenityTabPath(amenityId, tab.segment)}
            end={tab.end}
            className={({ isActive }) =>
              `rounded-xl px-4 py-2.5 text-xs font-bold transition-all ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-100'
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'
              }`
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
