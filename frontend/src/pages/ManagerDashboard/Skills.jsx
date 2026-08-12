import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import SkillPicker from '../../features/departments/components/SkillPicker';
import { departmentsApi } from '../../features/departments/departmentsApi';
import { PageHeading } from '../../features/security/components/Primitives';
import { useManagerDepartment } from './useManagerDepartment';

// **The requirement, and it is one endpoint.**
//
// "The department manager should be able to add new skills. Newly created
// skills get auto added to the department."
//
// That is `POST /departments/{id}/skills`, which takes a *name*: it creates the
// trade in the global catalogue if no case-insensitive match exists, and
// attaches it to this department, in one transaction. There is no second step
// to forget, and no window in which a skill exists but belongs to nobody.
//
// Every change on this screen is live — unlike the admin's create form, where
// the department does not exist yet and the picker holds its selection until
// the id comes back.

export default function ManagerSkills() {
  const { departmentId, department } = useManagerDepartment();
  const [selected, setSelected] = useState([]);

  const skills = useQuery({
    queryKey: ['departments', departmentId, 'skills'],
    queryFn: () => departmentsApi.departmentSkills(departmentId),
    enabled: Boolean(departmentId),
  });

  // The picker owns the working copy; the query is the source of truth. They
  // are synchronised on load rather than the picker reading the query directly,
  // because every add and remove is already a call — re-reading on each one
  // would make the chips flicker through the server's round trip.
  useEffect(() => {
    if (skills.data) {
      setSelected(skills.data.map((skill) => ({ id: skill.id, name: skill.name })));
    }
  }, [skills.data]);

  if (!departmentId) {
    return (
      <p className="rounded-2xl border border-amber-100 bg-amber-50 p-6 text-xs font-semibold text-amber-800">
        No department is assigned to your account yet, so there is nothing to add
        skills to.
      </p>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeading
        title="Skills"
        description={`What ${department?.name || 'this department'} can be matched for.`}
      />

      <section className="space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
        {skills.isLoading ? (
          <p className="text-sm font-semibold text-slate-500">Loading skills…</p>
        ) : (
          <SkillPicker
            departmentId={departmentId}
            selected={selected}
            onChange={setSelected}
            label="Skills this department needs"
          />
        )}

        <div className="rounded-xl bg-slate-50 p-4">
          <p className="text-[11px] font-bold text-slate-600">
            Why this matters
          </p>
          <p className="mt-1 text-[10px] font-semibold leading-relaxed text-slate-500">
            Hiring searches match service people by skill. A skill you add here
            immediately widens who this department can find — and because the
            catalogue is shared by every community, a trade you name once is
            available to everyone, so a plumber never has to claim
            &ldquo;Plumbing&rdquo; twice.
          </p>
          <p className="mt-2 text-[10px] font-semibold leading-relaxed text-slate-500">
            Type to see the closest matches before you add anything. If the trade
            is already there under a slightly different spelling, it will show
            above the add button.
          </p>
        </div>
      </section>
    </div>
  );
}
