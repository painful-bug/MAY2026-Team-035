# Implemented Flows

HomeBandhu is currently implemented as a frontend-first React app. The backend is planned for a later phase. For now, domain data is stored in a Zustand store persisted to browser storage, while authentication is simulated.

This document lists the user-facing flows currently implemented on the `dev` branch. Each flow is intentionally kept separate so it can be reviewed, tested, and later mapped to backend APIs independently.

## Storage Model

- Domain data is stored in `localStorage` through the app Zustand store.
- The current logged-in user is stored in `sessionStorage` through the auth Zustand store.
- App data is rehydrated across tabs using the browser `storage` event.
- OTP, payments, and invite delivery are simulated in the frontend.

```mermaid
flowchart TD
  UI[React UI] --> Actions[Zustand Actions]
  Actions --> DomainStore[App Store]
  Actions --> AuthStore[Auth Store]
  DomainStore --> LocalStorage[localStorage]
  AuthStore --> SessionStorage[sessionStorage]
  LocalStorage --> CrossTab[Cross-tab Rehydration]
  CrossTab --> UI
```

## Public: Login With OTP

**Actor:** Resident or Admin  
**Entry point:** `/login`  
**State touched:** `currentUser`

```mermaid
flowchart TD
  A[User opens login page] --> B[Enters phone number]
  B --> C[Requests OTP]
  C --> D[App shows simulated OTP prompt]
  D --> E[User enters any 4 to 6 digit OTP]
  E --> F{Phone matches known user?}
  F -->|Resident| G[Set currentUser]
  G --> H[Navigate to resident dashboard]
  F -->|Admin| I[Set currentUser]
  I --> J[Navigate to admin dashboard]
  F -->|No match| K[Show invalid credentials error]
```

**Notes**

- OTP validation is simulated.
- Demo resident and admin phone numbers are supported.
- Login state is per tab because it uses `sessionStorage`.

## Public: Submit Access Request

**Actor:** New resident  
**Entry point:** `/signup`  
**State touched:** `pendingRequests`

```mermaid
flowchart TD
  A[New resident opens signup page] --> B[Enters name, email, phone, tower, flat, password]
  B --> C{Form valid?}
  C -->|No| D[Show validation error]
  C -->|Yes| E[Create pending registration request]
  E --> F[Show submitted confirmation]
  F --> G[Wait for admin approval]
```

**Notes**

- Password is collected by the form but is not used for real authentication yet.
- Approval is handled by an admin from the admin dashboard.

## Public: Join With Invite Link

**Actor:** Invited resident  
**Entry point:** `/join/:token`  
**State touched:** `users`, `invitations`, `currentUser`, `activities`

```mermaid
flowchart TD
  A[Resident opens invite link] --> B[App reads token from URL]
  B --> C{Token valid?}
  C -->|Invalid| D[Show invalid invite message]
  C -->|Expired| E[Show expired invite message]
  C -->|Already used| F[Show already used message]
  C -->|Valid| G[Activate users for the flat]
  G --> H[Mark invite as used]
  H --> I[Set currentUser]
  I --> J[Navigate to resident dashboard]
```

**Notes**

- Invite tokens are opaque and single-use.
- Redeeming one invite activates all invited users for that flat.

## Public: Join With Invite Code

**Actor:** Invited resident  
**Entry point:** `/login` invite mode  
**State touched:** `users`, `invitations`, `currentUser`, `activities`

```mermaid
flowchart TD
  A[Resident opens login page] --> B[Switches to invite code mode]
  B --> C[Enters phone number and invite code]
  C --> D{Invite can be redeemed?}
  D -->|No| E[Show invite error]
  D -->|Yes| F[Activate users for the flat]
  F --> G[Mark invite as used]
  G --> H[Set currentUser]
  H --> I[Navigate to resident dashboard]
```

## Resident: Pre-Approve Visitor

**Actor:** Resident  
**Entry point:** `/resident/visitors`  
**State touched:** `visitors`, `activities`

```mermaid
flowchart TD
  A[Resident opens visitors page] --> B[Enters visitor name, phone, purpose, date, and time]
  B --> C[Submits pre-approval]
  C --> D[Create visitor entry]
  D --> E[Generate gate code]
  E --> F[Show success toast with code]
  F --> G[Add activity feed entry]
```

**Notes**

- Gate codes are generated on the frontend.

## Resident: Raise Complaint

**Actor:** Resident  
**Entry point:** `/resident/complaints`  
**State touched:** `complaints`, `activities`

```mermaid
flowchart TD
  A[Resident opens complaints page] --> B[Enters title, category, urgency, and description]
  B --> C{Required fields present?}
  C -->|No| D[Do not submit]
  C -->|Yes| E[Create complaint]
  E --> F[Set status to Pending]
  F --> G[Show success toast]
  G --> H[Add activity feed entry]
  H --> I[Complaint appears in resident and admin views]
```

## Resident: Book Amenity

**Actor:** Resident  
**Entry point:** `/resident/amenities`  
**State touched:** `bookings`, `activities`

```mermaid
flowchart TD
  A[Resident opens amenities page] --> B[Selects an amenity]
  B --> C[Chooses date and time slot]
  C --> D[Submits booking]
  D --> E[Create confirmed booking]
  E --> F[Show success toast]
  F --> G[Add activity feed entry]
```

## Resident: Pay Maintenance Invoice

**Actor:** Resident  
**Entry point:** `/resident/payments`  
**State touched:** `payments`, `activities`

```mermaid
flowchart TD
  A[Resident opens payments page] --> B[Selects unpaid invoice]
  B --> C[Chooses payment method]
  C --> D[Confirms payment]
  D --> E[Mark invoice as Paid]
  E --> F[Set paid date and payment method]
  F --> G[Show payment success toast]
  G --> H[Add activity feed entry]
```

**Notes**

- Payment processing is simulated.

## Resident: View Notices

**Actor:** Resident  
**Entry point:** `/resident/notices`  
**State touched:** Read-only `notices`

```mermaid
flowchart TD
  A[Resident opens notices page] --> B[App reads notices]
  B --> C[Display society notices]
  C --> D[Resident reviews notice details]
```

## Resident: Add Phone Number To Flat

**Actor:** Resident  
**Entry point:** `/resident/profile`  
**State touched:** `users`, `activities`

```mermaid
flowchart TD
  A[Resident opens profile page] --> B[Views numbers registered to flat]
  B --> C[Enters optional name and phone number]
  C --> D[Submits new number]
  D --> E[Create active resident user for same flat]
  E --> F[Show success toast]
  F --> G[Add activity feed entry]
```

## Admin: Review Pending Registration

**Actor:** Admin  
**Entry point:** `/admin/pending`  
**State touched:** `pendingRequests`, `users`, `payments`, `activities`

```mermaid
flowchart TD
  A[Admin opens pending registrations] --> B[Reviews resident request]
  B --> C{Approve or reject?}
  C -->|Reject| D[Remove request]
  D --> E[Show rejection toast]
  C -->|Approve| F[Create resident user]
  F --> G[Create default unpaid maintenance invoice]
  G --> H[Remove pending request]
  H --> I[Show approval toast]
  I --> J[Add activity feed entry]
```

## Admin: Invite Resident

**Actor:** Admin  
**Entry point:** `/admin/residents`  
**State touched:** `users`, `invitations`, `activities`

```mermaid
flowchart TD
  A[Admin opens residents page] --> B[Clicks Add Resident]
  B --> C[Enters name, email, tower, flat, and phone numbers]
  C --> D{Form valid?}
  D -->|No| E[Stay on form]
  D -->|Yes| F[Create invited user records]
  F --> G[Create single-use invite token]
  G --> H[Show invite link and invite code]
  H --> I[Admin copies and shares invite]
```

**Notes**

- One invite can cover multiple phone numbers for the same flat.
- Created users start with `Invited` status.

## Admin: Edit Or Remove Resident

**Actor:** Admin  
**Entry point:** `/admin/residents`  
**State touched:** `users`, `activities`

```mermaid
flowchart TD
  A[Admin opens residents page] --> B[Searches resident list]
  B --> C{Choose action}
  C -->|Edit| D[Update resident details]
  D --> E[Save updated user record]
  E --> F[Show success toast]
  C -->|Remove| G[Confirm removal]
  G --> H[Delete resident record]
  H --> I[Show removal toast]
  F --> J[Add activity feed entry]
  I --> J
```

## Admin: Add Admin

**Actor:** Admin  
**Entry point:** `/admin/admins`  
**State touched:** `users`, `activities`

```mermaid
flowchart TD
  A[Admin opens admins page] --> B[Clicks add admin]
  B --> C[Enters admin details]
  C --> D[Create admin user]
  D --> E[Show success toast]
  E --> F[Add activity feed entry]
```

## Admin: Manage Amenities

**Actor:** Admin  
**Entry point:** `/admin/amenities`  
**State touched:** `amenities`, `activities`

```mermaid
flowchart TD
  A[Admin opens amenities management] --> B{Choose action}
  B -->|Add| C[Create amenity]
  B -->|Edit| D[Update amenity details]
  B -->|Delete| E[Remove amenity]
  B -->|Toggle hold| F[Switch availability status]
  C --> G[Show toast]
  D --> G
  E --> G
  F --> G
  G --> H[Add activity feed entry]
```

## Admin: Post Notice

**Actor:** Admin  
**Entry point:** `/admin/notices`  
**State touched:** `notices`, `activities`

```mermaid
flowchart TD
  A[Admin opens notices board] --> B[Clicks new notice]
  B --> C[Enters title, description, urgency, and category]
  C --> D[Posts notice]
  D --> E[Create notice record]
  E --> F[Show success toast]
  F --> G[Add activity feed entry]
  G --> H[Notice appears for residents]
```

## Admin: Update Complaint

**Actor:** Admin  
**Entry point:** `/admin/complaints`  
**State touched:** `complaints`, `activities`

```mermaid
flowchart TD
  A[Admin opens complaints management] --> B[Filters complaints by status]
  B --> C[Clicks Update on complaint]
  C --> D[Changes assignee, status, or progress]
  D --> E[Saves changes]
  E --> F[Update complaint record]
  F --> G[Show success toast]
  G --> H{Status changed?}
  H -->|Yes| I[Add activity feed entry]
  H -->|No| J[No status activity added]
  I --> K[Resident sees updated complaint]
  J --> K
```

## Admin: View Maintenance Payments

**Actor:** Admin  
**Entry point:** `/admin/maintenance`  
**State touched:** Read-only `payments`

```mermaid
flowchart TD
  A[Admin opens maintenance payments] --> B[App reads payment records]
  B --> C[Display paid and unpaid invoices]
  C --> D[Admin reviews collection status]
```

## Admin: View Dashboard

**Actor:** Admin  
**Entry point:** `/admin`  
**State touched:** Read-only dashboard collections

```mermaid
flowchart TD
  A[Admin opens dashboard] --> B[Read residents, pending requests, complaints, payments, and activities]
  B --> C[Calculate summary metrics]
  C --> D[Display dashboard cards and recent activity]
```

## Resident: View Dashboard

**Actor:** Resident  
**Entry point:** `/resident`  
**State touched:** Read-only dashboard collections

```mermaid
flowchart TD
  A[Resident opens dashboard] --> B[Read notices, visitors, complaints, payments, bookings, and activities]
  B --> C[Calculate resident summary]
  C --> D[Display cards, recent activity, dues, visitors, and notices]
```

## Future Backend Mapping

When backend work begins, the frontend actions in this document can be mapped to API endpoints. Examples:

- Login and OTP flows can map to authentication endpoints.
- Registration requests can map to resident onboarding endpoints.
- Invite creation and redemption can move from browser storage to server-side validation.
- Complaints, visitors, payments, notices, amenities, and users can become persisted database-backed resources.
- Cross-tab browser sync can later be complemented or replaced by API refetching, WebSocket updates, or server-sent events.
