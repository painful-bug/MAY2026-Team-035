# AGENTS.md

# HomeBandhu - AI Agent Instructions

Welcome to the HomeBandhu codebase.

This document contains the engineering rules and architectural decisions that every AI coding agent must follow while contributing to this repository.

These instructions override default assumptions.

---

# Project Overview

HomeBandhu is a modern Apartment & Residential Community Management Platform.

The project supports:

- Apartment Associations
- Residential Layouts
- Villa Communities
- Gated Communities

Current Phase:

Frontend Prototype (Milestone 1)

Backend is NOT implemented yet.

The objective is to build a scalable frontend that can later integrate with APIs without major refactoring.

---

# Technology Stack

Framework
- React 19

Build Tool
- Vite

Routing
- React Router DOM

Styling
- Tailwind CSS

Icons
- Lucide React

Global State
- Zustand

Component State
- React useState

Mock Data
- JavaScript JSON

HTTP (Future)
- Axios

Backend (Future)
- Node.js
- Express.js
- PostgreSQL
- Prisma ORM
- JWT Authentication

---

# Development Philosophy

Always think long-term.

Even if a feature currently uses mock data, structure the code exactly as it would exist in production.

Avoid shortcuts that will make backend integration difficult.

Every screen should be backend-ready.

---

# Current Development Stage

Frontend only.

Do NOT implement:

- Backend
- Express
- Node APIs
- Firebase
- Supabase
- Database
- Authentication server
- JWT implementation
- Axios calls

Use mock JSON and Zustand instead.

---

# Architecture Rules

Always follow this structure.

src/

assets/

components/

common/

cards/

forms/

layout/

pages/

layouts/

routes/

stores/

data/

hooks/

services/

utils/

Never place business logic inside UI components.

---

# State Management

Use Zustand for:

- Logged-in user
- Authentication state
- Current association
- Sidebar state
- Theme
- Notifications
- Dashboard state
- Global application state

Use useState for:

- Forms
- Modals
- Search
- Dropdowns
- Local UI

Avoid unnecessary Context API.

---

# Mock Data Rules

All data must come from

src/data/

Never hardcode arrays inside components.

Example

users.js

complaints.js

residents.js

admins.js

notices.js

association.js

Every mock file should represent a future database table.

---

# Routing Rules

Resident Portal

/

Admin Portal

/admin

These are separate experiences.

Do not merge them.

Admins are also residents.

After login,

Admins first enter the Resident Dashboard.

Resident Dashboard contains

"Switch to Admin Dashboard"

This changes routes only.

---

# Admin Registration Flow

Current implementation:

Frontend only.

Future implementation:

Phone Number

↓

OTP Verification

↓

Association Registration

↓

Map Configuration

↓

Feature Configuration

↓

Admin Profile

↓

Dashboard

Store onboarding state in Zustand.

---

# Resident Registration

Residents cannot directly join.

Flow

Resident submits registration request.

↓

Pending Requests

↓

Admin approves/rejects

↓

Resident becomes active

Currently simulate this with mock JSON.

---

# UI Design Guidelines

Design language:

Minimal

Modern

Professional

Premium SaaS

Rounded corners

Large spacing

Soft shadows

Accessible

Responsive

Reusable components

Do not clutter interfaces.

---

# Component Rules

Components should be:

Small

Reusable

Single responsibility

Composable

Avoid files larger than approximately 300 lines when possible.

Extract repeated UI into reusable components.

---

# Naming Conventions

Pages

LoginPage.jsx

AdminDashboard.jsx

ResidentDashboard.jsx

Components

DashboardCard.jsx

Sidebar.jsx

Header.jsx

NoticeCard.jsx

Hooks

useAuth.js

Stores

authStore.js

Utilities

formatDate.js

---

# Future Backend Integration

Every feature should assume future APIs.

Example

Current

Mock JSON

Future

Axios

↓

Express API

↓

Database

UI components should not need major changes.

---

# Future Database Entities

Association

Resident

Admin

Building

Block

Flat

Visitor

Complaint

Notice

Maintenance

Amenity

Booking

Payment

Parking

SecurityStaff

FeatureFlags

Design the frontend with these entities in mind.

---

# Code Style

Use

Functional Components

ES Modules

Arrow Functions

Tailwind CSS

Reusable Hooks

Reusable Cards

Meaningful names

Avoid anonymous functions where readability suffers.

---

# Things To Avoid

Do NOT

- Introduce Redux
- Introduce Material UI
- Introduce Bootstrap
- Hardcode mock data in components
- Write backend code
- Duplicate components
- Change project architecture without reason

---

# AI Expectations

Before creating any new feature:

Understand the existing architecture.

Reuse existing components.

Reuse Zustand stores where appropriate.

Maintain visual consistency.

Maintain naming conventions.

Maintain folder structure.

Always think about future backend integration.

Do not rewrite working code unless necessary.

When making changes, preserve scalability, readability, and maintainability.

Every contribution should make the codebase easier—not harder—to extend.