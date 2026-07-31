DESIGN OF COMPONENTS

HomeBandhu is currently implemented as a frontend prototype using React, React
Router, Tailwind CSS, and Zustand. The application is divided into functional
components so that each major workflow can later be connected to backend APIs
without requiring substantial changes to the user interface. At the present
stage, mock data and browser storage are used in place of a backend and
database.


1. Authentication and Role-Based Access Component
   (Public Entry and Session Management)

- Provide separate entry and login flows for residents and association
  administrators.
- Support phone-number-based authentication with simulated OTP verification.
- Allow residents to activate their accounts using an invitation link or
  invitation code.
- Maintain the authenticated user session separately in each browser tab.
- Redirect authenticated users to the appropriate resident or administrator
  dashboard.
- Prevent residents from accessing administrator routes through role-based
  route guards.
- Allow administrators, who may also be residents, to switch between the
  administrator and resident interfaces.


2. Association Onboarding and Configuration Component
   (Initial Society Setup)

- Guide a new administrator through association registration using a
  multi-step onboarding flow.
- Record the association name and community type, including apartment
  complexes and villa communities.
- Configure blocks or villas and associate each unit with a location on the
  community map.
- Allow the administrator to select the functional modules required by the
  association.
- Collect the initial administrator's profile, contact information,
  designation, unit number, and profile image.
- Validate the completion of each onboarding stage before allowing access to
  the next stage.
- Create a simulated association and administrator record after OTP
  confirmation.
- Keep the onboarding workflow behind a service boundary so that it can later
  be replaced with registration APIs.


3. Resident, Administrator, and Department Management Component
   (Community Administration)

- Maintain resident and administrator records, including names, contact
  details, roles, flats, towers, and account status.
- Allow prospective residents to submit access requests for administrator
  review.
- Enable administrators to approve or reject pending registration requests.
- Create a resident account and an initial maintenance invoice when a
  registration request is approved.
- Allow administrators to add, edit, remove, and invite residents.
- Support multiple phone numbers belonging to the same apartment or household.
- Generate time-limited, single-use invitations that residents can redeem
  using a link or code.
- Allow administrators to add other association administrators.
- Maintain departments with contact details, department heads, staff members,
  operating hours, complaint categories, and service-level targets.
- Prevent a department from being deleted while it is responsible for
  unresolved complaints.


4. Resident Portal Component
   (Resident Self-Service Interface)

- Provide residents with a dedicated dashboard and navigation layout separate
  from the administrator portal.
- Display a summary of maintenance dues, visitors, complaints, notices,
  bookings, and recent activity.
- Provide direct access to visitor pre-approval, complaint submission, amenity
  booking, payments, notices, help, and profile management.
- Allow residents to review the current state and history of their submitted
  requests.
- Allow a resident to add another phone number to the same apartment.
- Present management contact information and frequently asked questions.
- Use responsive navigation so that the portal remains usable on desktop and
  mobile devices.


5. Visitor and Gate Access Component
   (Pre-Approval and Pass Management)

- Allow residents to pre-approve individual visitors or groups before their
  expected arrival.
- Record the purpose, date, time, number of guests, resident flat, and other
  visit details.
- Generate a structured QR pass and a short access code for the visitor group.
- Display expected visitors and their current entry status.
- Record when an approved visitor or group is checked in.
- Add visitor-related actions to the resident's recent-activity history.
- Provide the frontend foundation for a future security interface that can
  verify passes at the gate.
- Keep offline verification, material registers, tanker logs, and long-term
  security reports as planned extensions beyond the current prototype.


6. Complaint and Service Resolution Component
   (Tracking and Accountability)

- Allow residents to submit complaints with a title, description, category,
  urgency, location, and supporting attachments.
- Assign an expected resolution time according to the selected urgency level.
- Maintain a timestamped complaint timeline beginning from the original
  submission.
- Allow administrators to assign complaints to responsible personnel or
  departments.
- Track complaint status, progress, assignee, management notes, and unread
  updates.
- Support comments between residents and the management team.
- Allow residents to reopen a complaint when the reported issue remains
  unresolved.
- Allow residents to confirm a resolution and provide a rating and feedback.
- Connect complaint categories with the appropriate department and its
  service-level target.
- Reflect complaint updates across resident and administrator browser tabs
  through shared application state.


7. Notice and Community Communication Component
   (Announcements and Updates)

- Allow administrators to publish society notices and announcements.
- Classify notices using categories and urgency levels.
- Record the publication date and display notices in the resident portal.
- Provide residents with a central place to review important association
  updates.
- Generate in-application confirmation messages when notices or other records
  are created or updated.
- Record significant actions in a shared activity feed for improved
  visibility.
- Reserve external push notifications and message-delivery services for future
  backend integration.


8. Amenities and Booking Management Component
   (Facility Scheduling and Administration)

- Allow residents to browse available amenities and review their descriptions,
  operating hours, capacity, and availability.
- Support single-day and multi-day amenity bookings.
- Validate booking dates and time slots before creating a reservation.
- Allow residents to cancel selected dates from a multi-day booking without
  cancelling the entire booking.
- Allow administrators to create, update, activate, deactivate, or remove
  amenities.
- Configure booking modes, capacity limits, approval requirements, private
  bookings, cleaning buffers, and resident booking limits.
- Display bookings through an administrative timeline and calendar-oriented
  interface.
- Allow administrators to create bookings, block maintenance periods, edit
  reservations, and cancel bookings.
- Provide approval and rejection workflows for bookings that require
  administrator authorization.
- Keep amenity services separate from pages and components so that browser
  persistence can later be replaced by API calls.


9. Payment, Ledger, and Reporting Component
   (Financial Tracking)

- Display resident maintenance invoices with their amount, due date, billing
  period, and payment status.
- Allow residents to simulate payment using a selected payment method.
- Mark successful payments as paid and record the payment date and method.
- Allow administrators to review paid and unpaid maintenance records.
- Maintain an amenity financial ledger containing booking charges, payments,
  deposits, deductions, and refunds.
- Support deposit refunds, damage deductions, and forced booking
  cancellations.
- Synchronize booking cancellations with their corresponding amenity financial
  records.
- Generate filtered amenity reports containing revenue, active bookings,
  pending approvals, active amenities, and monthly booking counts.
- Use simulated transactions only; no real payment gateway is connected in the
  current milestone.


10. Application State, Persistence, and Synchronization Component
    (Shared Frontend Data Layer)

- Store the principal domain collections in modular Zustand slices, including
  users, invitations, registration requests, complaints, departments, notices,
  visitors, amenities, bookings, payments, activities, and notifications.
- Seed the frontend with structured mock data maintained separately from the
  user-interface components.
- Persist shared domain data in browser localStorage so that changes remain
  available after a page reload.
- Persist authentication in sessionStorage so that different tabs can maintain
  independent resident and administrator sessions.
- Listen for browser storage events and rehydrate the shared application state
  when another tab makes a change.
- Provide global toast notifications and an activity feed for important user
  and administrator actions.
- Separate complex amenity workflows into pages, components, stores, services,
  validation utilities, and persistence modules.
- Preserve service boundaries that can later be connected to backend APIs and
  a database without redesigning the frontend pages.


COMPONENT INTERACTION

The public authentication and onboarding components provide entry into the
system. After authentication, React Router directs the user to either the
resident or administrator layout. Pages interact with domain-specific Zustand
stores or service modules, which apply the required business rules and update
the shared state. The persistence layer stores these changes in the browser,
while cross-tab synchronization makes relevant updates visible in other active
sessions. This organization keeps presentation, workflow logic, shared state,
and persistence responsibilities separated and prepares the prototype for
future backend integration.
