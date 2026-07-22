// HomeBandhu Vue 3 Frontend Logic (Milestone 2 - Comprehensive Wireframe Engine)
// Uses Vue 3 Composition API via CDN. All state is maintained in reactive objects.
// Data is synced with localStorage to persist across refreshes.

const { ref, reactive, computed, onMounted, watch } = Vue;

const HomeBandhuApp = {
  setup() {
    // --- MOCK DATABASE STRUCTURES (Wireframes 1-12) ---
    const defaultServicemen = [
      { id: 'S1', name: 'Ramesh Kumar', specialty: 'Plumbing', rating: 4.8, status: 'Available' },
      { id: 'S2', name: 'Sunil Sharma', specialty: 'Electrician', rating: 4.7, status: 'Available' },
      { id: 'S3', name: 'Arjun Verma', specialty: 'Gas Utility', rating: 4.9, status: 'Available' },
      { id: 'S4', name: 'Vikram Singh', specialty: 'Billing & Accounts', rating: 4.5, status: 'Available' },
    ];

    const defaultNotices = [
      { id: 'N1', reference: 'Section 4 - Safety', body: 'Water tank cleaning scheduled for Tower A & B on Nov 8. Please store water in advance.', dateOfEffect: '2026-11-08', isImmediate: false, datePublished: '2026-11-04', readBy: ['B-1204'] },
      { id: 'N2', reference: 'Section 12 - Events', body: 'Diwali celebration at Clubhouse. All residents are cordially invited for lights & sweets.', dateOfEffect: '2026-11-06', isImmediate: false, datePublished: '2026-11-03', readBy: [] },
      { id: 'N3', reference: 'Section 8 - Utilities', body: 'Lift maintenance for Tower B scheduled on Nov 4 between 2 PM to 5 PM.', dateOfEffect: '2026-11-04', isImmediate: false, datePublished: '2026-11-02', readBy: ['B-1204'] }
    ];

    const defaultComplaints = [
      {
        id: '1042',
        title: 'Leaking tap in kitchen',
        description: 'Kitchen sink pipe has been leaking steadily since yesterday evening, water pooling under the cabinet. Needs a technician with replacement parts.',
        category: 'Plumbing',
        priority: 'High',
        status: 'Work in Progress',
        residentName: 'John Doe',
        residentFlat: 'Flat 4B',
        residentPhone: '98765 43210',
        assignedTo: 'S1',
        dateRaised: '2026-10-12',
        isStarred: true,
        slaStatus: 'Overdue by 1 hr',
        slaTimer: 'Overdue by 1 hr',
        latestUpdate: 'Plumber assigned, awaiting parts',
        history: [
          { status: 'Submitted', timestamp: '2026-10-12 10:05 AM', detail: 'Complaint raised by resident' },
          { status: 'Assigned', timestamp: '2026-10-12 10:40 AM', detail: 'Assigned to plumber Suresh Rao' },
          { status: 'Scheduled', timestamp: '2026-10-12 12:50 PM', detail: 'Visit scheduled' },
          { status: 'Work in Progress', timestamp: '2026-10-12 01:15 PM', detail: 'Work started on site' }
        ],
        slaTimeline: [
          { stage: 'Raised', target: '10:15 AM', actual: '10:05 AM', staff: null, isCompleted: true, isOverdue: false },
          { stage: 'Assigned', target: '11:00 AM', actual: '10:40 AM', staff: 'Suresh Rao', isCompleted: true, isOverdue: false },
          { stage: 'Scheduled', target: '1:00 PM', actual: '12:50 PM', staff: 'Suresh Rao', isCompleted: true, isOverdue: false },
          { stage: 'Work in Progress', target: '3:00 PM', actual: 'Overdue by 1 hr', staff: 'Suresh Rao', isCompleted: false, isOverdue: true },
          { stage: 'Resolved', target: '5:00 PM', actual: 'pending', staff: null, isCompleted: false, isOverdue: false }
        ],
        messages: [
          { sender: 'Admin', text: "Any update on 4B's sink?" },
          { sender: 'Suresh', text: "On site now, checking the part." },
          { sender: 'Admin', text: "It's now past the 3 PM target." }
        ]
      },
      {
        id: '1043',
        title: 'Circuit breaker tripping',
        description: 'Main distribution breaker trips every time air conditioner is turned on.',
        category: 'Electrical',
        priority: 'High',
        status: 'Assigned',
        residentName: 'Meera Iyer',
        residentFlat: 'Flat 2A',
        residentPhone: '98765 22222',
        assignedTo: 'S2',
        dateRaised: '2026-10-13',
        isStarred: true,
        slaStatus: '3 hrs left',
        slaTimer: '3 hrs left',
        latestUpdate: 'Electrician dispatched',
        history: [
          { status: 'Submitted', timestamp: '2026-10-13 08:15 AM', detail: 'Ticket logged' },
          { status: 'Assigned', timestamp: '2026-10-13 09:00 AM', detail: 'Assigned to Sunil Sharma' }
        ],
        slaTimeline: [
          { stage: 'Raised', target: '08:30 AM', actual: '08:15 AM', staff: null, isCompleted: true, isOverdue: false },
          { stage: 'Assigned', target: '09:30 AM', actual: '09:00 AM', staff: 'Sunil Sharma', isCompleted: true, isOverdue: false },
          { stage: 'Scheduled', target: '12:00 PM', actual: '3 hrs left', staff: 'Sunil Sharma', isCompleted: false, isOverdue: false },
          { stage: 'Work in Progress', target: '03:00 PM', actual: 'pending', staff: null, isCompleted: false, isOverdue: false },
          { stage: 'Resolved', target: '06:00 PM', actual: 'pending', staff: null, isCompleted: false, isOverdue: false }
        ],
        messages: []
      },
      {
        id: '1044',
        title: 'Gate intercom unresponsive',
        description: 'Intercom connection to security post not ringing for guest approvals.',
        category: 'Security',
        priority: 'Medium',
        status: 'Submitted',
        residentName: 'Ravi Kumar',
        residentFlat: 'Flat 6C',
        residentPhone: '98765 11111',
        assignedTo: null,
        dateRaised: '2026-10-14',
        isStarred: false,
        slaStatus: '1 day left',
        slaTimer: '1 day left',
        latestUpdate: 'Ticket logged',
        history: [
          { status: 'Submitted', timestamp: '2026-10-14 09:00 AM', detail: 'Ticket logged' }
        ],
        slaTimeline: [],
        messages: []
      },
      {
        id: '1045',
        title: 'Corridor window glass cracked',
        description: 'Glass window pane cracked on 1st floor corridor landing.',
        category: 'Housekeeping',
        priority: 'Low',
        status: 'Scheduled',
        residentName: 'Priya Nair',
        residentFlat: 'Flat 1D',
        residentPhone: '98765 33333',
        assignedTo: 'S4',
        dateRaised: '2026-10-13',
        isStarred: false,
        slaStatus: '5 hrs left',
        slaTimer: '5 hrs left',
        latestUpdate: 'Visit scheduled for tomorrow',
        history: [
          { status: 'Submitted', timestamp: '2026-10-13 02:30 PM', detail: 'Ticket logged' }
        ],
        slaTimeline: [],
        messages: []
      },
      {
        id: '1046',
        title: 'Water pipe leak confirmed fixed',
        description: 'Overhead pipe seepage repaired and inspected.',
        category: 'Plumbing',
        priority: 'Low',
        status: 'Resolved',
        residentName: 'Suresh Rao',
        residentFlat: 'Flat 3B',
        residentPhone: '98765 44444',
        assignedTo: 'S1',
        dateRaised: '2026-10-10',
        isStarred: false,
        slaStatus: '—',
        slaTimer: '—',
        latestUpdate: 'Leak fixed, confirmed by resident',
        history: [
          { status: 'Submitted', timestamp: '2026-10-10 11:00 AM', detail: 'Ticket logged' },
          { status: 'Resolved', timestamp: '2026-10-10 04:00 PM', detail: 'Resolved' }
        ],
        slaTimeline: [],
        messages: []
      }
    ];

    const defaultBookings = [
      { id: 'B1', amenityName: 'Swimming Pool', residentName: 'Anil Bhatt', residentFlat: 'Flat 3A', dates: ['2026-10-15'], timeSlot: '6–7 PM', totalCost: 500, paymentStatus: 'Unpaid', status: 'Pending', hasDefaulterWarning: true, defaulterReason: 'Outstanding Dues: Booking Blocked' },
      { id: 'B2', amenityName: 'Swimming Pool', residentName: 'Sana Qureshi', residentFlat: 'Flat 5B', dates: ['2026-10-16'], timeSlot: '4–6 PM', totalCost: 1000, paymentStatus: 'Paid', status: 'Pending', hasDefaulterWarning: false, defaulterReason: null },
      { id: 'B3', amenityName: 'Party Hall', residentName: 'Desai Family', residentFlat: 'Flat 8C', dates: ['2026-10-09'], timeSlot: 'Full Day', totalCost: 8000, paymentStatus: 'Paid', status: 'Completed', depositStatus: 'Held', depositAmount: 2000, hasDefaulterWarning: false },
      { id: 'B4', amenityName: 'Party Hall', residentName: 'Rao Anniversary', residentFlat: 'Flat 4A', dates: ['2026-10-19'], timeSlot: 'Evening', totalCost: 6000, paymentStatus: 'Paid', status: 'Upcoming', hasDefaulterWarning: false },
      { id: 'B5', amenityName: 'Party Hall', residentName: 'Menon Wedding', residentFlat: 'Flat 2D', dates: ['2026-10-20', '2026-10-21', '2026-10-22'], timeSlot: '3-day', totalCost: 24000, paymentStatus: 'Paid', status: 'Upcoming', isMultiDay: true, subDays: [
        { day: 'Day 1 — Oct 20', event: 'Mehendi', status: 'Active' },
        { day: 'Day 2 — Oct 21', event: 'Sangeet', status: 'Active' },
        { day: 'Day 3 — Oct 22', event: 'Reception', status: 'Canceled', isProratedRefunded: true }
      ]}
    ];

    const defaultVisitors = [
      { id: 'V1', name: 'Priya Sharma', type: 'Expected', phone: '9876543210', otp: '482910', qrCode: 'QR_PRIYA_482910', residentFlat: 'B-1204', checkInTime: null, approvalStatus: 'Approved' },
      { id: 'V2', name: 'Rahul Verma', type: 'Checked In', phone: '9123456789', otp: '109283', qrCode: 'QR_RAHUL_109283', residentFlat: 'B-1204', checkInTime: '2026-11-08 10:00 AM', approvalStatus: 'Approved' }
    ];

    const defaultFacilities = [
      { name: 'Swimming Pool', pendingCount: 3, dueAmount: 5000, isEnabled: true, photo: 'pool photo' },
      { name: 'Party Hall', pendingCount: 0, dueAmount: 0, isEnabled: false, photo: 'party hall photo' },
      { name: 'Tennis Court', pendingCount: 1, dueAmount: 1200, isEnabled: true, photo: 'tennis court photo' }
    ];

    const defaultBylaws = [
      { id: '1.1', title: '1.1 Noise Limits', category: '1.0 General', status: 'Live', lastPublished: 'Sep 2, 2026', content: 'Quiet hours are observed from 10:00 PM to 7:00 AM daily. Residents and guests must keep noise — including music, construction, and gatherings — to a level that does not disturb neighboring units. Repeated violations may result in a formal notice.' },
      { id: '1.2', title: '1.2 Pet Policy', category: '1.0 General', status: 'Pending Amendment', lastPublished: 'Aug 1, 2026', pendingDate: 'Aug 14, 2026', content: 'Residents may keep up to two (2) domestic pets per unit. Dogs must be leashed at all times in common areas. Owners are responsible for immediate cleanup.' },
      { id: '2.1', title: '2.1 Visitor Passes', category: '2.0 Parking', status: 'Live', lastPublished: 'Jun 3, 2026', content: 'Each unit is allocated a maximum of 2 visitor parking passes per day. Vehicles parked in visitor spots beyond 24 hours require admin approval.' },
      { id: '2.2', title: '2.2 Reserved Spots', category: '2.0 Parking', status: 'Live', lastPublished: 'May 10, 2026', content: 'Reserved parking spots are assigned exclusively to registered resident vehicle numbers.' }
    ];

    const defaultCommittee = [
      { name: 'Meera Nair', flat: 'Flat 2A', role: 'President', tags: ['Official App Chat'] },
      { name: 'Rahul Sharma', flat: 'Flat 4B', role: 'Secretary', tags: ['Plumbing', 'Security', 'Official App Chat'] },
      { name: 'Vikram Desai', flat: 'Flat 4C', role: 'Treasurer', tags: ['Finance', 'Phone Exposed'] }
    ];

    const defaultMeetings = [
      { title: 'Monthly Board Meeting', date: 'Today, 7:00 PM', status: 'Upcoming', virtualLink: 'meet.google.com/xyz-abcd-efg' },
      { title: 'Budget Review Session', date: 'Jun 18, 2026', status: 'Awaiting Minutes', virtualLink: 'meet.google.com/budget-2026' },
      { title: 'Q2 AGM', date: 'Apr 3, 2026', status: 'Minutes Filed', virtualLink: 'meet.google.com/q2-agm' }
    ];

    const defaultRecords = [
      { type: 'Minute', title: 'Budget Review Session', date: 'Jun 18, 2026', file: 'budget-review-jun18.pdf' },
      { type: 'Resolution', title: 'Approve Vendor Contract Renewal', date: 'from Q2 AGM · Apr 3, 2026', file: 'res-2026-014.pdf' },
      { type: 'Minute', title: 'Q2 AGM', date: 'Apr 3, 2026', file: 'q2-agm-minutes.pdf' }
    ];

    // --- APPLICATION STATE ---
    const currentRole = ref('admin'); // Options: 'resident', 'admin', 'security', 'serviceman'
    const currentTab = ref('dashboard'); // Tabs depend on role
    
    // Database Stores (Reactive)
    const db = reactive({
      servicemen: [],
      notices: [],
      complaints: [],
      bookings: [],
      visitors: [],
      waterTankers: [],
      materialMovements: [],
      facilities: [],
      bylaws: [],
      committee: [],
      meetings: [],
      records: []
    });

    // Offline mode for security
    const isOfflineMode = ref(false);
    
    // Dynamic alerts/toasts
    const toasts = ref([]);
    
    // Wireframe specific states
    const complaintFilter = ref('active'); // 'active', 'resolved', 'all'
    const selectedComplaintDetail = ref(null); // for Wireframe 7b
    const selectedAmenity = ref(null); // null or facility name
    const amenityTab = ref('dashboard'); // 'dashboard', 'approvals', 'ledger', 'settings'
    const selectedBylaw = ref(null);
    const delayCauseMessage = ref('');

    // --- MODAL CONTROLS & FORM INPUTS ---
    const activeModals = reactive({
      raiseComplaint: false,
      bookAmenity: false,
      publishNotice: false,
      preApproveVisitor: false,
      makePayment: false,
      verifyOTP: false,
      pushNotification: false,
      complaintDetail: false,     // Wireframe 7b
      requestDelayCause: false,   // Wireframe 7c
      blockOutTime: false,        // Wireframe 8b
      adminOverrideBooking: false,// Wireframe 8f
      rejectBookingReason: false, // Wireframe 8h
      depositAction: false,       // Wireframe 8d
      editBylaw: false,           // Wireframe 9b
      publishBylawConfig: false,  // Wireframe 9c
      bylawHistory: false,        // Wireframe 9d
      scheduleMeeting: false,     // Wireframe 10f
      addRecord: false,           // Wireframe 10h
      addCommitteeMember: false,  // Wireframe 10c/10d
      createDepartment: false     // Wireframe 3b
    });

    // Form data objects
    const newComplaint = reactive({ title: '', description: '', category: 'Plumbing', priority: 'Medium', selectedId: null });
    const newBooking = reactive({ amenityName: 'Gym', dates: [], isMultiDay: false, customDate: '' });
    const newNotice = reactive({ reference: 'Section 4 - Safety', body: '', dateOfEffect: new Date().toISOString().split('T')[0], isImmediate: false });
    const newVisitor = reactive({ name: '', phone: '' });
    
    // Security Forms
    const otpVerifyInput = ref('');
    const adHocVisitorForm = reactive({ name: '', phone: '', flat: 'B-1204' });
    const newTanker = reactive({ vehicleNumber: '', capacity: '10000L', source: 'Aqua Builders' });
    const newMaterial = reactive({ type: 'Inward', description: '', contactName: '', phone: '' });
    
    // Payment mockup state
    const paymentProcessing = ref(false);
    const paymentSuccess = ref(false);
    const paymentTargetBooking = ref(null);

    // Push notification visitor state
    const currentPushVisitor = ref(null);

    // Serviceman working state
    const selectedServicemanId = ref('S1');

    // Admin Wireframe Forms
    const blockOutForm = reactive({ reason: 'Filter cleaning & chlorine top-up', depts: ['Plumbing', 'Cleaning'] });
    const overrideBookingForm = reactive({ residentName: '', date: '2026-10-15', timeSlot: '4:00 - 5:00 PM', isComped: true, skipBuffer: false, guests: [] });
    const rejectBookingForm = reactive({ booking: null, reason: 'Outstanding dues on account', notifyResident: true });
    const depositActionForm = reactive({ booking: null, actionType: 'Refund', amount: 1500, reason: 'Cracked pool tile' });
    const bylawEditForm = reactive({ id: '1.2', title: '1.2 Pet Policy', content: '', changeType: 'Major Amendment', effectiveDate: '2026-08-14', requireAck: true });
    const newMeetingForm = reactive({ title: '', date: '', virtualLink: 'meet.google.com/meeting', agenda: '1. General review\n2. Maintenance budget' });
    const newRecordForm = reactive({ pastMeeting: 'Budget Review Session', type: 'Minute', file: 'notes.pdf', notes: '' });
    const newDeptForm = reactive({ name: '', categories: ['General'], staffName: 'Suresh Rao' });

    // --- HASH ROUTING FOR BROWSER BACK BUTTON SUPPORT ---
    function syncHashToState() {
      const hash = window.location.hash;
      if (!hash || hash === '#' || hash === '#/') {
        currentRole.value = 'admin';
        currentTab.value = 'dashboard';
        updateHash();
        return;
      }
      const parts = hash.replace(/^#\/?/, '').split('/');
      if (parts.length >= 2) {
        const role = parts[0];
        const tab = parts[1];
        if (['resident', 'admin', 'security', 'serviceman'].includes(role)) {
          currentRole.value = role;
          // Validate & alias tab keys per role to prevent blank screens
          const validTabs = {
            resident: ['dashboard', 'complaints', 'amenities', 'visitors', 'notices'],
            admin: ['dashboard', 'complaints', 'bookings', 'notices', 'committee'],
            security: ['check-in', 'registers', 'water-tanker'],
            serviceman: ['dashboard']
          };

          let validRoleTabs = validTabs[role] || ['dashboard'];
          let normalizedTab = tab;
          
          if (role === 'admin' && tab === 'amenities') normalizedTab = 'bookings';
          if (role === 'resident' && tab === 'bookings') normalizedTab = 'amenities';
          
          if (!validRoleTabs.includes(normalizedTab)) {
            normalizedTab = validRoleTabs[0];
          }

          currentTab.value = normalizedTab;
        }
        if (parts.length >= 3 && parts[2]) {
          newComplaint.selectedId = parts[2];
        } else {
          newComplaint.selectedId = null;
        }
      }
    }

    function updateHash() {
      let targetHash = `#/${currentRole.value}/${currentTab.value}`;
      if (currentTab.value === 'complaints' && newComplaint.selectedId) {
        targetHash += `/${newComplaint.selectedId}`;
      }
      if (window.location.hash !== targetHash) {
        window.location.hash = targetHash;
      }
    }

    // --- INITIALIZATION ---
    onMounted(() => {
      // Load data from localStorage or fallback to defaults
      db.servicemen = loadFromStorage('hb_servicemen', defaultServicemen);
      db.notices = loadFromStorage('hb_notices', defaultNotices);
      db.complaints = loadFromStorage('hb_complaints', defaultComplaints);
      db.bookings = loadFromStorage('hb_bookings', defaultBookings);
      db.visitors = loadFromStorage('hb_visitors', defaultVisitors);
      db.facilities = loadFromStorage('hb_facilities', defaultFacilities);
      db.bylaws = loadFromStorage('hb_bylaws', defaultBylaws);
      db.committee = loadFromStorage('hb_committee', defaultCommittee);
      db.meetings = loadFromStorage('hb_meetings', defaultMeetings);
      db.records = loadFromStorage('hb_records', defaultRecords);
      db.waterTankers = loadFromStorage('hb_waterTankers', []);
      db.materialMovements = loadFromStorage('hb_materialMovements', []);
      
      if (db.bylaws.length > 0) {
        selectedBylaw.value = db.bylaws[0];
      }

      // Initialize hash routing state
      syncHashToState();
      window.addEventListener('hashchange', syncHashToState);
      
      showToast('Welcome to HomeBandhu Society Portal! Feel free to switch roles to demo the application.', 'info');
    });

    // Helper functions
    function loadFromStorage(key, fallback) {
      const data = localStorage.getItem(key);
      return data ? JSON.parse(data) : fallback;
    }

    function saveToStorage(key, value) {
      localStorage.setItem(key, JSON.stringify(value));
    }

    // Save triggers on database changes
    watch(() => db.servicemen, (val) => saveToStorage('hb_servicemen', val), { deep: true });
    watch(() => db.notices, (val) => saveToStorage('hb_notices', val), { deep: true });
    watch(() => db.complaints, (val) => saveToStorage('hb_complaints', val), { deep: true });
    watch(() => db.bookings, (val) => saveToStorage('hb_bookings', val), { deep: true });
    watch(() => db.visitors, (val) => saveToStorage('hb_visitors', val), { deep: true });
    watch(() => db.facilities, (val) => saveToStorage('hb_facilities', val), { deep: true });
    watch(() => db.bylaws, (val) => saveToStorage('hb_bylaws', val), { deep: true });
    watch(() => db.waterTankers, (val) => saveToStorage('hb_waterTankers', val), { deep: true });
    watch(() => db.materialMovements, (val) => saveToStorage('hb_materialMovements', val), { deep: true });

    // Watchers to update URL hash when role/tab/complaint changes
    watch([currentRole, currentTab, () => newComplaint.selectedId], () => {
      updateHash();
    });

    // Toast manager
    function showToast(message, type = 'success') {
      const id = Date.now();
      toasts.value.push({ id, message, type });
      setTimeout(() => {
        toasts.value = toasts.value.filter(t => t.id !== id);
      }, 4000);
    }

    // --- ROLE & TAB CONTROL ---
    function switchRole(role) {
      currentRole.value = role;
      if (role === 'resident') {
        currentTab.value = 'dashboard';
      } else if (role === 'admin') {
        currentTab.value = 'dashboard';
      } else if (role === 'security') {
        currentTab.value = 'check-in';
      } else if (role === 'serviceman') {
        currentTab.value = 'dashboard';
      }
      showToast(`Switched view to ${role.toUpperCase()} role`, 'info');
    }

    // --- WIREFRAME COMPLAINTS TRIAGE METHODS (7a–7f) ---
    function toggleStarComplaint(comp) {
      comp.isStarred = !comp.isStarred;
      showToast(comp.isStarred ? `Pinned Ticket #${comp.id} to Urgent Complaints` : `Unpinned Ticket #${comp.id}`, 'info');
    }

    function openComplaintDetail(comp) {
      selectedComplaintDetail.value = comp;
      activeModals.complaintDetail = true;
    }

    function openRequestDelayCause() {
      activeModals.requestDelayCause = true;
    }

    function sendDelayRequest() {
      if (selectedComplaintDetail.value) {
        if (!selectedComplaintDetail.value.messages) selectedComplaintDetail.value.messages = [];
        selectedComplaintDetail.value.messages.push({
          sender: 'Admin',
          text: delayCauseMessage.value || 'This complaint has exceeded its SLA. Please provide the cause for the delay and an updated ETA.'
        });
        showToast('SLA Delay Cause Request dispatched to assigned staff.', 'warning');
      }
      delayCauseMessage.value = '';
      activeModals.requestDelayCause = false;
    }

    // --- WIREFRAME AMENITIES WORKSPACE METHODS (8a–8i) ---
    function openAmenityDetail(facilityName) {
      selectedAmenity.value = facilityName;
      amenityTab.value = 'dashboard';
    }

    function closeAmenityDetail() {
      selectedAmenity.value = null;
    }

    function submitBlockOutSlot() {
      showToast(`Maintenance block slot configured for ${selectedAmenity.value || 'facility'}.`, 'success');
      activeModals.blockOutTime = false;
    }

    function submitAdminOverrideBooking() {
      const newBook = {
        id: 'B' + (db.bookings.length + 1),
        amenityName: selectedAmenity.value || 'Swimming Pool',
        residentName: overrideBookingForm.residentName || 'Rohan Desai',
        residentFlat: 'Flat 6A',
        dates: [overrideBookingForm.date],
        timeSlot: overrideBookingForm.timeSlot,
        totalCost: overrideBookingForm.isComped ? 0 : 500,
        paymentStatus: overrideBookingForm.isComped ? 'Paid (Comped)' : 'Paid',
        status: 'Confirmed',
        hasDefaulterWarning: false
      };
      db.bookings.unshift(newBook);
      showToast(`Admin Override Booking created for ${newBook.residentName}. Security gate cleared.`, 'success');
      activeModals.adminOverrideBooking = false;
    }

    function openRejectBookingModal(booking) {
      rejectBookingForm.booking = booking;
      activeModals.rejectBookingReason = true;
    }

    function confirmBookingRejection() {
      if (rejectBookingForm.booking) {
        rejectBookingForm.booking.status = 'Rejected';
        showToast(`Booking request rejected. ${rejectBookingForm.notifyResident ? 'Resident notified with reason.' : ''}`, 'danger');
      }
      activeModals.rejectBookingReason = false;
    }

    function openDepositActionModal(booking, actionType) {
      depositActionForm.booking = booking;
      depositActionForm.actionType = actionType;
      activeModals.depositAction = true;
    }

    function confirmDepositAction() {
      if (depositActionForm.booking) {
        depositActionForm.booking.depositStatus = depositActionForm.actionType === 'Refund' ? 'Refunded' : 'Deducted';
        showToast(`Deposit ${depositActionForm.actionType} processed (₹${depositActionForm.amount}). Ledger updated.`, 'info');
      }
      activeModals.depositAction = false;
    }

    function forceCancelBooking(booking) {
      booking.status = 'Cancelled';
      showToast(`Booking ${booking.id} force-cancelled. Resident notified.`, 'warning');
    }

    // --- WIREFRAME BYLAWS METHODS (9a-9e) ---
    function selectBylaw(bylaw) {
      selectedBylaw.value = bylaw;
    }

    function openEditBylawsModal(bylaw) {
      bylawEditForm.id = bylaw.id;
      bylawEditForm.title = bylaw.title;
      bylawEditForm.content = bylaw.content;
      activeModals.editBylaw = true;
    }

    function openPublishBylawsConfig() {
      activeModals.editBylaw = false;
      activeModals.publishBylawsConfig = true;
    }

    function confirmPublishBylaws() {
      const bylaw = db.bylaws.find(b => b.id === bylawEditForm.id);
      if (bylaw) {
        bylaw.content = bylawEditForm.content;
        bylaw.status = bylawEditForm.changeType === 'Major Amendment' ? 'Pending Amendment' : 'Live';
        bylaw.lastPublished = new Date().toISOString().split('T')[0];
        showToast(`Bylaws section ${bylaw.id} updated. Notification sent to residents.`, 'success');
      }
      activeModals.publishBylawsConfig = false;
    }

    // --- WIREFRAME COMMITTEE METHODS (10a-10h) ---
    function submitScheduleMeeting() {
      if (!newMeetingForm.title) return;
      db.meetings.unshift({
        title: newMeetingForm.title,
        date: newMeetingForm.date || 'Today, 7:00 PM',
        status: 'Upcoming',
        virtualLink: newMeetingForm.virtualLink
      });
      showToast(`Meeting scheduled: ${newMeetingForm.title}`, 'success');
      activeModals.scheduleMeeting = false;
    }

    function submitAddRecord() {
      if (!newRecordForm.pastMeeting) return;
      db.records.unshift({
        type: newRecordForm.type,
        title: newRecordForm.pastMeeting,
        date: new Date().toISOString().split('T')[0],
        file: newRecordForm.file
      });
      showToast(`Record ${newRecordForm.type} added to hub.`, 'success');
      activeModals.addRecord = false;
    }

    function submitCreateDepartment() {
      if (!newDeptForm.name) return;
      showToast(`Department ${newDeptForm.name} created successfully!`, 'success');
      activeModals.createDepartment = false;
    }

    // --- RESIDENT WORKFLOWS ---
    function submitComplaint() {
      if (!newComplaint.title || !newComplaint.description) {
        showToast('Please fill out all complaint fields.', 'danger');
        return;
      }
      
      const complaintId = '' + (db.complaints.length + 1040);
      const today = new Date().toISOString().split('T')[0];
      
      const complaint = {
        id: complaintId,
        title: newComplaint.title,
        description: newComplaint.description,
        category: newComplaint.category,
        priority: newComplaint.priority,
        status: 'Submitted',
        residentName: 'Sai Vishnu',
        residentFlat: 'B-1204',
        residentPhone: '98765 43210',
        assignedTo: null,
        dateRaised: today,
        isStarred: false,
        slaStatus: '1 day left',
        slaTimer: '1 day left',
        latestUpdate: 'Ticket logged by resident',
        history: [
          { status: 'Submitted', timestamp: `${today} ${getCurrentTimeStr()}`, detail: 'Complaint raised by resident' }
        ],
        slaTimeline: [],
        messages: []
      };

      db.complaints.unshift(complaint);
      newComplaint.selectedId = complaintId;
      
      newComplaint.title = '';
      newComplaint.description = '';
      newComplaint.category = 'Plumbing';
      newComplaint.priority = 'Medium';
      activeModals.raiseComplaint = false;
      
      showToast('Complaint registered successfully! Admin will assign a serviceman shortly.');
    }

    function submitPreApproveVisitor() {
      if (!newVisitor.name || !newVisitor.phone) {
        showToast('Please specify visitor name and contact.', 'danger');
        return;
      }

      const generatedOTP = Math.floor(100000 + Math.random() * 900000).toString();
      const visitor = {
        id: 'V' + (db.visitors.length + 1),
        name: newVisitor.name,
        type: 'Expected',
        phone: newVisitor.phone,
        otp: generatedOTP,
        qrCode: `QR_${newVisitor.name.toUpperCase().replace(/\s+/g, '_')}_${generatedOTP}`,
        residentFlat: 'B-1204',
        checkInTime: null,
        approvalStatus: 'Approved'
      };

      db.visitors.unshift(visitor);
      newVisitor.name = '';
      newVisitor.phone = '';
      activeModals.preApproveVisitor = false;
      
      showToast(`Visitor authorized! Share OTP: ${generatedOTP} or download QR.`);
    }

    function selectBookedDates() {
      if (!newBooking.customDate) {
        showToast('Please select a valid date.', 'danger');
        return;
      }
      
      const selectedDate = new Date(newBooking.customDate);
      const bookedDates = [newBooking.customDate];
      
      if (newBooking.isMultiDay) {
        const nextDay = new Date(selectedDate);
        nextDay.setDate(selectedDate.getDate() + 1);
        bookedDates.push(nextDay.toISOString().split('T')[0]);
      }

      const bookingId = 'B' + (db.bookings.length + 1);
      const costPerDay = newBooking.amenityName === 'Club House' ? 2000 : 500;
      const totalCost = bookedDates.length * costPerDay;

      const booking = {
        id: bookingId,
        amenityName: newBooking.amenityName,
        dates: bookedDates,
        timeSlot: 'Standard Slot',
        status: 'Pending',
        totalCost: totalCost,
        paymentStatus: 'Unpaid',
        residentFlat: 'B-1204',
        residentName: 'Sai Vishnu',
        isMultiDay: newBooking.isMultiDay,
        hasDefaulterWarning: false
      };

      db.bookings.unshift(booking);
      activeModals.bookAmenity = false;
      
      triggerPaymentFlow(booking);
      showToast('Amenity reservation requested! Please complete your payment.');
    }

    function triggerPaymentFlow(booking) {
      paymentTargetBooking.value = booking;
      paymentSuccess.value = false;
      paymentProcessing.value = false;
      activeModals.makePayment = true;
    }

    function processPayment() {
      paymentProcessing.value = true;
      setTimeout(() => {
        paymentProcessing.value = false;
        paymentSuccess.value = true;
        
        const booking = db.bookings.find(b => b.id === paymentTargetBooking.value.id);
        if (booking) {
          booking.paymentStatus = 'Paid';
          booking.status = 'Confirmed';
        }
        
        showToast('Payment successful! Your booking is now confirmed.', 'success');
      }, 1800);
    }

    // --- ADMIN WORKFLOWS ---
    function assignComplaintToServiceman(complaintId, servicemanId) {
      const complaint = db.complaints.find(c => c.id === complaintId);
      const serviceman = db.servicemen.find(s => s.id === servicemanId);
      
      if (!complaint || !serviceman) return;
      
      complaint.assignedTo = serviceman.id;
      complaint.status = 'Analysing';
      complaint.latestUpdate = `Assigned to ${serviceman.name}`;
      complaint.history.push({
        status: 'Analysing',
        timestamp: `${new Date().toISOString().split('T')[0]} ${getCurrentTimeStr()}`,
        detail: `Assigned to ${serviceman.name} (${serviceman.specialty})`
      });
      
      showToast(`Complaint assigned to ${serviceman.name}.`);
    }

    function setBookingStatus(bookingId, status) {
      const booking = db.bookings.find(b => b.id === bookingId);
      if (booking) {
        booking.status = status;
        showToast(`Booking ${bookingId} has been ${status.toLowerCase()}.`);
      }
    }

    function cancelSpecificBookingDate(bookingId, dateToCancel) {
      const booking = db.bookings.find(b => b.id === bookingId);
      if (!booking) return;

      booking.dates = booking.dates.filter(d => d !== dateToCancel);
      
      const costPerDay = booking.amenityName === 'Club House' ? 2000 : 500;
      booking.totalCost = booking.dates.length * costPerDay;
      
      if (booking.dates.length === 0) {
        booking.status = 'Cancelled';
      }
      
      showToast(`Date ${dateToCancel} cancelled. Refund of ₹${costPerDay} initiated.`, 'info');
    }

    function publishNotice() {
      if (!newNotice.body) {
        showToast('Notice body cannot be empty.', 'danger');
        return;
      }

      const today = new Date().toISOString().split('T')[0];
      const noticeId = 'N' + (db.notices.length + 1);

      const notice = {
        id: noticeId,
        reference: newNotice.reference,
        body: newNotice.body,
        dateOfEffect: newNotice.isImmediate ? today : newNotice.dateOfEffect || today,
        isImmediate: newNotice.isImmediate,
        datePublished: today,
        readBy: []
      };

      db.notices.unshift(notice);
      
      newNotice.reference = 'Section 4 - Safety';
      newNotice.body = '';
      newNotice.dateOfEffect = new Date().toISOString().split('T')[0];
      newNotice.isImmediate = true;
      activeModals.publishNotice = false;
      
      showToast('Notice published immediately. Residents notified.');
    }

    // --- SECURITY WORKFLOWS ---
    function verifyVisitorOTP() {
      if (!otpVerifyInput.value) {
        showToast('Please enter a 6-digit code.', 'danger');
        return;
      }

      const visitor = db.visitors.find(v => v.otp === otpVerifyInput.value && v.type === 'Expected');
      if (visitor) {
        visitor.type = 'Checked In';
        visitor.checkInTime = `${new Date().toISOString().split('T')[0]} ${getCurrentTimeStr()}`;
        otpVerifyInput.value = '';
        showToast(`Access granted! Welcome ${visitor.name}.`);
      } else {
        showToast('Invalid or expired OTP code.', 'danger');
      }
    }

    function submitAdHocVisitor() {
      if (!adHocVisitorForm.name || !adHocVisitorForm.phone) {
        showToast('Please fill out visitor details.', 'danger');
        return;
      }

      const newId = 'V' + (db.visitors.length + 1);
      const visitor = {
        id: newId,
        name: adHocVisitorForm.name,
        type: 'Pending',
        phone: adHocVisitorForm.phone,
        otp: null,
        qrCode: null,
        residentFlat: adHocVisitorForm.flat,
        checkInTime: null,
        approvalStatus: 'Pending'
      };

      db.visitors.unshift(visitor);
      currentPushVisitor.value = visitor;
      
      adHocVisitorForm.name = '';
      adHocVisitorForm.phone = '';

      activeModals.pushNotification = true;
      showToast('Visitor request sent to Resident flat B-1204! Resident approval pending.', 'warning');
    }

    function handlePushNotificationApproval(approved) {
      if (currentPushVisitor.value) {
        const visitor = db.visitors.find(v => v.id === currentPushVisitor.value.id);
        if (visitor) {
          if (approved) {
            visitor.approvalStatus = 'Approved';
            visitor.type = 'Checked In';
            visitor.checkInTime = `${new Date().toISOString().split('T')[0]} ${getCurrentTimeStr()}`;
            showToast(`Visitor ${visitor.name} has been APPROVED. Access granted.`);
          } else {
            visitor.approvalStatus = 'Rejected';
            visitor.type = 'Expected';
            showToast(`Visitor ${visitor.name} has been REJECTED. Access denied.`, 'danger');
          }
        }
      }
      activeModals.pushNotification = false;
      currentPushVisitor.value = null;
    }

    function submitMaterialLog() {
      if (!newMaterial.description || !newMaterial.contactName) {
        showToast('Please enter material detail and courier name.', 'danger');
        return;
      }
      const log = {
        id: 'M' + (db.materialMovements.length + 1),
        type: newMaterial.type,
        description: newMaterial.description,
        contactName: newMaterial.contactName,
        phone: newMaterial.phone || 'N/A',
        timeStamp: `${new Date().toISOString().split('T')[0]} ${getCurrentTimeStr()}`
      };
      db.materialMovements.unshift(log);
      
      newMaterial.description = '';
      newMaterial.contactName = '';
      newMaterial.phone = '';
      showToast('Material movement logged successfully.');
    }

    function submitTankerLog() {
      if (!newTanker.vehicleNumber) {
        showToast('Please enter water tanker vehicle number.', 'danger');
        return;
      }
      const log = {
        id: 'WT' + (db.waterTankers.length + 1),
        vehicleNumber: newTanker.vehicleNumber,
        capacity: newTanker.capacity,
        source: newTanker.source,
        checkInTime: `${new Date().toISOString().split('T')[0]} ${getCurrentTimeStr()}`
      };
      db.waterTankers.unshift(log);
      
      newTanker.vehicleNumber = '';
      showToast('Water tanker intake logged.');
    }

    function toggleOffline() {
      isOfflineMode.value = !isOfflineMode.value;
      if (isOfflineMode.value) {
        showToast('Offline Mode Activated. Logging entries locally on browser storage...', 'warning');
      } else {
        showToast('Network online. Synchronizing local registers back to society database...', 'success');
      }
    }

    // --- SERVICEMAN WORKFLOWS ---
    function progressJob(complaintId, nextState) {
      const complaint = db.complaints.find(c => c.id === complaintId);
      if (!complaint) return;

      complaint.status = nextState;
      complaint.history.push({
        status: nextState,
        timestamp: `${new Date().toISOString().split('T')[0]} ${getCurrentTimeStr()}`,
        detail: `Status updated to ${nextState}`
      });
      showToast(`Job status updated to ${nextState}`);
    }

    function requestJobClosure(complaintId) {
      const complaint = db.complaints.find(c => c.id === complaintId);
      if (!complaint) return;
      
      const randomOTP = Math.floor(1000 + Math.random() * 9000).toString();
      complaint.closureOTP = randomOTP;
      
      showToast(`Closure requested. Resident OTP is simulated: ${randomOTP}`, 'warning');
    }

    function closeJob(complaintId, inputOTP) {
      const complaint = db.complaints.find(c => c.id === complaintId);
      if (!complaint) return;

      if (complaint.closureOTP === inputOTP) {
        complaint.status = 'Resolved';
        complaint.history.push({
          status: 'Resolved',
          timestamp: `${new Date().toISOString().split('T')[0]} ${getCurrentTimeStr()}`,
          detail: 'Resolved by serviceman. Verified via OTP.'
        });
        showToast('Job closed successfully! Resident verified.');
      } else {
        showToast('Incorrect verification OTP code.', 'danger');
      }
    }

    function markNoticeAsRead(noticeId) {
      const notice = db.notices.find(n => n.id === noticeId);
      if (notice && !notice.readBy.includes('B-1204')) {
        notice.readBy.push('B-1204');
        showToast('Notice marked as read.');
      }
    }

    function getCurrentTimeStr() {
      const d = new Date();
      let hours = d.getHours();
      let minutes = d.getMinutes();
      const ampm = hours >= 12 ? 'PM' : 'AM';
      hours = hours % 12;
      hours = hours ? hours : 12;
      minutes = minutes < 10 ? '0' + minutes : minutes;
      return `${hours}:${minutes} ${ampm}`;
    }

    // Computeds for lists & stats
    const residentNoticesCount = computed(() => {
      return db.notices.filter(n => !n.readBy.includes('B-1204')).length;
    });

    const activeComplaintsList = computed(() => {
      if (currentRole.value === 'resident') {
        return db.complaints.filter(c => c.residentFlat === 'B-1204');
      }
      return db.complaints;
    });

    const filteredComplaints = computed(() => {
      let list = db.complaints;
      if (complaintFilter.value === 'active') {
        list = list.filter(c => c.status !== 'Resolved');
      } else if (complaintFilter.value === 'resolved') {
        list = list.filter(c => c.status === 'Resolved');
      }
      return list;
    });

    const urgentComplaints = computed(() => {
      return filteredComplaints.value.filter(c => c.isStarred);
    });

    const standardComplaints = computed(() => {
      return filteredComplaints.value.filter(c => !c.isStarred);
    });

    const servicemanJobsList = computed(() => {
      return db.complaints.filter(c => c.assignedTo === selectedServicemanId.value);
    });

    const pendingBookingsList = computed(() => {
      return db.bookings.filter(b => b.status === 'Pending');
    });

    const selectedComplaint = computed(() => {
      return db.complaints.find(c => c.id === newComplaint.selectedId) || null;
    });

    return {
      currentRole,
      currentTab,
      db,
      isOfflineMode,
      toasts,
      activeModals,
      newComplaint,
      newBooking,
      newNotice,
      newVisitor,
      otpVerifyInput,
      adHocVisitorForm,
      newTanker,
      newMaterial,
      paymentProcessing,
      paymentSuccess,
      paymentTargetBooking,
      currentPushVisitor,
      selectedServicemanId,
      selectedComplaint,
      residentNoticesCount,
      activeComplaintsList,
      filteredComplaints,
      urgentComplaints,
      standardComplaints,
      servicemanJobsList,
      pendingBookingsList,

      // Wireframe state
      complaintFilter,
      selectedComplaintDetail,
      selectedAmenity,
      amenityTab,
      selectedBylaw,
      delayCauseMessage,
      blockOutForm,
      overrideBookingForm,
      rejectBookingForm,
      depositActionForm,
      bylawEditForm,
      newMeetingForm,
      newRecordForm,
      newDeptForm,

      // Functions
      switchRole,
      submitComplaint,
      submitPreApproveVisitor,
      selectBookedDates,
      triggerPaymentFlow,
      processPayment,
      assignComplaintToServiceman,
      setBookingStatus,
      cancelSpecificBookingDate,
      publishNotice,
      verifyVisitorOTP,
      submitAdHocVisitor,
      handlePushNotificationApproval,
      submitMaterialLog,
      submitTankerLog,
      toggleOffline,
      progressJob,
      requestJobClosure,
      closeJob,
      markNoticeAsRead,
      showToast,

      // Wireframe Functions
      toggleStarComplaint,
      openComplaintDetail,
      openRequestDelayCause,
      sendDelayRequest,
      openAmenityDetail,
      closeAmenityDetail,
      submitBlockOutSlot,
      submitAdminOverrideBooking,
      openRejectBookingModal,
      confirmBookingRejection,
      openDepositActionModal,
      confirmDepositAction,
      forceCancelBooking,
      selectBylaw,
      openEditBylawsModal,
      openPublishBylawsConfig,
      confirmPublishBylaws,
      submitScheduleMeeting,
      submitAddRecord,
      submitCreateDepartment
    };
  }
};

// Create and mount the application
const app = Vue.createApp(HomeBandhuApp);
app.mount('#app');
