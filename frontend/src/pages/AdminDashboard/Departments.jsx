import React, { useEffect, useMemo, useState } from 'react';
// Both modals render through a portal to document.body. They used to render in
// place, inside AdminLayout's `<main class="animate-fade-in">` — and `fadeIn`
// animates opacity with `fill-mode: forwards`, which keeps the animation
// applied forever and therefore keeps <main> a stacking context forever. Any
// z-index inside it, `z-[999]` included, is trapped at <main>'s own level
// (auto), so the sticky header's `z-40` — a sibling context — painted above
// the overlay and clipped the modal title. The portal moves the overlay out of
// that trap; no ancestor can capture it again.
import { createPortal } from 'react-dom';
import { useNavigate, useSearchParams } from 'react-router-dom';
// The "unassigned types" tile below calls `useQuery` — this import is what
// stood between /admin/departments and a ReferenceError that unmounted the
// whole app (the tile was added with the category-picker rework, the import
// was not).
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { QUERY_POLICIES } from '../../lib/api/queryClient';
import {
  AlertTriangle,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Eye,
  Mail,
  Pencil,
  Phone,
  Plus,
  Search,
  Trash2,
  UserRound,
  Users,
  X,
} from 'lucide-react';
import { useApp } from '../../store/useApp';
import { departmentsApi } from '../../features/departments/departmentsApi';
import CategoryPicker from '../../features/departments/components/CategoryPicker';
import SkillPicker from '../../features/departments/components/SkillPicker';

// **This form no longer adds technicians, and that is the point.**
//
// It used to carry a "Team members" block of typed-in names with a rank and a
// job title, which was the only way anybody got onto a roster. Technicians are
// now outside people: they register themselves (`service_providers`), apply or
// are invited, and a manager decides — the whole hiring surface at
// `/admin/departments/:id/hiring`. A second, quieter way to invent one here
// would produce roster rows with no account, no skills and no way to be
// dispatched, which is what the old block did.
//
// What remains is **leadership**, and it is a different kind of thing. A
// manager or supervisor is created by typing an email; that person signs in
// with it and is admitted (`staff_provisioning`). Nothing is sent, so the pending list below
// the form is the only place a mistyped address is ever visible.

/** A `{ id, name }` pair for the pickers, from the API's parallel arrays (R23). */
const pairsFrom = (names = [], ids = []) =>
  names.map((name, index) => ({ id: ids[index] ?? name, name }));

const emptyLeader = (rank) => ({
  key: `${rank}-${Math.random().toString(36).slice(2, 9)}`,
  name: '',
  email: '',
  phone: '',
  rank,
});

const emptyDepartment = () => ({
  name: '',
  description: '',
  categories: [],
  skills: [],
  head: '',
  email: '',
  phone: '',
  operatingHours: { start: '09:00', end: '18:00' },
  slaHours: 24,
  status: 'Active',
  leaders: [emptyLeader('manager')],
});

const getDepartmentForm = (department) => ({
  ...emptyDepartment(),
  ...department,
  // The API's optional fields are null when unset, but this form (and the
  // update slice, which trims them unconditionally) is string-typed throughout.
  description: department.description ?? '',
  head: department.head ?? '',
  email: department.email ?? '',
  phone: department.phone ?? '',
  slaHours: department.slaHours ?? 24,
  categories: pairsFrom(department.categories, department.categoryIds),
  skills: pairsFrom(department.skills, department.skillIds),
  operatingHours: {
    start: department.operatingHours?.start ?? '09:00',
    end: department.operatingHours?.end ?? '18:00',
  },
  // Editing an existing department does not re-provision anybody: its
  // leadership is whoever has already been invited, shown by the pending list
  // rather than re-entered here.
  leaders: [],
  // The real payload carries the roster, and the spread above would put it in
  // the form — from where `handleSubmit` spreads the form into the PATCH, whose
  // "replace the whole roster" semantics the `staff` note there describes.
  // Stripped here so key absence is guaranteed rather than assumed.
  staff: undefined,
});

const getDepartmentComplaints = (department, complaints) =>
  complaints.filter((complaint) => {
    const category = complaint.category?.toLowerCase() ?? '';
    return Boolean(category) && (
      (department.categories ?? []).some(
        (item) => item.toLowerCase() === category
      ) || department.name.toLowerCase().includes(category)
    );
  });

export default function Departments() {
  const complaints = useApp((state) => state.complaints);
  const createDepartment = useApp((state) => state.createDepartment);
  const updateDepartment = useApp((state) => state.updateDepartment);
  const setDepartmentStatus = useApp((state) => state.setDepartmentStatus);
  const deleteDepartment = useApp((state) => state.deleteDepartment);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [modalMode, setModalMode] = useState(null);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState(null);
  const [deleteDepartmentId, setDeleteDepartmentId] = useState(null);
  const [form, setForm] = useState(emptyDepartment);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  // **The list is `GET /departments`, not the snapshot copy in the store.** The
  // snapshot builds every department as `{staff: [], categories: []}` with only
  // name, description and status (dashboard_service.py:203, hardcoded and
  // intentional — see the router docstring), so rendering the store copy meant
  // no category chips and an edit form that blanked categories, skills, SLA,
  // head, contacts and hours however much was saved. The slice actions below
  // still write through the API (and keep their toasts, activity log and
  // guards); after each one resolves the page invalidates this key, so what is
  // rendered is always the server's answer rather than the optimistic copy.
  const departmentsQuery = useQuery({
    queryKey: ['departments'],
    queryFn: departmentsApi.list,
    ...QUERY_POLICIES.list,
  });
  const departments = useMemo(
    () => departmentsQuery.data ?? [],
    [departmentsQuery.data]
  );

  const selectedDepartment = departments.find(
    (department) => department.id === selectedDepartmentId
  );
  const departmentToDelete = departments.find(
    (department) => department.id === deleteDepartmentId
  );

  useEffect(() => {
    if (searchParams.get('create') !== '1') return;
    setForm(emptyDepartment());
    setSelectedDepartmentId(null);
    setModalMode('create');
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (!modalMode && !deleteDepartmentId) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setModalMode(null);
        setDeleteDepartmentId(null);
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleEscape);
    };
  }, [modalMode, deleteDepartmentId]);

  const departmentSummaries = useMemo(
    () =>
      departments.map((department) => {
        const ownedComplaints = getDepartmentComplaints(department, complaints);
        const activeComplaints = ownedComplaints.filter(
          (complaint) => complaint.status !== 'Resolved'
        );
        const overdueComplaints = activeComplaints.filter(
          (complaint) =>
            complaint.expectedResolutionAt &&
            new Date(complaint.expectedResolutionAt).getTime() < Date.now()
        );
        return {
          ...department,
          status: department.status ?? 'Active',
          activeComplaintCount: activeComplaints.length,
          resolvedComplaintCount: ownedComplaints.length - activeComplaints.length,
          overdueComplaintCount: overdueComplaints.length,
        };
      }),
    [departments, complaints]
  );

  const filteredDepartments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return departmentSummaries.filter((department) => {
      const matchesStatus =
        statusFilter === 'All' || department.status === statusFilter;
      const matchesSearch =
        !query ||
        [
          department.name,
          department.description,
          department.head,
          department.email,
          ...(department.categories ?? []),
          ...(department.staff ?? []).map((member) => member.name),
        ].some((value) => value?.toLowerCase().includes(query));
      return matchesStatus && matchesSearch;
    });
  }, [departmentSummaries, search, statusFilter]);

  const activeDepartmentCount = departments.filter(
    (department) => department.status !== 'Inactive'
  ).length;
  const totalStaffCount = departments.reduce(
    (total, department) => total + (department.staff?.length ?? 0),
    0
  );
  const activeComplaintCount = complaints.filter(
    (complaint) => complaint.status !== 'Resolved'
  ).length;

  // The community's own categories, for the "unassigned types" tile. The same
  // read the category picker uses, so the tile and the field can never disagree
  // about which categories exist.
  const categories = useQuery({
    queryKey: ['complaint-categories'],
    queryFn: departmentsApi.categories,
    // Named reference-data domain (task calls this out explicitly): was a
    // bespoke 60s staleTime, upgraded to the shared 30-minute policy every
    // other reader of this catalogue now uses.
    ...QUERY_POLICIES.reference,
  });
  const unassignedCategoryCount = (categories.data || []).filter(
    (category) => (category.departmentCount ?? 0) === 0
  ).length;

  // **Who has already been created for the department being edited.**
  // Re-entering one of them is not a harmless repeat: `staff_invitations_one_open_email`
  // is a unique index, so the second create answers 409 and the modal's banner
  // reported the whole save as failed even though the department and its skills
  // had gone through. The edit form lists these rows so nobody re-types a
  // person, and `handleSubmit` skips any that are typed anyway.
  //
  // Same key and same filter as the department page's own pending panel, so the
  // two share one cache entry instead of fetching the same list twice — and the
  // `['departments']` invalidation in `handleSubmit` refreshes both.
  const pendingInvitationsQuery = useQuery({
    queryKey: ['departments', selectedDepartmentId, 'staff-invitations'],
    queryFn: () =>
      departmentsApi.staffInvitations(selectedDepartmentId, { status: 'pending' }),
    ...QUERY_POLICIES.list,
    // `isLoading` rather than `isPending` is what the form is handed below: a
    // disabled query stays `pending` for as long as it is off, so the create
    // modal would otherwise render a spinner that never resolves.
    enabled: Boolean(selectedDepartmentId),
  });
  const pendingInvitations = useMemo(
    () => pendingInvitationsQuery.data ?? [],
    [pendingInvitationsQuery.data]
  );

  const openCreate = () => {
    setSelectedDepartmentId(null);
    setForm(emptyDepartment());
    setSaveError('');
    setModalMode('create');
  };

  const openView = (department) => {
    navigate(`/admin/departments/${department.id}`);
  };

  const openEdit = (department) => {
    setSelectedDepartmentId(department.id);
    setForm(getDepartmentForm(department));
    setModalMode('edit');
  };

  const closeModal = () => {
    setModalMode(null);
    setSelectedDepartmentId(null);
  };

  const setLeaderField = (key, field, value) => {
    setForm((current) => ({
      ...current,
      leaders: current.leaders.map((leader) =>
        leader.key === key ? { ...leader, [field]: value } : leader
      ),
    }));
  };

  const removeLeader = (key) => {
    setForm((current) => ({
      ...current,
      leaders: current.leaders.filter((leader) => leader.key !== key),
    }));
  };

  /**
   * Save the department, then its skills, then its leadership.
   *
   * **Three calls, in that order, because the last two need an id the first one
   * mints.** They are deliberately not folded into `POST /departments`: skills
   * are a relationship to a global catalogue and leadership provisioning writes
   * to a table with its own authorization, and putting either inside the
   * department create would mean one endpoint doing three jobs with three
   * different failure modes.
   *
   * A failure after the department is created leaves the department created.
   * That is stated to the operator rather than hidden — they are on the edit
   * screen for a department that now exists, and re-saving is the fix. Rolling
   * back a create because a supervisor's email was rejected would be the worse
   * outcome.
   *
   * `await` also fixes something that was quietly broken: `createDepartment` is
   * async, so `if (result) closeModal()` used to close the modal on a Promise —
   * which is always truthy — and a failed create looked like a successful one.
   */
  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.name.trim() || form.categories.length === 0 || saving) return;

    setSaving(true);
    setSaveError('');
    try {
      // `head` is a *derived* display name now, not a field. The form used to
      // carry a free-text "Department Manager" input beside the invitation
      // block — two generations of manager entry at once, and the owner read
      // it as duplicate fields because it was. The invitation block is the
      // only place a manager is entered; `head` survives purely as the display
      // name that the department cards and DepartmentDetail render. On create
      // it is the first manager-ranked invitation's name (or empty). On edit
      // the leaders list starts empty — leadership already invited is not
      // re-entered — so an absent manager row falls back to the department's
      // existing `head` rather than blanking it.
      const invitedManagerName =
        form.leaders
          .find((leader) => leader.rank === 'manager' && leader.name.trim())
          ?.name.trim() || '';
      const departmentData = {
        ...form,
        head: invitedManagerName || form.head || '',
        // The department wire takes category *names*: `upsert_category_names`
        // creates any it has not seen in this community, so choosing a new one
        // and saving is what creates it. There is no create-category endpoint
        // and none is needed.
        categories: form.categories.map((entry) => entry.name),
        // `staff` is deliberately omitted, not sent as `[]`. On a create there
        // is no roster yet, so the two are equivalent -- but on an *edit*,
        // `PATCH /departments/{id}` treats key presence as "replace the whole
        // roster": an explicit `staff: []` was reaching the API on every save
        // (this form never collects roster entries; that field died with the
        // hiring rework) and silently deactivating every member of the
        // department being edited. Omitting the key is what "leave the roster
        // alone" actually means.
      };

      const saved =
        modalMode === 'edit' && selectedDepartmentId
          ? await updateDepartment(selectedDepartmentId, departmentData)
          : await createDepartment(departmentData);
      if (!saved) return;

      const departmentId = saved.id;
      await departmentsApi.setDepartmentSkills(
        departmentId,
        form.skills.map((entry) => entry.id)
      );

      const leaders = form.leaders.filter(
        (leader) => leader.name.trim() && leader.email.trim()
      );
      // Addresses that already have an open invitation, which the API will
      // refuse a second one for. Lower-cased because `staff_invitations.invitee_email`
      // is `citext` and the RPC lower-cases what it stores, so the collision the
      // unique index sees ignores capitalisation and a case-sensitive check here
      // would let `P_Manager@…` through to a 409.
      //
      // The same set absorbs each address as it is sent, which is also what
      // collapses two rows typed with the same email in one save — the second
      // would otherwise fail against the row the first just created.
      const sentEmails = new Set(
        pendingInvitations.map((invitation) =>
          (invitation.email || '').trim().toLowerCase()
        )
      );
      for (const leader of leaders) {
        const email = leader.email.trim();
        // Already invited is not an error: the person is provisioned, which is
        // what the operator asked for.
        if (sentEmails.has(email.toLowerCase())) continue;
        sentEmails.add(email.toLowerCase());
        try {
          await departmentsApi.inviteStaffMember(departmentId, {
            email,
            name: leader.name.trim(),
            rank: leader.rank,
            phone: leader.phone.trim() || null,
          });
        } catch (error) {
          // Whatever went wrong here, the department and its skills are already
          // saved — say so, and say which address it was, because the banner is
          // the only thing the operator has to act on. `unique_violation` is
          // still reachable past the skip above (uniqueness is per *community*,
          // so the address may be pending in another department, or somebody
          // else may have created it since this list was fetched).
          throw new Error(
            error?.code === 'unique_violation'
              ? `${email} already has a pending invitation.`
              : `The department was saved, but ${email} could not be added: ${
                  error?.message || 'the request failed.'
                }`
          );
        }
      }

      closeModal();
    } catch (error) {
      setSaveError(
        error?.message || 'The department was saved but something after it failed.'
      );
    } finally {
      // Even a half-failed save changed the server (the department exists
      // before its skills are attached), so refetch regardless of outcome. The
      // prefix match also refreshes the detail page's roster and invitations.
      queryClient.invalidateQueries({ queryKey: ['departments'] });
      setSaving(false);
    }
  };

  const selectedSummary = departmentSummaries.find(
    (department) => department.id === selectedDepartmentId
  );
  const selectedComplaints = selectedDepartment
    ? getDepartmentComplaints(selectedDepartment, complaints)
    : [];
  const deleteActiveComplaintCount = departmentToDelete
    ? getDepartmentComplaints(departmentToDelete, complaints).filter(
        (complaint) => complaint.status !== 'Resolved'
      ).length
    : 0;

  // The slice owns the toast; this owns what the page shows afterwards.
  const changeStatus = async (departmentId, status) => {
    await setDepartmentStatus(departmentId, status);
    queryClient.invalidateQueries({ queryKey: ['departments'] });
  };

  const confirmDelete = async () => {
    if (!deleteDepartmentId) return;
    // `deleteDepartment` is async, so the unawaited `result?.ok` this used to
    // test was a property of a Promise — always undefined, so a successful
    // delete never closed this dialog (the same bug `handleSubmit`'s comment
    // records for the save path).
    const result = await deleteDepartment(deleteDepartmentId);
    queryClient.invalidateQueries({ queryKey: ['departments'] });
    if (result?.ok) setDeleteDepartmentId(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
            Departments
          </h1>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Manage service teams, complaint ownership, staffing, and response targets.
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="flex items-center justify-center gap-1.5 self-start rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 transition-colors hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" />
          New Department
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <SummaryCard
          label="Departments"
          value={departments.length}
          helper={`${activeDepartmentCount} active`}
          icon={Building2}
          tone="indigo"
        />
        <SummaryCard
          label="Team Members"
          value={totalStaffCount}
          helper="Across all departments"
          icon={Users}
          tone="emerald"
        />
        <SummaryCard
          label="Open Complaints"
          value={activeComplaintCount}
          helper="Live department workload"
          icon={BriefcaseBusiness}
          tone="amber"
        />
        {/* Counted from the community's real categories rather than a hardcoded
            six, which is what this tile used to do — so a category somebody
            invented could never be reported as unassigned, however unassigned
            it was. `departmentCount` comes from the same read the category
            picker uses. */}
        <SummaryCard
          label="Unassigned Types"
          value={unassignedCategoryCount}
          helper="Categories without an owner"
          icon={AlertTriangle}
          tone="rose"
        />
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-white p-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search departments, categories, or staff..."
            className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-xs font-semibold text-slate-700 placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none"
          />
        </div>
        <div className="flex rounded-xl bg-slate-50 p-1">
          {['All', 'Active', 'Inactive'].map((status) => (
            <button
              type="button"
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`rounded-lg px-3 py-2 text-[10px] font-bold transition-colors ${
                statusFilter === status
                  ? 'bg-white text-indigo-600 shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {departmentsQuery.isPending ? (
        <p className="text-sm font-semibold text-slate-500">
          Loading the departments…
        </p>
      ) : departmentsQuery.error ? (
        <p role="alert" className="text-xs font-semibold text-rose-600">
          {departmentsQuery.error.message}
        </p>
      ) : filteredDepartments.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-6 py-16 text-center">
          <Building2 className="mx-auto h-9 w-9 text-slate-300" />
          <h2 className="mt-3 text-sm font-extrabold text-slate-700">
            {departments.length === 0
              ? 'Create your first department'
              : 'No matching departments'}
          </h2>
          <p className="mx-auto mt-1 max-w-sm text-xs font-semibold text-slate-400">
            {departments.length === 0
              ? 'Set complaint ownership, add team members, and define response targets.'
              : 'Try changing the search or status filter.'}
          </p>
          {departments.length === 0 && (
            <button
              type="button"
              onClick={openCreate}
              className="mt-4 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-indigo-700"
            >
              Create Department
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {filteredDepartments.map((department) => (
            <article
              key={department.id}
              className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm transition-all hover:border-indigo-100 hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                    <Building2 className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="truncate text-sm font-extrabold text-slate-800">
                        {department.name}
                      </h2>
                      <StatusBadge status={department.status ?? 'Active'} />
                    </div>
                    <p className="mt-1 line-clamp-2 text-[11px] font-semibold leading-relaxed text-slate-400">
                      {department.description || 'No description added.'}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => openView(department)}
                  className="flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-2 text-[10px] font-bold text-slate-500 hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-600"
                  aria-label={`View ${department.name}`}
                >
                  <Eye className="h-4 w-4" />
                  Open
                </button>
              </div>

              <div className="mt-4 flex flex-wrap gap-1.5">
                {(department.categories ?? []).map((category) => (
                  <span
                    key={category}
                    className="rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-[9px] font-bold text-indigo-700"
                  >
                    {category}
                  </span>
                ))}
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-slate-50 p-3 text-[10px] font-semibold text-slate-500 sm:grid-cols-4">
                <Metric label="Staff" value={department.staff?.length ?? 0} />
                <Metric label="Open tickets" value={department.activeComplaintCount} />
                <Metric label="Overdue" value={department.overdueComplaintCount} />
                <Metric label="SLA" value={`${department.slaHours ?? 24}h`} />
              </div>

              <div className="mt-4 flex flex-col justify-between gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center">
                <div>
                  <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                    Department Manager
                  </p>
                  <p className="mt-0.5 text-xs font-bold text-slate-700">
                    {department.head || 'Not assigned'}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      changeStatus(
                        department.id,
                        department.status === 'Inactive' ? 'Active' : 'Inactive'
                      )
                    }
                    className="rounded-lg border border-slate-200 px-3 py-2 text-[10px] font-bold text-slate-600 hover:bg-slate-50"
                  >
                    {department.status === 'Inactive' ? 'Activate' : 'Deactivate'}
                  </button>
                  <button
                    type="button"
                    onClick={() => openEdit(department)}
                    className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:border-indigo-200 hover:text-indigo-600"
                    aria-label={`Edit ${department.name}`}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleteDepartmentId(department.id)}
                    className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600"
                    aria-label={`Delete ${department.name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Portalled to document.body — see the createPortal import note. Also
          `items-start`, not `items-center`: a centered child taller than the
          viewport overflows both edges and the top edge (the title) is the
          part that gets lost. Anchoring to the top with matching vertical
          padding and capping the panel at the remaining height means the
          title is always visible and the panel scrolls internally. */}
      {modalMode && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          aria-label={modalMode === 'edit' ? 'Edit department' : 'Create department'}
          className="fixed inset-0 z-[999] flex items-start justify-center bg-slate-900/60 px-4 py-8 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeModal();
          }}
        >
          <div className="max-h-[calc(100vh-4rem)] w-full max-w-3xl overflow-y-auto rounded-3xl bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-extrabold text-slate-900">
                  {modalMode === 'create'
                    ? 'Create Department'
                    : modalMode === 'edit'
                      ? 'Edit Department'
                      : selectedDepartment?.name}
                </h2>
                <p className="mt-1 text-xs font-semibold text-slate-400">
                  {modalMode === 'view'
                    ? 'Team details, service ownership, and current workload.'
                    : 'Configure ownership, contacts, staffing, and response targets.'}
                </p>
              </div>
              <button
                type="button"
                onClick={closeModal}
                className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200"
                aria-label="Close department dialog"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {modalMode === 'view' && selectedDepartment ? (
              <DepartmentDetails
                department={selectedDepartment}
                summary={selectedSummary}
                complaints={selectedComplaints}
                onEdit={() => openEdit(selectedDepartment)}
              />
            ) : (
              <DepartmentForm
                form={form}
                setForm={setForm}
                departmentId={modalMode === 'edit' ? selectedDepartmentId : null}
                pendingInvitations={pendingInvitations}
                pendingInvitationsLoading={pendingInvitationsQuery.isLoading}
                setLeaderField={setLeaderField}
                removeLeader={removeLeader}
                onAddLeader={(rank) =>
                  setForm((current) => ({
                    ...current,
                    leaders: [...current.leaders, emptyLeader(rank)],
                  }))
                }
                onCancel={closeModal}
                onSubmit={handleSubmit}
                isEditing={modalMode === 'edit'}
                saving={saving}
                saveError={saveError}
              />
            )}
          </div>
        </div>,
        document.body
      )}

      {/* Portalled for the same stacking-context reason as the form modal.
          This one keeps items-center: the panel is max-w-md and short, so it
          always fits — but max-h + internal scroll guard the tiny-viewport
          case anyway. */}
      {departmentToDelete && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Delete ${departmentToDelete.name}`}
          className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
        >
          <div className="max-h-[calc(100vh-2rem)] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-6 shadow-xl">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-50 text-rose-600">
              <Trash2 className="h-5 w-5" />
            </div>
            <h2 className="mt-4 text-lg font-extrabold text-slate-900">
              Delete {departmentToDelete.name}?
            </h2>
            {deleteActiveComplaintCount > 0 ? (
              <p className="mt-2 text-xs font-semibold leading-relaxed text-slate-500">
                This department owns {deleteActiveComplaintCount} active complaint
                {deleteActiveComplaintCount === 1 ? '' : 's'}. Resolve or reassign
                them before deletion. You can deactivate the department now instead.
              </p>
            ) : (
              <p className="mt-2 text-xs font-semibold leading-relaxed text-slate-500">
                This permanently removes its configuration and staff directory.
                Complaint records will remain available.
              </p>
            )}
            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={() => setDeleteDepartmentId(null)}
                className="flex-1 rounded-xl border border-slate-200 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              {deleteActiveComplaintCount > 0 ? (
                <button
                  type="button"
                  onClick={() => {
                    changeStatus(departmentToDelete.id, 'Inactive');
                    setDeleteDepartmentId(null);
                  }}
                  className="flex-1 rounded-xl bg-slate-800 py-2.5 text-xs font-bold text-white hover:bg-slate-900"
                >
                  Deactivate
                </button>
              ) : (
                <button
                  type="button"
                  onClick={confirmDelete}
                  className="flex-1 rounded-xl bg-rose-600 py-2.5 text-xs font-bold text-white hover:bg-rose-700"
                >
                  Delete Department
                </button>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

function SummaryCard({ label, value, helper, icon: Icon, tone }) {
  const tones = {
    indigo: 'bg-indigo-50 text-indigo-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-600',
    rose: 'bg-rose-50 text-rose-600',
  };
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
            {label}
          </p>
          <p className="mt-1 text-2xl font-extrabold text-slate-800">{value}</p>
          <p className="mt-1 text-[10px] font-semibold text-slate-400">{helper}</p>
        </div>
        <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${tones[tone]}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-sm font-extrabold text-slate-700">{value}</p>
    </div>
  );
}

function StatusBadge({ status }) {
  const isActive = status !== 'Inactive';
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[9px] font-extrabold ${
        isActive
          ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
          : 'border-slate-200 bg-slate-100 text-slate-500'
      }`}
    >
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

function DepartmentForm({
  form,
  setForm,
  departmentId,
  pendingInvitations = [],
  pendingInvitationsLoading = false,
  setLeaderField,
  removeLeader,
  onAddLeader,
  onCancel,
  onSubmit,
  isEditing,
  saving,
  saveError,
}) {
  // Validation that waits for the user: the category requirement is real, but
  // painting it red onto a form nobody has touched yet reads as "you already
  // did something wrong". It appears once the field has been interacted with
  // (or a submit is attempted); until then the disabled submit button carries
  // the requirement silently.
  const [categoriesTouched, setCategoriesTouched] = useState(false);
  const inputClass =
    'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';
  const isSecurityDepartment =
    form.name.toLowerCase().includes('security') ||
    form.categories.some((entry) => entry.name === 'Security');
  return (
    <form
      onSubmit={(event) => {
        setCategoriesTouched(true);
        onSubmit(event);
      }}
      className="mt-6 space-y-5"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Department name" required>
          <input
            required
            value={form.name}
            onChange={(event) =>
              setForm((current) => ({ ...current, name: event.target.value }))
            }
            placeholder="e.g. Electrical Services"
            className={inputClass}
          />
        </Field>
        <Field label="Status">
          <select
            value={form.status}
            onChange={(event) =>
              setForm((current) => ({ ...current, status: event.target.value }))
            }
            className={inputClass}
          >
            <option value="Active">Active</option>
            <option value="Inactive">Inactive</option>
          </select>
        </Field>
      </div>

      <Field label="Description">
        <textarea
          rows={2}
          value={form.description}
          onChange={(event) =>
            setForm((current) => ({
              ...current,
              description: event.target.value,
            }))
          }
          placeholder="What does this department handle?"
          className={`${inputClass} resize-none`}
        />
      </Field>

      {/* A combobox over the community's real categories, replacing a hardcoded
          six-item checkbox grid. The grid could not express a category anybody
          invented, while the backend has accepted arbitrary names since 0019 —
          so a society with a lift or a swimming pool had no way to say so. */}
      <CategoryPicker
        required
        selected={form.categories}
        onChange={(categories) => {
          setCategoriesTouched(true);
          setForm((current) => ({ ...current, categories }));
        }}
      />
      {categoriesTouched && form.categories.length === 0 && (
        <p className="-mt-3 text-[10px] font-semibold text-rose-500">
          Select at least one complaint category.
        </p>
      )}

      {/* Skills, which this form has never had. A department needs them
          explicitly: nothing is inherited from the categories above, because
          the two answer different questions and inheriting one from the other
          would give every department a list nobody chose. */}
      <SkillPicker
        departmentId={departmentId}
        selected={form.skills}
        onChange={(skills) => setForm((current) => ({ ...current, skills }))}
      />
      <p className="-mt-3 text-[10px] font-semibold text-slate-400">
        Who this department can hire depends on these. A skill that is not in
        the list yet is created when you add it — the catalogue is shared by
        every community.
      </p>

      {/* The free-text "Department Manager" input is gone on purpose: it was
          the previous generation of manager entry, and with the invitation
          block below it the form carried both at once — the owner read that
          as duplicate manager fields because it was. The manager is entered
          in the invitation block only; `head` (the display name the cards and
          DepartmentDetail show) is derived from the first manager-ranked
          invitation at submit time, and an edit with no re-entered manager
          keeps the existing head. The two fields kept here are the
          *department's* contact details, not a person's — relabelled so
          nobody reads them as one again. */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Department contact email">
          <input
            type="email"
            value={form.email}
            onChange={(event) =>
              setForm((current) => ({ ...current, email: event.target.value }))
            }
            placeholder="department@example.com"
            className={inputClass}
          />
        </Field>
        <Field label="Department contact phone">
          <input
            required={isSecurityDepartment}
            value={form.phone}
            onChange={(event) =>
              setForm((current) => ({ ...current, phone: event.target.value }))
            }
            placeholder="+91 98765 43210"
            className={inputClass}
          />
        </Field>
        <Field label="Response SLA (hours)">
          <input
            type="number"
            min="1"
            max="720"
            required
            value={form.slaHours}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                slaHours: Number(event.target.value),
              }))
            }
            className={inputClass}
          />
        </Field>
      </div>

      {isSecurityDepartment && (
        <p className="-mt-2 rounded-xl border border-indigo-100 bg-indigo-50 px-3.5 py-3 text-[10px] font-semibold leading-relaxed text-indigo-700">
          The security department manager can sign in through the Community
          Portal using the contact phone number. Staff use the phone numbers in
          the team list below.
        </p>
      )}

      <Field label="Operating hours">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-1">
            <span className="text-[10px] font-semibold text-slate-400">
              Start time
            </span>
            <input
              type="time"
              value={form.operatingHours.start}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  operatingHours: {
                    ...current.operatingHours,
                    start: event.target.value,
                  },
                }))
              }
              className={inputClass}
            />
          </label>
          <label className="space-y-1">
            <span className="text-[10px] font-semibold text-slate-400">
              End time
            </span>
            <input
              type="time"
              value={form.operatingHours.end}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  operatingHours: {
                    ...current.operatingHours,
                    end: event.target.value,
                  },
                }))
              }
              className={inputClass}
            />
          </label>
        </div>
      </Field>

      {/* **Leadership, not staff.** The block this replaces added typed-in
          technicians with a rank and a job title, and it was the only way onto
          a roster. Technicians are outside people now — they register, apply or
          are invited, and a manager decides, all at
          `/admin/departments/:id/hiring`. Inventing one here would produce a
          roster row with no account, no skills and nothing that can dispatch to
          it.

          A manager or supervisor is a different thing and has no registration
          flow at all: type an email, and that person is admitted the first time
          they sign in with it. */}
      <div className="space-y-3 rounded-2xl border border-slate-100 bg-slate-50 p-4">
        <div>
          <p className="text-xs font-extrabold text-slate-700">
            Manager and supervisors
          </p>
          <p className="mt-0.5 text-[10px] font-semibold leading-relaxed text-slate-400">
            They sign in with the email address entered here — nothing is sent,
            so a wrong address simply never arrives. Technicians are hired from
            the department&rsquo;s hiring screen instead.
          </p>
        </div>

        {/* **Who has already been created, above the empty rows.** The email is
            not a delivery address, it is the key a sign-in is matched against,
            and one open invitation per address is a unique index — so re-typing
            somebody already listed here used to answer 409 and report the whole
            save as failed. This list existed only on the department's own page,
            which is not the screen anybody is looking at while they type.

            Read-only on purpose. Correcting or withdrawing one is
            `PendingInvitations` on that page, and duplicating those mutations
            inside a form that has not been submitted yet would mean an edit that
            lands while the surrounding form is still a draft. */}
        {isEditing && pendingInvitationsLoading && (
          <p className="text-[10px] font-semibold text-slate-400">
            Checking who has already been invited…
          </p>
        )}

        {isEditing && pendingInvitations.length > 0 && (
          <div className="space-y-2">
            {pendingInvitations.map((invitation) => (
              <div
                key={invitation.id}
                className="flex items-center justify-between gap-2 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-[11px] font-bold text-amber-900">
                    {invitation.name || invitation.email}
                    {invitation.rank && (
                      <>
                        {' · '}
                        <span className="font-semibold">
                          {invitation.rank === 'manager' ? 'Manager' : 'Supervisor'}
                        </span>
                      </>
                    )}
                  </p>
                  <p className="truncate text-[10px] font-semibold text-amber-700">
                    {invitation.email}
                  </p>
                </div>
                <span className="shrink-0 rounded-full border border-amber-200 bg-white px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider text-amber-700">
                  Pending
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Held back while the list above is still loading: "nobody has been
            invited yet" is a claim, and it would be made before the answer
            arrives. */}
        {form.leaders.length === 0 && !pendingInvitationsLoading && (
          <p className="rounded-xl border border-dashed border-slate-300 px-3 py-4 text-center text-[10px] font-semibold text-slate-400">
            {isEditing
              ? pendingInvitations.length > 0
                ? 'Everyone invited so far is listed above. Add a row for somebody new.'
                : 'Nobody has been invited yet. A department can run without leadership and be given some later.'
              : 'No manager yet. A department can be created without one and given one later.'}
          </p>
        )}

        {form.leaders.map((leader) => (
          <div
            key={leader.key}
            className="grid gap-2 rounded-xl border border-slate-100 bg-white p-3 sm:grid-cols-[1fr_1.2fr_1fr_auto_auto]"
          >
            <input
              value={leader.name}
              onChange={(event) => setLeaderField(leader.key, 'name', event.target.value)}
              placeholder="Full name"
              className={inputClass}
            />
            <input
              type="email"
              required={Boolean(leader.name.trim())}
              value={leader.email}
              onChange={(event) => setLeaderField(leader.key, 'email', event.target.value)}
              placeholder="Email for sign-in"
              className={inputClass}
            />
            <input
              value={leader.phone}
              onChange={(event) => setLeaderField(leader.key, 'phone', event.target.value)}
              placeholder="Phone"
              className={inputClass}
            />
            <select
              value={leader.rank}
              onChange={(event) => setLeaderField(leader.key, 'rank', event.target.value)}
              className={inputClass}
            >
              {/* Two values, and the closed set is the database's:
                  `staff_invitations_rank_check`. `member` is deliberately not
                  offered — that rank comes from hiring. */}
              <option value="manager">Manager</option>
              <option value="supervisor">Supervisor</option>
            </select>
            <button
              type="button"
              onClick={() => removeLeader(leader.key)}
              className="rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
              aria-label={`Remove ${leader.name || 'this person'}`}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onAddLeader('manager')}
            className="flex items-center gap-1 rounded-lg bg-white px-3 py-2 text-[10px] font-bold text-indigo-600 shadow-sm"
          >
            <Plus className="h-3.5 w-3.5" /> Add manager
          </button>
          {/* Optional, and offered as its own button so it reads that way: a
              department goes through without one. */}
          <button
            type="button"
            onClick={() => onAddLeader('supervisor')}
            className="flex items-center gap-1 rounded-lg bg-white px-3 py-2 text-[10px] font-bold text-slate-500 shadow-sm"
          >
            <Plus className="h-3.5 w-3.5" /> Add supervisor (optional)
          </button>
        </div>
      </div>

      {saveError ? (
        <p
          role="alert"
          className="rounded-xl border border-rose-100 bg-rose-50 px-3.5 py-3 text-[10px] font-semibold leading-relaxed text-rose-700"
        >
          {saveError}
        </p>
      ) : null}

      <div className="flex gap-3 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 rounded-xl border border-slate-200 py-3 text-xs font-bold text-slate-600 hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving || !form.name.trim() || form.categories.length === 0}
          className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-bold text-white shadow-md shadow-indigo-100 hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {saving ? 'Saving…' : isEditing ? 'Save Changes' : 'Create Department'}
        </button>
      </div>
    </form>
  );
}

function DepartmentDetails({ department, summary, complaints, onEdit }) {
  return (
    <div className="mt-6 space-y-5">
      <div className="grid gap-3 sm:grid-cols-4">
        <MetricPanel
          label="Status"
          value={department.status ?? 'Active'}
          icon={CheckCircle2}
        />
        <MetricPanel
          label="Team size"
          value={department.staff?.length ?? 0}
          icon={Users}
        />
        <MetricPanel
          label="Open tickets"
          value={summary?.activeComplaintCount ?? 0}
          icon={BriefcaseBusiness}
        />
        <MetricPanel
          label="Response SLA"
          value={`${department.slaHours ?? 24} hours`}
          icon={Clock3}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-slate-100 p-4">
          <h3 className="text-xs font-extrabold text-slate-700">Department details</h3>
          <p className="mt-2 text-xs font-semibold leading-relaxed text-slate-500">
            {department.description || 'No description added.'}
          </p>
          <div className="mt-4 space-y-2.5 text-xs font-semibold text-slate-500">
            <DetailRow icon={UserRound} value={department.head || 'No department manager'} />
            <DetailRow icon={Mail} value={department.email || 'No email added'} />
            <DetailRow icon={Phone} value={department.phone || 'No phone added'} />
            <DetailRow
              icon={Clock3}
              value={`${department.operatingHours?.start ?? '09:00'} – ${department.operatingHours?.end ?? '18:00'}`}
            />
          </div>
        </div>
        <div className="rounded-2xl border border-slate-100 p-4">
          <h3 className="text-xs font-extrabold text-slate-700">Complaint ownership</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {(department.categories ?? []).map((category) => (
              <span
                key={category}
                className="rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-bold text-indigo-700"
              >
                {category}
              </span>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <Metric label="Open" value={summary?.activeComplaintCount ?? 0} />
            <Metric label="Resolved" value={summary?.resolvedComplaintCount ?? 0} />
            <Metric label="Overdue" value={summary?.overdueComplaintCount ?? 0} />
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-100">
        <div className="border-b border-slate-100 px-4 py-3">
          <h3 className="text-xs font-extrabold text-slate-700">Staff directory</h3>
        </div>
        {department.staff?.length ? (
          <div className="divide-y divide-slate-100">
            {department.staff.map((member) => (
              <div
                key={member.id}
                className="flex flex-col justify-between gap-2 px-4 py-3 text-xs sm:flex-row sm:items-center"
              >
                <div>
                  <p className="font-bold text-slate-700">{member.name}</p>
                  <p className="mt-0.5 text-[10px] font-semibold text-slate-400">
                    {member.role}
                  </p>
                </div>
                <p className="font-semibold text-slate-500">
                  {member.phone || 'No phone'}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="px-4 py-6 text-center text-xs font-semibold text-slate-400">
            No staff assigned.
          </p>
        )}
      </div>

      <div className="rounded-2xl border border-slate-100">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h3 className="text-xs font-extrabold text-slate-700">Recent complaints</h3>
          <span className="text-[10px] font-bold text-slate-400">
            {complaints.length} total
          </span>
        </div>
        {complaints.length ? (
          <div className="divide-y divide-slate-100">
            {complaints.slice(0, 4).map((complaint) => (
              <div
                key={complaint.id}
                className="flex items-center justify-between gap-3 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-slate-700">
                    {complaint.title}
                  </p>
                  <p className="mt-0.5 text-[10px] font-semibold text-slate-400">
                    Flat {complaint.flat} · {complaint.urgency} urgency
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-slate-500">
                    {complaint.status}
                  </span>
                  <ChevronRight className="h-3.5 w-3.5 text-slate-300" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="px-4 py-6 text-center text-xs font-semibold text-slate-400">
            No complaints in this department’s categories.
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={onEdit}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-xs font-bold text-white hover:bg-indigo-700"
      >
        <Pencil className="h-4 w-4" /> Edit Department
      </button>
    </div>
  );
}

function MetricPanel({ label, value, icon: Icon }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <Icon className="h-4 w-4 text-indigo-600" />
      <p className="mt-2 text-[9px] font-bold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="mt-0.5 text-xs font-extrabold text-slate-700">{value}</p>
    </div>
  );
}

function DetailRow({ icon: Icon, value }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-3.5 w-3.5 shrink-0 text-slate-400" />
      <span>{value}</span>
    </div>
  );
}

function Field({ label, required = false, children }) {
  return (
    <div className="space-y-1.5">
      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
        {label}
        {required && <span className="text-rose-500"> *</span>}
      </label>
      {children}
    </div>
  );
}
