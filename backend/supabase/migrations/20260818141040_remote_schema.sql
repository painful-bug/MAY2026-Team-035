drop extension if exists "pg_net";

create type "public"."media_status" as enum ('pending', 'active', 'quarantined', 'deleted');

create type "public"."request_status" as enum ('pending', 'approved', 'rejected', 'cancelled');

create type "public"."user_role" as enum ('RESIDENT', 'MANAGER', 'TECHNICIAN', 'SECURITY', 'ADMIN');

drop trigger if exists "dashboard_sse_amenity_bookings" on "public"."amenity_bookings";

drop trigger if exists "dashboard_sse_visitor_requests" on "public"."visitor_requests";

drop trigger if exists "access_request_sse" on "public"."access_requests";

drop trigger if exists "dashboard_sse_access_requests" on "public"."access_requests";

drop trigger if exists "amenities_sse" on "public"."amenities";

drop trigger if exists "amenities_sync_status" on "public"."amenities";

drop trigger if exists "dashboard_sse_amenities" on "public"."amenities";

drop trigger if exists "amenity_bookings_sse" on "public"."amenity_bookings";

drop trigger if exists "community_billing_settings_set_updated_at" on "public"."community_billing_settings";

drop trigger if exists "dashboard_sse_community_billing_settings" on "public"."community_billing_settings";

drop trigger if exists "community_memberships_professional_mode" on "public"."community_memberships";

drop trigger if exists "dashboard_sse_community_memberships" on "public"."community_memberships";

drop trigger if exists "community_settings_set_updated_at" on "public"."community_settings";

drop trigger if exists "dashboard_sse_community_settings" on "public"."community_settings";

drop trigger if exists "complaint_categories_link_skill" on "public"."complaint_categories";

drop trigger if exists "complaint_comments_sse" on "public"."complaint_comments";

drop trigger if exists "complaints_department_live_work_guard" on "public"."complaints";

drop trigger if exists "complaints_on_resolved" on "public"."complaints";

drop trigger if exists "complaints_sse" on "public"."complaints";

drop trigger if exists "dashboard_sse_complaints" on "public"."complaints";

drop trigger if exists "dashboard_sse_departments" on "public"."departments";

drop trigger if exists "departments_sse" on "public"."departments";

drop trigger if exists "departments_sync_status" on "public"."departments";

drop trigger if exists "dashboard_sse_invoices" on "public"."invoices";

drop trigger if exists "invoices_sse" on "public"."invoices";

drop trigger if exists "dashboard_sse_notices" on "public"."notices";

drop trigger if exists "notices_notify_residents" on "public"."notices";

drop trigger if exists "notifications_sse_event" on "public"."notifications";

drop trigger if exists "dashboard_sse_payments" on "public"."payments";

drop trigger if exists "payments_sse" on "public"."payments";

drop trigger if exists "security_shifts_block_departing" on "public"."security_shifts";

drop trigger if exists "service_applications_notify_invited" on "public"."service_applications";

drop trigger if exists "service_applications_notify_rejected" on "public"."service_applications";

drop trigger if exists "service_applications_set_updated_at" on "public"."service_applications";

drop trigger if exists "service_providers_set_updated_at" on "public"."service_providers";

drop trigger if exists "staff_assignments_sse" on "public"."staff_assignments";

drop trigger if exists "work_order_assignments_block_departing" on "public"."work_order_assignments";

drop trigger if exists "work_order_assignments_open_chat" on "public"."work_order_assignments";

drop trigger if exists "work_order_assignments_project_complaint" on "public"."work_order_assignments";

drop trigger if exists "work_orders_clear_complaint_pool_flag" on "public"."work_orders";

drop trigger if exists "work_orders_lock_dm_threads" on "public"."work_orders";

drop trigger if exists "work_orders_project_complaint" on "public"."work_orders";

drop trigger if exists "work_orders_set_updated_at" on "public"."work_orders";

drop trigger if exists "work_orders_sync_dispatch" on "public"."work_orders";

drop trigger if exists "work_orders_terminal_complaint_guard" on "public"."work_orders";

drop policy "access_requests_admin_read" on "public"."access_requests";

drop policy "access_requests_applicant_read" on "public"."access_requests";

drop policy "communities_member" on "public"."communities";

drop policy "memberships_self" on "public"."community_memberships";

drop policy "profiles_self" on "public"."profiles";

drop policy "invites_admin" on "public"."resident_invites";

drop policy "units_member" on "public"."units";

drop policy "amenity_booking_charges_read" on "public"."amenity_booking_charges";

drop policy "amenity_booking_guests_read" on "public"."amenity_booking_guests";

drop policy "amenity_bookings_admin_write" on "public"."amenity_bookings";

drop policy "amenity_bookings_read" on "public"."amenity_bookings";

drop policy "amenity_financial_events_read" on "public"."amenity_financial_events";

drop policy "blacklisted_providers_read" on "public"."blacklisted_service_providers";

drop policy "communities_service_application_read" on "public"."communities";

drop policy "billing_settings_admin_write" on "public"."community_billing_settings";

drop policy "billing_settings_member_read" on "public"."community_billing_settings";

drop policy "community_settings_admin_write" on "public"."community_settings";

drop policy "community_settings_member_read" on "public"."community_settings";

drop policy "complaint_categories_read" on "public"."complaint_categories";

drop policy "complaint_categories_write" on "public"."complaint_categories";

drop policy "complaint_comments_read" on "public"."complaint_comments";

drop policy "complaint_department_requests_read" on "public"."complaint_department_requests";

drop policy "complaint_events_read" on "public"."complaint_events";

drop policy "complaint_read_state_read" on "public"."complaint_read_state";

drop policy "complaints_read" on "public"."complaints";

drop policy "conversation_messages_read" on "public"."conversation_messages";

drop policy "conversations_read" on "public"."conversations";

drop policy "department_categories_read" on "public"."department_categories";

drop policy "department_categories_write" on "public"."department_categories";

drop policy "department_skills_read" on "public"."department_skills";

drop policy "departments_admin_write" on "public"."departments";

drop policy "departments_read" on "public"."departments";

drop policy "departments_service_application_read" on "public"."departments";

drop policy "dm_messages_read" on "public"."dm_messages";

drop policy "invoice_line_items_read" on "public"."invoice_line_items";

drop policy "invoices_admin_write" on "public"."invoices";

drop policy "invoices_read" on "public"."invoices";

drop policy "material_movements_read" on "public"."material_movements";

drop policy "notices_admin_write" on "public"."notices";

drop policy "notices_read" on "public"."notices";

drop policy "offline_reconcile_log_read" on "public"."offline_reconcile_log";

drop policy "payment_events_read" on "public"."payment_events";

drop policy "payments_read" on "public"."payments";

drop policy "security_incidents_read" on "public"."security_incidents";

drop policy "security_posts_read" on "public"."security_posts";

drop policy "security_shifts_read" on "public"."security_shifts";

drop policy "service_applications_read" on "public"."service_applications";

drop policy "staff_assignments_admin_write" on "public"."staff_assignments";

drop policy "staff_assignments_read" on "public"."staff_assignments";

drop policy "staff_departures_read" on "public"."staff_departures";

drop policy "staff_invitations_read" on "public"."staff_invitations";

drop policy "unit_contacts_read" on "public"."unit_contacts";

drop policy "unit_residencies_read" on "public"."unit_residencies";

drop policy "visitor_events_read" on "public"."visitor_events";

drop policy "visitor_requests_read" on "public"."visitor_requests";

drop policy "water_tanker_logs_read" on "public"."water_tanker_logs";

drop policy "work_order_assignments_read" on "public"."work_order_assignments";

drop policy "work_orders_read" on "public"."work_orders";

drop policy "worker_availability_rules_read" on "public"."worker_availability_rules";

drop policy "worker_unavailability_read" on "public"."worker_unavailability";

revoke references on table "public"."amenity_maintenance_blocks" from "anon";

revoke trigger on table "public"."amenity_maintenance_blocks" from "anon";

revoke truncate on table "public"."amenity_maintenance_blocks" from "anon";

revoke references on table "public"."amenity_maintenance_blocks" from "authenticated";

revoke trigger on table "public"."amenity_maintenance_blocks" from "authenticated";

revoke truncate on table "public"."amenity_maintenance_blocks" from "authenticated";

revoke delete on table "public"."amenity_maintenance_blocks" from "service_role";

revoke insert on table "public"."amenity_maintenance_blocks" from "service_role";

revoke references on table "public"."amenity_maintenance_blocks" from "service_role";

revoke select on table "public"."amenity_maintenance_blocks" from "service_role";

revoke trigger on table "public"."amenity_maintenance_blocks" from "service_role";

revoke truncate on table "public"."amenity_maintenance_blocks" from "service_role";

revoke update on table "public"."amenity_maintenance_blocks" from "service_role";

revoke references on table "public"."amenity_operating_hours" from "anon";

revoke trigger on table "public"."amenity_operating_hours" from "anon";

revoke truncate on table "public"."amenity_operating_hours" from "anon";

revoke references on table "public"."amenity_operating_hours" from "authenticated";

revoke trigger on table "public"."amenity_operating_hours" from "authenticated";

revoke truncate on table "public"."amenity_operating_hours" from "authenticated";

revoke delete on table "public"."amenity_operating_hours" from "service_role";

revoke insert on table "public"."amenity_operating_hours" from "service_role";

revoke references on table "public"."amenity_operating_hours" from "service_role";

revoke select on table "public"."amenity_operating_hours" from "service_role";

revoke trigger on table "public"."amenity_operating_hours" from "service_role";

revoke truncate on table "public"."amenity_operating_hours" from "service_role";

revoke update on table "public"."amenity_operating_hours" from "service_role";

revoke references on table "public"."idempotency_records" from "anon";

revoke trigger on table "public"."idempotency_records" from "anon";

revoke truncate on table "public"."idempotency_records" from "anon";

revoke references on table "public"."idempotency_records" from "authenticated";

revoke trigger on table "public"."idempotency_records" from "authenticated";

revoke truncate on table "public"."idempotency_records" from "authenticated";

revoke delete on table "public"."idempotency_records" from "service_role";

revoke insert on table "public"."idempotency_records" from "service_role";

revoke references on table "public"."idempotency_records" from "service_role";

revoke select on table "public"."idempotency_records" from "service_role";

revoke trigger on table "public"."idempotency_records" from "service_role";

revoke truncate on table "public"."idempotency_records" from "service_role";

revoke update on table "public"."idempotency_records" from "service_role";

revoke references on table "public"."media" from "anon";

revoke trigger on table "public"."media" from "anon";

revoke truncate on table "public"."media" from "anon";

revoke references on table "public"."media" from "authenticated";

revoke trigger on table "public"."media" from "authenticated";

revoke truncate on table "public"."media" from "authenticated";

revoke delete on table "public"."media" from "service_role";

revoke insert on table "public"."media" from "service_role";

revoke references on table "public"."media" from "service_role";

revoke select on table "public"."media" from "service_role";

revoke trigger on table "public"."media" from "service_role";

revoke truncate on table "public"."media" from "service_role";

revoke update on table "public"."media" from "service_role";

revoke references on table "public"."member_activity" from "anon";

revoke trigger on table "public"."member_activity" from "anon";

revoke truncate on table "public"."member_activity" from "anon";

revoke references on table "public"."member_activity" from "authenticated";

revoke trigger on table "public"."member_activity" from "authenticated";

revoke truncate on table "public"."member_activity" from "authenticated";

revoke delete on table "public"."member_activity" from "service_role";

revoke insert on table "public"."member_activity" from "service_role";

revoke references on table "public"."member_activity" from "service_role";

revoke select on table "public"."member_activity" from "service_role";

revoke trigger on table "public"."member_activity" from "service_role";

revoke truncate on table "public"."member_activity" from "service_role";

revoke update on table "public"."member_activity" from "service_role";

revoke references on table "public"."rate_limit_buckets" from "anon";

revoke trigger on table "public"."rate_limit_buckets" from "anon";

revoke truncate on table "public"."rate_limit_buckets" from "anon";

revoke references on table "public"."rate_limit_buckets" from "authenticated";

revoke trigger on table "public"."rate_limit_buckets" from "authenticated";

revoke truncate on table "public"."rate_limit_buckets" from "authenticated";

revoke delete on table "public"."rate_limit_buckets" from "service_role";

revoke insert on table "public"."rate_limit_buckets" from "service_role";

revoke references on table "public"."rate_limit_buckets" from "service_role";

revoke select on table "public"."rate_limit_buckets" from "service_role";

revoke trigger on table "public"."rate_limit_buckets" from "service_role";

revoke truncate on table "public"."rate_limit_buckets" from "service_role";

revoke update on table "public"."rate_limit_buckets" from "service_role";

alter table "public"."access_requests" drop constraint "access_requests_check";

alter table "public"."access_requests" drop constraint "access_requests_rejection_reason_check";

alter table "public"."access_requests" drop constraint "access_requests_status_check";

alter table "public"."amenity_booking_charges" drop constraint "amenity_booking_charges_amount_check";

alter table "public"."amenity_booking_charges" drop constraint "amenity_booking_charges_booking_occurrence_id_fkey";

alter table "public"."amenity_financial_events" drop constraint "amenity_financial_events_actor_membership_id_fkey";

alter table "public"."amenity_maintenance_blocks" drop constraint "amenity_maintenance_blocks_amenity_id_fkey";

alter table "public"."amenity_operating_hours" drop constraint "amenity_operating_hours_amenity_id_fkey";

alter table "public"."buildings" drop constraint "buildings_community_id_code_key";

alter table "public"."buildings" drop constraint "buildings_community_id_fkey";

alter table "public"."communities" drop constraint "communities_active_admin_membership_id_fkey";

alter table "public"."communities" drop constraint "communities_community_type_check";

alter table "public"."communities" drop constraint "communities_country_code_check";

alter table "public"."communities" drop constraint "communities_status_check";

alter table "public"."community_admin_terms" drop constraint "community_admin_terms_designation_check";

alter table "public"."community_features" drop constraint "community_features_updated_by_membership_id_fkey";

alter table "public"."departments" drop constraint "departments_manager_membership_id_fkey";

alter table "public"."idempotency_records" drop constraint "idempotency_records_community_id_fkey";

alter table "public"."media" drop constraint "media_community_id_fkey";

alter table "public"."media" drop constraint "media_storage_path_key";

alter table "public"."media" drop constraint "media_uploaded_by_membership_id_fkey";

alter table "public"."member_activity" drop constraint "member_activity_community_id_fkey";

alter table "public"."member_activity" drop constraint "member_activity_membership_id_fkey";

alter table "public"."notifications" drop constraint "notifications_recipient_membership_id_fkey";

alter table "public"."payments" drop constraint "payments_community_id_idempotency_key_key";

alter table "public"."resident_invites" drop constraint "resident_invites_code_hash_key";

alter table "public"."resident_invites" drop constraint "resident_invites_community_id_fkey";

alter table "public"."resident_invites" drop constraint "resident_invites_token_hash_key";

alter table "public"."units" drop constraint "units_building_id_fkey";

alter table "public"."units" drop constraint "units_community_id_fkey";

alter table "public"."units" drop constraint "units_community_id_unit_code_key";

alter table "public"."visitor_events" drop constraint "visitor_events_actor_membership_id_fkey";

alter table "public"."access_requests" drop constraint "access_requests_applicant_profile_id_fkey";

alter table "public"."access_requests" drop constraint "access_requests_community_id_fkey";

alter table "public"."access_requests" drop constraint "access_requests_requested_unit_id_fkey";

alter table "public"."access_requests" drop constraint "access_requests_reviewed_by_membership_id_fkey";

alter table "public"."amenities" drop constraint "amenities_community_id_fkey";

alter table "public"."amenity_booking_charges" drop constraint "amenity_booking_charges_community_id_fkey";

alter table "public"."amenity_booking_guests" drop constraint "amenity_booking_guests_community_id_fkey";

alter table "public"."amenity_bookings" drop constraint "amenity_bookings_amenity_id_fkey";

alter table "public"."amenity_bookings" drop constraint "amenity_bookings_amenity_id_tstzrange_excl";

alter table "public"."amenity_bookings" drop constraint "amenity_bookings_booked_by_membership_id_fkey";

alter table "public"."amenity_bookings" drop constraint "amenity_bookings_community_id_fkey";

alter table "public"."amenity_bookings" drop constraint "amenity_bookings_unit_id_fkey";

alter table "public"."amenity_financial_events" drop constraint "amenity_financial_events_booking_charge_id_fkey";

alter table "public"."amenity_financial_events" drop constraint "amenity_financial_events_community_id_fkey";

alter table "public"."audit_events" drop constraint "audit_events_actor_membership_id_fkey";

alter table "public"."audit_events" drop constraint "audit_events_community_id_fkey";

alter table "public"."blacklisted_residents" drop constraint "blacklisted_residents_blacklisted_by_membership_id_fkey";

alter table "public"."blacklisted_residents" drop constraint "blacklisted_residents_community_id_fkey";

alter table "public"."blacklisted_residents" drop constraint "blacklisted_residents_profile_id_fkey";

alter table "public"."blacklisted_residents" drop constraint "blacklisted_residents_revoked_by_membership_id_fkey";

alter table "public"."blacklisted_service_providers" drop constraint "blacklisted_service_providers_blacklisted_by_membership_id_fkey";

alter table "public"."blacklisted_service_providers" drop constraint "blacklisted_service_providers_community_id_fkey";

alter table "public"."blacklisted_service_providers" drop constraint "blacklisted_service_providers_revoked_by_membership_id_fkey";

alter table "public"."blacklisted_service_providers" drop constraint "blacklisted_service_providers_service_provider_id_fkey";

alter table "public"."booking_charges" drop constraint "booking_charges_booking_id_fkey";

alter table "public"."booking_refunds" drop constraint "booking_refunds_booking_charge_id_fkey";

alter table "public"."community_admin_terms" drop constraint "community_admin_terms_admin_membership_id_fkey";

alter table "public"."community_admin_terms" drop constraint "community_admin_terms_community_id_fkey";

alter table "public"."community_admin_terms" drop constraint "community_admin_terms_transferred_by_membership_id_fkey";

alter table "public"."community_billing_settings" drop constraint "community_billing_settings_community_id_fkey";

alter table "public"."community_features" drop constraint "community_features_community_id_fkey";

alter table "public"."community_features" drop constraint "community_features_feature_code_fkey";

alter table "public"."community_memberships" drop constraint "community_memberships_check";

alter table "public"."community_memberships" drop constraint "community_memberships_community_id_fkey";

alter table "public"."community_memberships" drop constraint "community_memberships_department_id_fkey";

alter table "public"."community_memberships" drop constraint "community_memberships_profile_id_fkey";

alter table "public"."community_settings" drop constraint "community_settings_community_id_fkey";

alter table "public"."community_settings" drop constraint "community_settings_updated_by_membership_id_fkey";

alter table "public"."complaint_categories" drop constraint "complaint_categories_community_id_fkey";

alter table "public"."complaint_categories" drop constraint "complaint_categories_skill_id_fkey";

alter table "public"."complaint_comments" drop constraint "complaint_comments_author_membership_id_fkey";

alter table "public"."complaint_comments" drop constraint "complaint_comments_complaint_id_fkey";

alter table "public"."complaint_department_requests" drop constraint "complaint_department_requests_complaint_id_fkey";

alter table "public"."complaint_department_requests" drop constraint "complaint_department_requests_decided_by_membership_id_fkey";

alter table "public"."complaint_department_requests" drop constraint "complaint_department_requests_from_department_id_fkey";

alter table "public"."complaint_department_requests" drop constraint "complaint_department_requests_requested_by_membership_id_fkey";

alter table "public"."complaint_department_requests" drop constraint "complaint_department_requests_to_department_id_fkey";

alter table "public"."complaint_events" drop constraint "complaint_events_actor_membership_id_fkey";

alter table "public"."complaint_events" drop constraint "complaint_events_complaint_id_fkey";

alter table "public"."complaint_read_state" drop constraint "complaint_read_state_complaint_id_fkey";

alter table "public"."complaint_read_state" drop constraint "complaint_read_state_membership_id_fkey";

alter table "public"."complaints" drop constraint "complaints_assigned_to_membership_id_fkey";

alter table "public"."complaints" drop constraint "complaints_community_id_fkey";

alter table "public"."complaints" drop constraint "complaints_department_id_fkey";

alter table "public"."complaints" drop constraint "complaints_raised_by_membership_id_fkey";

alter table "public"."complaints" drop constraint "complaints_skill_id_fkey";

alter table "public"."conversation_messages" drop constraint "conversation_messages_author_membership_id_fkey";

alter table "public"."conversation_messages" drop constraint "conversation_messages_author_provider_id_fkey";

alter table "public"."conversation_messages" drop constraint "conversation_messages_conversation_id_fkey";

alter table "public"."conversations" drop constraint "conversations_community_id_fkey";

alter table "public"."conversations" drop constraint "conversations_department_id_fkey";

alter table "public"."conversations" drop constraint "conversations_department_tenant_fkey";

alter table "public"."conversations" drop constraint "conversations_service_provider_id_fkey";

alter table "public"."department_categories" drop constraint "department_categories_category_id_fkey";

alter table "public"."department_categories" drop constraint "department_categories_department_id_fkey";

alter table "public"."department_skills" drop constraint "department_skills_department_id_fkey";

alter table "public"."department_skills" drop constraint "department_skills_skill_id_fkey";

alter table "public"."departments" drop constraint "departments_community_id_fkey";

alter table "public"."dispatch_tasks" drop constraint "dispatch_tasks_complaint_id_fkey";

alter table "public"."dispatch_tasks" drop constraint "dispatch_tasks_departure_id_fkey";

alter table "public"."dispatch_tasks" drop constraint "dispatch_tasks_work_order_id_fkey";

alter table "public"."dm_messages" drop constraint "dm_messages_author_profile_id_fkey";

alter table "public"."dm_messages" drop constraint "dm_messages_thread_id_fkey";

alter table "public"."dm_threads" drop constraint "dm_threads_community_id_fkey";

alter table "public"."dm_threads" drop constraint "dm_threads_participant_a_profile_id_fkey";

alter table "public"."dm_threads" drop constraint "dm_threads_participant_b_profile_id_fkey";

alter table "public"."dm_threads" drop constraint "dm_threads_work_order_id_fkey";

alter table "public"."invoice_line_items" drop constraint "invoice_line_items_community_id_fkey";

alter table "public"."invoice_line_items" drop constraint "invoice_line_items_invoice_id_fkey";

alter table "public"."invoice_line_items" drop constraint "invoice_line_items_quantity_check";

alter table "public"."invoices" drop constraint "invoices_community_id_fkey";

alter table "public"."invoices" drop constraint "invoices_membership_id_fkey";

alter table "public"."invoices" drop constraint "invoices_unit_id_fkey";

alter table "public"."material_movements" drop constraint "material_movements_community_id_fkey";

alter table "public"."material_movements" drop constraint "material_movements_post_id_fkey";

alter table "public"."material_movements" drop constraint "material_movements_recorded_by_membership_id_fkey";

alter table "public"."material_movements" drop constraint "material_movements_unit_id_fkey";

alter table "public"."notices" drop constraint "notices_author_membership_id_fkey";

alter table "public"."notices" drop constraint "notices_community_id_fkey";

alter table "public"."notifications" drop constraint "notifications_recipient_profile_id_fkey";

alter table "public"."offline_reconcile_log" drop constraint "offline_reconcile_log_community_id_fkey";

alter table "public"."offline_reconcile_log" drop constraint "offline_reconcile_log_submitted_by_membership_id_fkey";

alter table "public"."offline_reconcile_log" drop constraint "offline_reconcile_log_visitor_request_id_fkey";

alter table "public"."payment_events" drop constraint "payment_events_payment_id_fkey";

alter table "public"."payments" drop constraint "payments_community_id_fkey";

alter table "public"."payments" drop constraint "payments_failure_code_check";

alter table "public"."payments" drop constraint "payments_invoice_id_fkey";

alter table "public"."payments" drop constraint "payments_payer_profile_id_fkey";

alter table "public"."payments" drop constraint "payments_received_by_membership_id_fkey";

alter table "public"."push_subscriptions" drop constraint "push_subscriptions_profile_id_fkey";

alter table "public"."resident_invites" drop constraint "resident_invites_created_by_membership_id_fkey";

alter table "public"."resident_invites" drop constraint "resident_invites_intended_unit_id_fkey";

alter table "public"."resident_invites" drop constraint "resident_invites_redeemed_by_profile_id_fkey";

alter table "public"."security_incidents" drop constraint "security_incidents_community_id_fkey";

alter table "public"."security_incidents" drop constraint "security_incidents_post_id_fkey";

alter table "public"."security_incidents" drop constraint "security_incidents_reported_by_membership_id_fkey";

alter table "public"."security_posts" drop constraint "security_posts_community_id_fkey";

alter table "public"."security_posts" drop constraint "security_posts_department_tenant_fkey";

alter table "public"."security_shifts" drop constraint "security_shifts_community_id_fkey";

alter table "public"."security_shifts" drop constraint "security_shifts_created_by_membership_id_fkey";

alter table "public"."security_shifts" drop constraint "security_shifts_department_tenant_fkey";

alter table "public"."security_shifts" drop constraint "security_shifts_post_id_fkey";

alter table "public"."security_shifts" drop constraint "security_shifts_staff_assignment_id_fkey";

alter table "public"."service_applications" drop constraint "service_applications_community_id_fkey";

alter table "public"."service_applications" drop constraint "service_applications_created_by_membership_id_fkey";

alter table "public"."service_applications" drop constraint "service_applications_decided_by_membership_id_fkey";

alter table "public"."service_applications" drop constraint "service_applications_department_id_fkey";

alter table "public"."service_applications" drop constraint "service_applications_department_tenant_fkey";

alter table "public"."service_applications" drop constraint "service_applications_service_provider_id_fkey";

alter table "public"."service_provider_skills" drop constraint "service_provider_skills_service_provider_id_fkey";

alter table "public"."service_provider_skills" drop constraint "service_provider_skills_skill_id_fkey";

alter table "public"."service_providers" drop constraint "service_providers_profile_id_fkey";

alter table "public"."sse_events" drop constraint "sse_events_community_id_fkey";

alter table "public"."sse_events" drop constraint "sse_events_recipient_membership_id_fkey";

alter table "public"."staff_assignments" drop constraint "staff_assignments_department_id_fkey";

alter table "public"."staff_assignments" drop constraint "staff_assignments_department_tenant_fkey";

alter table "public"."staff_assignments" drop constraint "staff_assignments_membership_id_fkey";

alter table "public"."staff_assignments" drop constraint "staff_assignments_service_provider_id_fkey";

alter table "public"."staff_departures" drop constraint "staff_departures_community_id_fkey";

alter table "public"."staff_departures" drop constraint "staff_departures_decided_by_membership_id_fkey";

alter table "public"."staff_departures" drop constraint "staff_departures_department_tenant_fkey";

alter table "public"."staff_departures" drop constraint "staff_departures_requested_by_membership_id_fkey";

alter table "public"."staff_departures" drop constraint "staff_departures_service_provider_id_fkey";

alter table "public"."staff_departures" drop constraint "staff_departures_staff_assignment_id_fkey";

alter table "public"."staff_invitations" drop constraint "staff_invitations_claimed_by_profile_id_fkey";

alter table "public"."staff_invitations" drop constraint "staff_invitations_community_id_fkey";

alter table "public"."staff_invitations" drop constraint "staff_invitations_created_by_membership_id_fkey";

alter table "public"."staff_invitations" drop constraint "staff_invitations_department_id_fkey";

alter table "public"."unit_contacts" drop constraint "unit_contacts_added_by_membership_id_fkey";

alter table "public"."unit_contacts" drop constraint "unit_contacts_community_id_fkey";

alter table "public"."unit_contacts" drop constraint "unit_contacts_unit_id_fkey";

alter table "public"."unit_residencies" drop constraint "unit_residencies_membership_id_fkey";

alter table "public"."unit_residencies" drop constraint "unit_residencies_unit_id_fkey";

alter table "public"."visitor_events" drop constraint "visitor_events_visitor_request_id_fkey";

alter table "public"."visitor_requests" drop constraint "visitor_requests_approved_by_membership_id_fkey";

alter table "public"."visitor_requests" drop constraint "visitor_requests_community_id_fkey";

alter table "public"."visitor_requests" drop constraint "visitor_requests_requested_by_membership_id_fkey";

alter table "public"."water_tanker_logs" drop constraint "water_tanker_logs_community_id_fkey";

alter table "public"."water_tanker_logs" drop constraint "water_tanker_logs_post_id_fkey";

alter table "public"."water_tanker_logs" drop constraint "water_tanker_logs_recorded_by_membership_id_fkey";

alter table "public"."work_order_assignments" drop constraint "work_order_assignments_staff_assignment_id_fkey";

alter table "public"."work_order_assignments" drop constraint "work_order_assignments_work_order_id_fkey";

alter table "public"."work_orders" drop constraint "work_orders_community_id_fkey";

alter table "public"."work_orders" drop constraint "work_orders_complaint_id_fkey";

alter table "public"."work_orders" drop constraint "work_orders_department_tenant_fkey";

alter table "public"."work_orders" drop constraint "work_orders_skill_id_fkey";

alter table "public"."work_orders" drop constraint "work_orders_supervisor_membership_id_fkey";

alter table "public"."worker_availability_rules" drop constraint "worker_availability_rules_service_provider_id_fkey";

alter table "public"."worker_availability_rules" drop constraint "worker_availability_rules_staff_assignment_id_fkey";

alter table "public"."worker_unavailability" drop constraint "worker_unavailability_service_provider_id_fkey";

alter table "public"."worker_unavailability" drop constraint "worker_unavailability_staff_assignment_id_fkey";

drop function if exists "public"."approve_access_request"(p_request_id uuid, p_reviewer_profile_id uuid, p_unit_id uuid, p_relationship residency_relationship);

drop function if exists "public"."claim_email_invitation"(p_invite_id uuid, p_profile_id uuid);

drop view if exists "public"."amenity_booking_overview";

drop view if exists "public"."amenity_ledger_summary";

drop view if exists "public"."amenity_overview";

drop view if exists "public"."bookable_amenity";

drop view if exists "public"."community_settings_overview";

drop view if exists "public"."complaint_overview";

drop view if exists "public"."conversation_message_overview";

drop view if exists "public"."conversation_overview";

drop view if exists "public"."department_overview";

drop view if exists "public"."department_staff_overview";

drop view if exists "public"."dm_thread_overview";

drop view if exists "public"."household_overview";

drop view if exists "public"."invoice_overview";

drop view if exists "public"."management_contact_overview";

drop view if exists "public"."my_worker_availability_rule";

drop view if exists "public"."my_worker_job";

drop view if exists "public"."my_worker_unavailability";

drop view if exists "public"."notification_overview";

drop view if exists "public"."payment_overview";

drop view if exists "public"."pending_access_request_overview";

drop view if exists "public"."resident_booking_overview";

drop view if exists "public"."resident_invoice_overview";

drop view if exists "public"."resident_notice_overview";

drop view if exists "public"."security_incident_overview";

drop view if exists "public"."service_application_overview";

drop view if exists "public"."service_engagement_overview";

drop view if exists "public"."service_provider_overview";

drop view if exists "public"."staff_departure_overview";

drop view if exists "public"."visitor_pass_overview";

drop view if exists "public"."work_order_assignment_overview";

drop view if exists "public"."work_order_overview";

drop view if exists "public"."amenity_ledger_overview";

drop view if exists "public"."community_module_overview";

alter table "public"."amenity_booking_charges" drop constraint "amenity_booking_charges_pkey";

alter table "public"."amenity_financial_events" drop constraint "amenity_financial_events_pkey";

alter table "public"."amenity_maintenance_blocks" drop constraint "amenity_maintenance_blocks_pkey";

alter table "public"."amenity_operating_hours" drop constraint "amenity_operating_hours_pkey";

alter table "public"."buildings" drop constraint "buildings_pkey";

alter table "public"."communities" drop constraint "communities_pkey";

alter table "public"."idempotency_records" drop constraint "idempotency_records_pkey";

alter table "public"."media" drop constraint "media_pkey";

alter table "public"."member_activity" drop constraint "member_activity_pkey";

alter table "public"."notifications" drop constraint "notifications_pkey";

alter table "public"."rate_limit_buckets" drop constraint "rate_limit_buckets_pkey";

alter table "public"."resident_invites" drop constraint "resident_invites_pkey";

alter table "public"."units" drop constraint "units_pkey";

alter table "public"."visitor_events" drop constraint "visitor_events_pkey";

drop index if exists "public"."amenity_maintenance_blocks_pkey";

drop index if exists "public"."amenity_operating_hours_pkey";

drop index if exists "public"."buildings_community_id_code_key";

drop index if exists "public"."buildings_pkey";

drop index if exists "public"."communities_pkey";

drop index if exists "public"."community_admin_one_active";

drop index if exists "public"."idempotency_records_pkey";

drop index if exists "public"."invites_one_open_email";

drop index if exists "public"."media_pkey";

drop index if exists "public"."media_storage_path_key";

drop index if exists "public"."member_activity_pkey";

drop index if exists "public"."memberships_active_person_community";

drop index if exists "public"."memberships_one_default";

drop index if exists "public"."payments_community_id_idempotency_key_key";

drop index if exists "public"."profiles_email_unique";

drop index if exists "public"."rate_limit_buckets_pkey";

drop index if exists "public"."residencies_active_member_unit";

drop index if exists "public"."resident_invites_code_hash_key";

drop index if exists "public"."resident_invites_pkey";

drop index if exists "public"."resident_invites_token_hash_key";

drop index if exists "public"."units_community_id_unit_code_key";

drop index if exists "public"."access_requests_one_pending_per_profile_community";

drop index if exists "public"."amenity_booking_charges_pkey";

select 1; 
-- drop index if exists "public"."amenity_bookings_amenity_id_tstzrange_excl";

drop index if exists "public"."amenity_financial_events_pkey";

drop index if exists "public"."communities_active_name_trgm";

drop index if exists "public"."notifications_pkey";

drop index if exists "public"."skills_name_trgm";

drop index if exists "public"."units_pkey";

drop index if exists "public"."visitor_events_pkey";

drop index if exists "public"."visitor_requests_live_code_idx";

drop table "public"."amenity_maintenance_blocks";

drop table "public"."amenity_operating_hours";

drop table "public"."idempotency_records";

drop table "public"."media";

drop table "public"."member_activity";

drop table "public"."rate_limit_buckets";


  create table "public"."amenity_rules" (
    "id" uuid not null default gen_random_uuid(),
    "amenity_id" uuid not null,
    "minimum_duration_minutes" integer,
    "maximum_duration_minutes" integer,
    "minimum_lead_minutes" integer,
    "maximum_advance_days" integer,
    "cancellation_cutoff_minutes" integer,
    "max_guests" integer,
    "effective_from" timestamp with time zone not null default now(),
    "effective_to" timestamp with time zone,
    "created_by_membership_id" uuid not null
      );


alter table "public"."amenity_rules" enable row level security;


  create table "public"."booking_guests" (
    "id" uuid not null default gen_random_uuid(),
    "booking_occurrence_id" uuid not null,
    "guest_name" text not null,
    "guest_phone_e164" character varying(20),
    "created_at" timestamp with time zone not null default now()
      );


alter table "public"."booking_guests" enable row level security;


  create table "public"."community_registration_requests" (
    "id" uuid not null default gen_random_uuid(),
    "requested_name" text not null,
    "requested_community_type" text not null,
    "contact_full_name" text not null,
    "contact_email" public.citext not null,
    "contact_phone_e164" character varying(20) not null,
    "requested_address" text,
    "otp_verified_at" timestamp with time zone,
    "status" public.request_status not null default 'pending'::public.request_status,
    "review_note" text,
    "reviewed_at" timestamp with time zone,
    "approved_community_id" uuid,
    "submitted_at" timestamp with time zone not null default now(),
    "updated_at" timestamp with time zone not null default now()
      );


alter table "public"."community_registration_requests" enable row level security;


  create table "public"."legacy_amenity_booking_charges" (
    "id" uuid not null default gen_random_uuid(),
    "booking_occurrence_id" uuid not null,
    "charge_type" text not null,
    "description" text,
    "amount" numeric(12,2) not null,
    "currency" character(3) not null default 'INR'::bpchar,
    "created_at" timestamp with time zone not null default now()
      );


alter table "public"."legacy_amenity_booking_charges" enable row level security;


  create table "public"."legacy_amenity_booking_occurrences" (
    "id" uuid not null default gen_random_uuid(),
    "booking_series_id" uuid not null,
    "amenity_id" uuid not null,
    "starts_at" timestamp with time zone not null,
    "ends_at" timestamp with time zone not null,
    "status" public.booking_status not null default 'requested'::public.booking_status,
    "approval_by_membership_id" uuid,
    "approved_at" timestamp with time zone,
    "cancellation_reason" text,
    "created_at" timestamp with time zone not null default now(),
    "updated_at" timestamp with time zone not null default now()
      );


alter table "public"."legacy_amenity_booking_occurrences" enable row level security;


  create table "public"."legacy_amenity_booking_series" (
    "id" uuid not null default gen_random_uuid(),
    "amenity_id" uuid not null,
    "community_id" uuid not null,
    "booked_by_membership_id" uuid not null,
    "liable_unit_id" uuid not null,
    "recurrence_rule" text,
    "status" public.booking_status not null default 'requested'::public.booking_status,
    "created_at" timestamp with time zone not null default now(),
    "updated_at" timestamp with time zone not null default now()
      );


alter table "public"."legacy_amenity_booking_series" enable row level security;


  create table "public"."legacy_amenity_financial_events" (
    "id" uuid not null default gen_random_uuid(),
    "booking_occurrence_id" uuid not null,
    "event_type" text not null,
    "amount" numeric(12,2) not null,
    "currency" character(3) not null default 'INR'::bpchar,
    "actor_membership_id" uuid,
    "reference" text,
    "created_at" timestamp with time zone not null default now()
      );


alter table "public"."legacy_amenity_financial_events" enable row level security;


  create table "public"."legacy_notifications" (
    "id" uuid not null default gen_random_uuid(),
    "community_id" uuid not null,
    "recipient_membership_id" uuid not null,
    "notification_type" text not null,
    "title" text not null,
    "body" text not null,
    "payload" jsonb,
    "read_at" timestamp with time zone,
    "created_at" timestamp with time zone not null default now()
      );


alter table "public"."legacy_notifications" enable row level security;


  create table "public"."legacy_visitor_events" (
    "id" uuid not null default gen_random_uuid(),
    "visitor_access_request_id" uuid not null,
    "actor_membership_id" uuid,
    "event_type" text not null,
    "occurred_at" timestamp with time zone not null default now(),
    "note" text
      );


alter table "public"."legacy_visitor_events" enable row level security;


  create table "public"."media_assets" (
    "id" uuid not null default gen_random_uuid(),
    "community_id" uuid not null,
    "uploaded_by_membership_id" uuid,
    "storage_bucket" text not null,
    "storage_path" text not null,
    "mime_type" text not null,
    "byte_size" bigint not null,
    "status" public.media_status not null default 'pending'::public.media_status,
    "created_at" timestamp with time zone not null default now()
      );


alter table "public"."media_assets" enable row level security;


  create table "public"."notification_deliveries" (
    "id" uuid not null default gen_random_uuid(),
    "notification_id" uuid not null,
    "channel" text not null,
    "status" text not null,
    "provider_message_id" text,
    "attempted_at" timestamp with time zone not null default now(),
    "delivered_at" timestamp with time zone,
    "failure_reason" text
      );


alter table "public"."notification_deliveries" enable row level security;


  create table "public"."policies" (
    "id" uuid not null default gen_random_uuid(),
    "community_id" uuid not null,
    "title" text not null,
    "status" text not null default 'draft'::text,
    "current_revision_id" uuid,
    "created_by_membership_id" uuid not null,
    "created_at" timestamp with time zone not null default now(),
    "updated_at" timestamp with time zone not null default now()
      );


alter table "public"."policies" enable row level security;


  create table "public"."policy_revisions" (
    "id" uuid not null default gen_random_uuid(),
    "policy_id" uuid not null,
    "revision_number" integer not null,
    "body" text not null,
    "change_summary" text,
    "authored_by_membership_id" uuid not null,
    "published_at" timestamp with time zone,
    "created_at" timestamp with time zone not null default now()
      );


alter table "public"."policy_revisions" enable row level security;


  create table "public"."saved_visitors" (
    "id" uuid not null default gen_random_uuid(),
    "community_id" uuid not null,
    "created_by_membership_id" uuid not null,
    "full_name" text not null,
    "phone_e164" character varying(20),
    "default_purpose" text,
    "created_at" timestamp with time zone not null default now(),
    "updated_at" timestamp with time zone not null default now()
      );


alter table "public"."saved_visitors" enable row level security;


  create table "public"."visitor_access_requests" (
    "id" uuid not null default gen_random_uuid(),
    "community_id" uuid not null,
    "unit_id" uuid not null,
    "requested_by_membership_id" uuid not null,
    "saved_visitor_id" uuid,
    "visitor_name" text not null,
    "visitor_phone_e164" character varying(20),
    "purpose" text not null,
    "expected_from" timestamp with time zone not null,
    "expected_until" timestamp with time zone,
    "gate_code_hash" text,
    "status" public.visitor_status not null default 'expected'::public.visitor_status,
    "decided_by_membership_id" uuid,
    "decided_at" timestamp with time zone,
    "checked_in_by_membership_id" uuid,
    "checked_in_at" timestamp with time zone,
    "checked_out_by_membership_id" uuid,
    "checked_out_at" timestamp with time zone,
    "created_at" timestamp with time zone not null default now(),
    "updated_at" timestamp with time zone not null default now()
      );


alter table "public"."visitor_access_requests" enable row level security;


  create table "public"."visitor_attachments" (
    "visitor_access_request_id" uuid not null,
    "media_asset_id" uuid not null,
    "attached_by_membership_id" uuid,
    "created_at" timestamp with time zone not null default now()
      );


alter table "public"."visitor_attachments" enable row level security;


  create table "public"."work_order_attachments" (
    "work_order_id" uuid not null,
    "media_asset_id" uuid not null,
    "attached_by_membership_id" uuid,
    "created_at" timestamp with time zone not null default now()
      );


alter table "public"."work_order_attachments" enable row level security;


  create table "public"."work_order_completion_verifications" (
    "id" uuid not null default gen_random_uuid(),
    "work_order_id" uuid not null,
    "verified_by_membership_id" uuid not null,
    "outcome" text not null,
    "rating" smallint,
    "note" text,
    "verified_at" timestamp with time zone not null default now()
      );


alter table "public"."work_order_completion_verifications" enable row level security;


  create table "public"."work_order_proposals" (
    "id" uuid not null default gen_random_uuid(),
    "work_order_id" uuid not null,
    "proposed_by_membership_id" uuid not null,
    "proposed_start_at" timestamp with time zone,
    "proposed_end_at" timestamp with time zone,
    "proposed_amount" numeric(12,2),
    "currency" character(3) not null default 'INR'::bpchar,
    "status" text not null default 'proposed'::text,
    "responded_by_membership_id" uuid,
    "responded_at" timestamp with time zone,
    "note" text,
    "created_at" timestamp with time zone not null default now()
      );


alter table "public"."work_order_proposals" enable row level security;


  create table "public"."work_order_views" (
    "id" uuid not null default gen_random_uuid(),
    "work_order_id" uuid not null,
    "membership_id" uuid not null,
    "viewed_at" timestamp with time zone not null default now()
      );


alter table "public"."work_order_views" enable row level security;

alter table "public"."access_requests" add column "created_profile_id" uuid;

alter table "public"."access_requests" alter column "applicant_email" drop not null;

alter table "public"."access_requests" alter column "applicant_email" set data type public.citext using "applicant_email"::public.citext;

alter table "public"."access_requests" alter column "applicant_profile_id" drop not null;

alter table "public"."access_requests" alter column "requested_relationship" set default 'tenant'::public.residency_relationship;

alter table "public"."access_requests" alter column "requested_relationship" set data type public.residency_relationship using "requested_relationship"::text::public.residency_relationship;

alter table "public"."access_requests" alter column "status" set default 'pending'::public.request_status;

alter table "public"."access_requests" alter column "status" set data type public.request_status using "status"::public.request_status;

alter table "public"."amenities" drop column "booking_rules";

alter table "public"."amenities" add column "hourly_rate" numeric(12,2) not null default 0;

alter table "public"."amenities" alter column "approval_required" set default false;

alter table "public"."amenities" alter column "booking_mode" set default 'slot'::text;

alter table "public"."amenities" alter column "category" set not null;

alter table "public"."amenities" enable row level security;

alter table "public"."amenity_bookings" alter column "status" set default 'requested'::public.booking_status;

alter table "public"."amenity_bookings" alter column "status" set data type public.booking_status using "status"::text::public.booking_status;

alter table "public"."audit_events" drop column "payload";

alter table "public"."audit_events" add column "after_data" jsonb;

alter table "public"."audit_events" add column "before_data" jsonb;

alter table "public"."audit_events" add column "entity_id" uuid;

alter table "public"."audit_events" add column "entity_type" text not null;

alter table "public"."audit_events" add column "request_id" uuid;

alter table "public"."audit_events" alter column "community_id" set not null;

alter table "public"."audit_events" enable row level security;

alter table "public"."booking_charges" enable row level security;

alter table "public"."booking_refunds" enable row level security;

alter table "public"."buildings" add column "coordinates" jsonb;

alter table "public"."buildings" enable row level security;

alter table "public"."communities" drop column "active_admin_membership_id";

alter table "public"."communities" drop column "address_line2";

alter table "public"."communities" drop column "country_code";

alter table "public"."communities" alter column "address_line1" drop not null;

alter table "public"."communities" alter column "city" drop not null;

alter table "public"."communities" alter column "community_type" set default 'apartment'::text;

alter table "public"."communities" alter column "location" set default 
CASE
    WHEN ((latitude IS NULL) OR (longitude IS NULL)) THEN NULL::extensions.geography
    ELSE (extensions.st_setsrid(extensions.st_makepoint((longitude)::double precision, (latitude)::double precision), 4326))::extensions.geography
END;

alter table "public"."communities" alter column "location" set data type extensions.geography(Point,4326) using "location"::extensions.geography(Point,4326);

alter table "public"."communities" alter column "postal_code" drop not null;

alter table "public"."communities" alter column "state" drop not null;

alter table "public"."community_admin_terms" drop column "designation";

alter table "public"."community_admin_terms" add column "created_at" timestamp with time zone not null default now();

alter table "public"."community_admin_terms" add column "role_before_term" public.membership_role not null default 'resident'::public.membership_role;

alter table "public"."community_admin_terms" enable row level security;

alter table "public"."community_features" enable row level security;

alter table "public"."community_memberships" alter column "role" set data type public.membership_role using "role"::text::public.membership_role;

alter table "public"."community_memberships" alter column "status" set default 'pending'::public.membership_status;

alter table "public"."community_memberships" alter column "status" set data type public.membership_status using "status"::text::public.membership_status;

alter table "public"."complaint_events" drop column "payload";

alter table "public"."complaint_events" add column "new_status" public.complaint_status;

alter table "public"."complaint_events" add column "note" text;

alter table "public"."complaint_events" add column "previous_status" public.complaint_status;

alter table "public"."complaints" drop column "aggregate_version";

alter table "public"."complaints" add column "closed_at" timestamp with time zone;

alter table "public"."complaints" add column "unit_id" uuid;

alter table "public"."complaints" alter column "description" set not null;

alter table "public"."complaints" alter column "progress_percent" set data type smallint using "progress_percent"::smallint;

alter table "public"."complaints" alter column "status" set default 'open'::public.complaint_status;

alter table "public"."complaints" alter column "status" set data type public.complaint_status using "status"::text::public.complaint_status;

alter table "public"."departments" alter column "contact_email" set data type public.citext using "contact_email"::public.citext;

alter table "public"."departments" alter column "hours" drop default;

alter table "public"."departments" alter column "hours" drop not null;

alter table "public"."departments" alter column "hours" set data type text using "hours"::text;

alter table "public"."feature_catalog" alter column "description" drop default;

alter table "public"."feature_catalog" enable row level security;

alter table "public"."invoice_line_items" add column "amenity_booking_charge_id" uuid;

alter table "public"."invoice_line_items" add column "created_at" timestamp with time zone not null default now();

alter table "public"."invoice_line_items" alter column "amount" drop not null;

alter table "public"."invoice_line_items" alter column "quantity" set data type numeric(10,2) using "quantity"::numeric(10,2);

alter table "public"."invoice_line_items" alter column "total_amount" drop expression;

alter table "public"."invoice_line_items" alter column "total_amount" set not null;

alter table "public"."invoice_line_items" alter column "unit_amount" drop default;

alter table "public"."invoices" add column "booking_occurrence_id" uuid;

alter table "public"."invoices" add column "created_by_membership_id" uuid;

alter table "public"."invoices" add column "issued_at" timestamp with time zone not null default now();

alter table "public"."invoices" add column "liable_unit_id" uuid;

alter table "public"."invoices" add column "subtotal" numeric(12,2) not null default 0;

alter table "public"."invoices" alter column "due_at" set not null;

alter table "public"."invoices" alter column "invoice_number" set not null;

alter table "public"."invoices" alter column "invoice_type" drop default;

alter table "public"."invoices" alter column "membership_id" drop not null;

alter table "public"."invoices" alter column "status" set default 'draft'::public.invoice_status;

alter table "public"."invoices" alter column "status" set data type public.invoice_status using "status"::text::public.invoice_status;

alter table "public"."invoices" alter column "total_amount" drop default;

alter table "public"."notices" add column "audience_role" public.membership_role;

alter table "public"."notices" add column "expires_at" timestamp with time zone;

alter table "public"."notices" add column "status" text not null default 'draft'::text;

alter table "public"."notices" alter column "author_membership_id" set not null;

alter table "public"."payment_events" add column "actor_membership_id" uuid;

alter table "public"."payment_events" alter column "payload" drop default;

alter table "public"."payment_events" alter column "payload" drop not null;

alter table "public"."payments" add column "currency" character(3) default 'INR'::bpchar;

alter table "public"."payments" add column "method" text;

alter table "public"."payments" add column "payer_membership_id" uuid;

alter table "public"."payments" add column "recorded_by_membership_id" uuid;

alter table "public"."payments" alter column "community_id" drop not null;

alter table "public"."payments" alter column "invoice_id" set not null;

alter table "public"."payments" alter column "paid_at" drop default;

alter table "public"."payments" alter column "paid_at" drop not null;

alter table "public"."payments" alter column "provider" drop default;

alter table "public"."payments" alter column "provider" drop not null;

alter table "public"."payments" alter column "status" set default 'initiated'::public.payment_status;

alter table "public"."payments" alter column "status" set data type public.payment_status using "status"::text::public.payment_status;

alter table "public"."profiles" add column "legacy_community_id" uuid;

alter table "public"."profiles" add column "legacy_role" public.user_role not null default 'RESIDENT'::public.user_role;

alter table "public"."profiles" add column "legacy_unit_code" text;

alter table "public"."profiles" add column "status" text not null default 'Active'::text;

alter table "public"."profiles" alter column "display_email" set data type public.citext using "display_email"::public.citext;

alter table "public"."profiles" alter column "phone_e164" set data type text using "phone_e164"::text;

alter table "public"."resident_invites" add column "legacy_created_by_profile_id" uuid;

alter table "public"."resident_invites" add column "legacy_role" public.user_role not null default 'RESIDENT'::public.user_role;

alter table "public"."resident_invites" add column "legacy_unit_code" text not null;

alter table "public"."resident_invites" alter column "community_id" drop not null;

alter table "public"."resident_invites" alter column "intended_role" set default 'resident'::public.membership_role;

alter table "public"."resident_invites" alter column "intended_role" set data type public.membership_role using "intended_role"::text::public.membership_role;

alter table "public"."resident_invites" alter column "invitee_email" drop not null;

alter table "public"."resident_invites" alter column "invitee_email" set data type public.citext using "invitee_email"::public.citext;

alter table "public"."resident_invites" alter column "invitee_phone_e164" set not null;

alter table "public"."resident_invites" alter column "invitee_phone_e164" set data type text using "invitee_phone_e164"::text;

alter table "public"."resident_invites" alter column "status" set default 'issued'::public.invite_status;

alter table "public"."resident_invites" alter column "status" set data type public.invite_status using "status"::text::public.invite_status;

alter table "public"."service_providers" alter column "location" set default 
CASE
    WHEN ((latitude IS NULL) OR (longitude IS NULL)) THEN NULL::extensions.geography
    ELSE (extensions.st_setsrid(extensions.st_makepoint((longitude)::double precision, (latitude)::double precision), 4326))::extensions.geography
END;

alter table "public"."service_providers" alter column "location" set data type extensions.geography(Point,4326) using "location"::extensions.geography(Point,4326);

alter table "public"."skills" enable row level security;

alter table "public"."sse_events" alter column "payload" set default '{}'::jsonb;

alter table "public"."staff_invitations" alter column "invitee_email" set data type public.citext using "invitee_email"::public.citext;

alter table "public"."unit_residencies" add column "created_by_membership_id" uuid;

alter table "public"."unit_residencies" add column "nominated_successor_residency_id" uuid;

alter table "public"."unit_residencies" alter column "relationship_type" set data type public.residency_relationship using "relationship_type"::text::public.residency_relationship;

alter table "public"."visitor_requests" alter column "status" set default 'expected'::public.visitor_status;

alter table "public"."visitor_requests" alter column "status" set data type public.visitor_status using "status"::text::public.visitor_status;

alter table "public"."work_order_assignments" add column "assigned_by_membership_id" uuid not null;

alter table "public"."work_order_assignments" add column "assignment_status" text not null default 'assigned'::text;

alter table "public"."work_order_assignments" add column "unassigned_at" timestamp with time zone;

alter table "public"."work_order_assignments" alter column "staff_assignment_id" set not null;

alter table "public"."work_orders" add column "completed_at" timestamp with time zone;

alter table "public"."work_orders" add column "created_by_membership_id" uuid not null;

alter table "public"."work_orders" add column "description" text;

alter table "public"."work_orders" add column "title" text not null;

alter table "public"."work_orders" alter column "complaint_id" set not null;

alter table "public"."worker_availability_rules" add column "created_at" timestamp with time zone not null default now();

CREATE UNIQUE INDEX access_requests_one_open_phone ON public.access_requests USING btree (community_id, applicant_phone_e164) WHERE (status = 'pending'::public.request_status);

CREATE UNIQUE INDEX amenity_booking_charges_pkey1 ON public.amenity_booking_charges USING btree (id);

select 1; 
-- CREATE INDEX amenity_booking_occurrences_no_approved_overlap ON public.legacy_amenity_booking_occurrences USING gist (amenity_id, tstzrange(starts_at, ends_at, '[)'::text)) WHERE (status = 'approved'::public.booking_status);

CREATE UNIQUE INDEX amenity_booking_occurrences_pkey ON public.legacy_amenity_booking_occurrences USING btree (id);

CREATE UNIQUE INDEX amenity_booking_series_pkey ON public.legacy_amenity_booking_series USING btree (id);

CREATE UNIQUE INDEX amenity_financial_events_pkey1 ON public.amenity_financial_events USING btree (id);

CREATE UNIQUE INDEX amenity_rules_pkey ON public.amenity_rules USING btree (id);

CREATE UNIQUE INDEX apartments_association_id_code_key ON public.units USING btree (community_id, unit_code);

CREATE UNIQUE INDEX apartments_pkey ON public.units USING btree (id);

CREATE UNIQUE INDEX associations_pkey ON public.communities USING btree (id);

CREATE UNIQUE INDEX booking_guests_pkey ON public.booking_guests USING btree (id);

CREATE UNIQUE INDEX buildings_community_code_unique ON public.buildings USING btree (community_id, code);

CREATE UNIQUE INDEX community_admin_terms_one_active_admin ON public.community_admin_terms USING btree (community_id) WHERE (ended_at IS NULL);

CREATE UNIQUE INDEX community_memberships_one_active_per_community ON public.community_memberships USING btree (community_id, profile_id) WHERE ((status = ANY (ARRAY['pending'::public.membership_status, 'active'::public.membership_status, 'suspended'::public.membership_status])) AND (ended_at IS NULL));

CREATE UNIQUE INDEX community_memberships_one_active_resident ON public.community_memberships USING btree (profile_id) WHERE ((role = 'resident'::public.membership_role) AND (status = 'active'::public.membership_status) AND (ended_at IS NULL));

CREATE UNIQUE INDEX community_memberships_one_default ON public.community_memberships USING btree (profile_id) WHERE (is_default_community AND (status = 'active'::public.membership_status) AND (ended_at IS NULL));

CREATE INDEX community_memberships_profile_idx ON public.community_memberships USING btree (profile_id, community_id) WHERE ((status = 'active'::public.membership_status) AND (ended_at IS NULL));

CREATE UNIQUE INDEX community_registration_requests_approved_community_id_key ON public.community_registration_requests USING btree (approved_community_id);

CREATE UNIQUE INDEX community_registration_requests_pkey ON public.community_registration_requests USING btree (id);

CREATE INDEX complaints_community_status_idx ON public.complaints USING btree (community_id, status, created_at DESC);

CREATE INDEX invitations_code_hash_idx ON public.resident_invites USING btree (code_hash);

CREATE INDEX invitations_phone_idx ON public.resident_invites USING btree (invitee_phone_e164);

CREATE UNIQUE INDEX invitations_pkey ON public.resident_invites USING btree (id);

CREATE UNIQUE INDEX invitations_token_hash_key ON public.resident_invites USING btree (token_hash);

CREATE UNIQUE INDEX invoices_community_id_invoice_number_key ON public.invoices USING btree (community_id, invoice_number);

CREATE INDEX invoices_unit_status_idx ON public.invoices USING btree (liable_unit_id, status, due_at);

CREATE UNIQUE INDEX media_assets_pkey ON public.media_assets USING btree (id);

CREATE UNIQUE INDEX media_assets_storage_path_key ON public.media_assets USING btree (storage_path);

CREATE UNIQUE INDEX notification_deliveries_pkey ON public.notification_deliveries USING btree (id);

CREATE UNIQUE INDEX notifications_pkey1 ON public.notifications USING btree (id);

CREATE INDEX notifications_recipient_idx ON public.legacy_notifications USING btree (recipient_membership_id, read_at, created_at DESC);

CREATE UNIQUE INDEX payments_provider_reference_key ON public.payments USING btree (provider_reference);

CREATE UNIQUE INDEX policies_pkey ON public.policies USING btree (id);

CREATE UNIQUE INDEX policy_revisions_pkey ON public.policy_revisions USING btree (id);

CREATE UNIQUE INDEX policy_revisions_policy_id_revision_number_key ON public.policy_revisions USING btree (policy_id, revision_number);

CREATE INDEX profiles_apartment_id_idx ON public.profiles USING btree (legacy_unit_code);

CREATE INDEX profiles_association_id_idx ON public.profiles USING btree (legacy_community_id);

CREATE UNIQUE INDEX profiles_phone_e164_unique ON public.profiles USING btree (phone_e164) WHERE (phone_e164 IS NOT NULL);

CREATE UNIQUE INDEX resident_invites_code_hash_unique ON public.resident_invites USING btree (code_hash);

CREATE INDEX resident_invites_intended_unit_idx ON public.resident_invites USING btree (intended_unit_id);

CREATE UNIQUE INDEX resident_invites_one_active_phone ON public.resident_invites USING btree (community_id, invitee_phone_e164) WHERE (status = 'issued'::public.invite_status);

CREATE UNIQUE INDEX saved_visitors_pkey ON public.saved_visitors USING btree (id);

CREATE INDEX unit_residencies_membership_idx ON public.unit_residencies USING btree (membership_id) WHERE (ended_at IS NULL);

CREATE UNIQUE INDEX unit_residencies_one_active_membership_unit ON public.unit_residencies USING btree (unit_id, membership_id) WHERE (ended_at IS NULL);

CREATE UNIQUE INDEX unit_residencies_one_active_primary_contact ON public.unit_residencies USING btree (unit_id) WHERE (is_primary_contact AND (ended_at IS NULL));

CREATE INDEX visitor_access_requests_community_status_idx ON public.visitor_access_requests USING btree (community_id, status, expected_from DESC);

CREATE UNIQUE INDEX visitor_access_requests_pkey ON public.visitor_access_requests USING btree (id);

CREATE UNIQUE INDEX visitor_attachments_pkey ON public.visitor_attachments USING btree (visitor_access_request_id, media_asset_id);

CREATE UNIQUE INDEX visitor_events_pkey1 ON public.visitor_events USING btree (id);

CREATE UNIQUE INDEX work_order_assignments_work_order_id_staff_assignment_id_key ON public.work_order_assignments USING btree (work_order_id, staff_assignment_id);

CREATE UNIQUE INDEX work_order_attachments_pkey ON public.work_order_attachments USING btree (work_order_id, media_asset_id);

CREATE UNIQUE INDEX work_order_completion_verifications_pkey ON public.work_order_completion_verifications USING btree (id);

CREATE UNIQUE INDEX work_order_proposals_pkey ON public.work_order_proposals USING btree (id);

CREATE UNIQUE INDEX work_order_views_pkey ON public.work_order_views USING btree (id);

CREATE UNIQUE INDEX work_order_views_work_order_id_membership_id_key ON public.work_order_views USING btree (work_order_id, membership_id);

CREATE UNIQUE INDEX access_requests_one_pending_per_profile_community ON public.access_requests USING btree (community_id, applicant_profile_id) WHERE (status = 'pending'::public.request_status);

CREATE UNIQUE INDEX amenity_booking_charges_pkey ON public.legacy_amenity_booking_charges USING btree (id);

select 1; 
-- CREATE INDEX amenity_bookings_amenity_id_tstzrange_excl ON public.amenity_bookings USING gist (amenity_id, tstzrange(starts_at, ends_at, '[)'::text)) WHERE (status = ANY (ARRAY['requested'::public.booking_status, 'approved'::public.booking_status]));

CREATE UNIQUE INDEX amenity_financial_events_pkey ON public.legacy_amenity_financial_events USING btree (id);

CREATE INDEX communities_active_name_trgm ON public.communities USING gin (lower(name) extensions.gin_trgm_ops) WHERE (status = 'active'::text);

CREATE UNIQUE INDEX notifications_pkey ON public.legacy_notifications USING btree (id);

CREATE INDEX skills_name_trgm ON public.skills USING gin (lower(name) extensions.gin_trgm_ops) WHERE is_active;

CREATE UNIQUE INDEX units_pkey ON public.buildings USING btree (id);

CREATE UNIQUE INDEX visitor_events_pkey ON public.legacy_visitor_events USING btree (id);

CREATE UNIQUE INDEX visitor_requests_live_code_idx ON public.visitor_requests USING btree (community_id, code_hash) WHERE ((code_hash IS NOT NULL) AND (status = ANY (ARRAY['expected'::public.visitor_status, 'pending_approval'::public.visitor_status, 'approved'::public.visitor_status])));

alter table "public"."amenity_booking_charges" add constraint "amenity_booking_charges_pkey1" PRIMARY KEY using index "amenity_booking_charges_pkey1";

alter table "public"."amenity_financial_events" add constraint "amenity_financial_events_pkey1" PRIMARY KEY using index "amenity_financial_events_pkey1";

alter table "public"."amenity_rules" add constraint "amenity_rules_pkey" PRIMARY KEY using index "amenity_rules_pkey";

alter table "public"."booking_guests" add constraint "booking_guests_pkey" PRIMARY KEY using index "booking_guests_pkey";

alter table "public"."buildings" add constraint "units_pkey" PRIMARY KEY using index "units_pkey";

alter table "public"."communities" add constraint "associations_pkey" PRIMARY KEY using index "associations_pkey";

alter table "public"."community_registration_requests" add constraint "community_registration_requests_pkey" PRIMARY KEY using index "community_registration_requests_pkey";

alter table "public"."legacy_amenity_booking_charges" add constraint "amenity_booking_charges_pkey" PRIMARY KEY using index "amenity_booking_charges_pkey";

alter table "public"."legacy_amenity_booking_occurrences" add constraint "amenity_booking_occurrences_pkey" PRIMARY KEY using index "amenity_booking_occurrences_pkey";

alter table "public"."legacy_amenity_booking_series" add constraint "amenity_booking_series_pkey" PRIMARY KEY using index "amenity_booking_series_pkey";

alter table "public"."legacy_amenity_financial_events" add constraint "amenity_financial_events_pkey" PRIMARY KEY using index "amenity_financial_events_pkey";

alter table "public"."legacy_notifications" add constraint "notifications_pkey" PRIMARY KEY using index "notifications_pkey";

alter table "public"."legacy_visitor_events" add constraint "visitor_events_pkey" PRIMARY KEY using index "visitor_events_pkey";

alter table "public"."media_assets" add constraint "media_assets_pkey" PRIMARY KEY using index "media_assets_pkey";

alter table "public"."notification_deliveries" add constraint "notification_deliveries_pkey" PRIMARY KEY using index "notification_deliveries_pkey";

alter table "public"."notifications" add constraint "notifications_pkey1" PRIMARY KEY using index "notifications_pkey1";

alter table "public"."policies" add constraint "policies_pkey" PRIMARY KEY using index "policies_pkey";

alter table "public"."policy_revisions" add constraint "policy_revisions_pkey" PRIMARY KEY using index "policy_revisions_pkey";

alter table "public"."resident_invites" add constraint "invitations_pkey" PRIMARY KEY using index "invitations_pkey";

alter table "public"."saved_visitors" add constraint "saved_visitors_pkey" PRIMARY KEY using index "saved_visitors_pkey";

alter table "public"."units" add constraint "apartments_pkey" PRIMARY KEY using index "apartments_pkey";

alter table "public"."visitor_access_requests" add constraint "visitor_access_requests_pkey" PRIMARY KEY using index "visitor_access_requests_pkey";

alter table "public"."visitor_attachments" add constraint "visitor_attachments_pkey" PRIMARY KEY using index "visitor_attachments_pkey";

alter table "public"."visitor_events" add constraint "visitor_events_pkey1" PRIMARY KEY using index "visitor_events_pkey1";

alter table "public"."work_order_attachments" add constraint "work_order_attachments_pkey" PRIMARY KEY using index "work_order_attachments_pkey";

alter table "public"."work_order_completion_verifications" add constraint "work_order_completion_verifications_pkey" PRIMARY KEY using index "work_order_completion_verifications_pkey";

alter table "public"."work_order_proposals" add constraint "work_order_proposals_pkey" PRIMARY KEY using index "work_order_proposals_pkey";

alter table "public"."work_order_views" add constraint "work_order_views_pkey" PRIMARY KEY using index "work_order_views_pkey";

alter table "public"."access_requests" add constraint "access_requests_created_profile_id_fkey" FOREIGN KEY (created_profile_id) REFERENCES public.profiles(id) ON DELETE SET NULL not valid;

alter table "public"."access_requests" validate constraint "access_requests_created_profile_id_fkey";

alter table "public"."amenities" add constraint "amenities_capacity_check" CHECK (((capacity IS NULL) OR (capacity > 0))) not valid;

alter table "public"."amenities" validate constraint "amenities_capacity_check";

alter table "public"."amenities" add constraint "amenities_hourly_rate_check" CHECK ((hourly_rate >= (0)::numeric)) not valid;

alter table "public"."amenities" validate constraint "amenities_hourly_rate_check";

alter table "public"."amenity_booking_charges" add constraint "amenity_booking_charges_amount_check1" CHECK ((amount >= (0)::numeric)) not valid;

alter table "public"."amenity_booking_charges" validate constraint "amenity_booking_charges_amount_check1";

alter table "public"."amenity_booking_charges" add constraint "amenity_booking_charges_booking_occurrence_id_fkey1" FOREIGN KEY (booking_occurrence_id) REFERENCES public.amenity_bookings(id) ON DELETE CASCADE not valid;

alter table "public"."amenity_booking_charges" validate constraint "amenity_booking_charges_booking_occurrence_id_fkey1";

alter table "public"."amenity_financial_events" add constraint "amenity_financial_events_actor_membership_id_fkey1" FOREIGN KEY (actor_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."amenity_financial_events" validate constraint "amenity_financial_events_actor_membership_id_fkey1";

alter table "public"."amenity_rules" add constraint "amenity_rules_amenity_id_fkey" FOREIGN KEY (amenity_id) REFERENCES public.amenities(id) ON DELETE CASCADE not valid;

alter table "public"."amenity_rules" validate constraint "amenity_rules_amenity_id_fkey";

alter table "public"."amenity_rules" add constraint "amenity_rules_cancellation_cutoff_minutes_check" CHECK (((cancellation_cutoff_minutes IS NULL) OR (cancellation_cutoff_minutes >= 0))) not valid;

alter table "public"."amenity_rules" validate constraint "amenity_rules_cancellation_cutoff_minutes_check";

alter table "public"."amenity_rules" add constraint "amenity_rules_check" CHECK (((effective_to IS NULL) OR (effective_to > effective_from))) not valid;

alter table "public"."amenity_rules" validate constraint "amenity_rules_check";

alter table "public"."amenity_rules" add constraint "amenity_rules_created_by_membership_id_fkey" FOREIGN KEY (created_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."amenity_rules" validate constraint "amenity_rules_created_by_membership_id_fkey";

alter table "public"."amenity_rules" add constraint "amenity_rules_max_guests_check" CHECK (((max_guests IS NULL) OR (max_guests >= 0))) not valid;

alter table "public"."amenity_rules" validate constraint "amenity_rules_max_guests_check";

alter table "public"."amenity_rules" add constraint "amenity_rules_maximum_advance_days_check" CHECK (((maximum_advance_days IS NULL) OR (maximum_advance_days >= 0))) not valid;

alter table "public"."amenity_rules" validate constraint "amenity_rules_maximum_advance_days_check";

alter table "public"."amenity_rules" add constraint "amenity_rules_maximum_duration_minutes_check" CHECK (((maximum_duration_minutes IS NULL) OR (maximum_duration_minutes > 0))) not valid;

alter table "public"."amenity_rules" validate constraint "amenity_rules_maximum_duration_minutes_check";

alter table "public"."amenity_rules" add constraint "amenity_rules_minimum_duration_minutes_check" CHECK (((minimum_duration_minutes IS NULL) OR (minimum_duration_minutes > 0))) not valid;

alter table "public"."amenity_rules" validate constraint "amenity_rules_minimum_duration_minutes_check";

alter table "public"."amenity_rules" add constraint "amenity_rules_minimum_lead_minutes_check" CHECK (((minimum_lead_minutes IS NULL) OR (minimum_lead_minutes >= 0))) not valid;

alter table "public"."amenity_rules" validate constraint "amenity_rules_minimum_lead_minutes_check";

alter table "public"."booking_guests" add constraint "booking_guests_booking_occurrence_id_fkey" FOREIGN KEY (booking_occurrence_id) REFERENCES public.legacy_amenity_booking_occurrences(id) ON DELETE CASCADE not valid;

alter table "public"."booking_guests" validate constraint "booking_guests_booking_occurrence_id_fkey";

alter table "public"."buildings" add constraint "units_association_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."buildings" validate constraint "units_association_id_fkey";

alter table "public"."community_admin_terms" add constraint "community_admin_terms_check" CHECK (((ended_at IS NULL) OR (ended_at >= started_at))) not valid;

alter table "public"."community_admin_terms" validate constraint "community_admin_terms_check";

alter table "public"."community_features" add constraint "community_features_updated_by_membership_fkey" FOREIGN KEY (updated_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."community_features" validate constraint "community_features_updated_by_membership_fkey";

alter table "public"."community_registration_requests" add constraint "community_registration_requests_approved_community_id_fkey" FOREIGN KEY (approved_community_id) REFERENCES public.communities(id) ON DELETE SET NULL not valid;

alter table "public"."community_registration_requests" validate constraint "community_registration_requests_approved_community_id_fkey";

alter table "public"."community_registration_requests" add constraint "community_registration_requests_approved_community_id_key" UNIQUE using index "community_registration_requests_approved_community_id_key";

alter table "public"."community_registration_requests" add constraint "community_registration_requests_requested_community_type_check" CHECK ((requested_community_type = ANY (ARRAY['apartment'::text, 'layout_villa'::text]))) not valid;

alter table "public"."community_registration_requests" validate constraint "community_registration_requests_requested_community_type_check";

alter table "public"."complaints" add constraint "complaints_unit_id_fkey" FOREIGN KEY (unit_id) REFERENCES public.units(id) ON DELETE SET NULL not valid;

alter table "public"."complaints" validate constraint "complaints_unit_id_fkey";

alter table "public"."departments" add constraint "departments_manager_membership_fkey" FOREIGN KEY (manager_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."departments" validate constraint "departments_manager_membership_fkey";

alter table "public"."invoice_line_items" add constraint "invoice_line_items_amenity_booking_charge_id_fkey" FOREIGN KEY (amenity_booking_charge_id) REFERENCES public.legacy_amenity_booking_charges(id) ON DELETE SET NULL not valid;

alter table "public"."invoice_line_items" validate constraint "invoice_line_items_amenity_booking_charge_id_fkey";

alter table "public"."invoice_line_items" add constraint "invoice_line_items_total_amount_check" CHECK ((total_amount >= (0)::numeric)) not valid;

alter table "public"."invoice_line_items" validate constraint "invoice_line_items_total_amount_check";

alter table "public"."invoice_line_items" add constraint "invoice_line_items_unit_amount_check" CHECK ((unit_amount >= (0)::numeric)) not valid;

alter table "public"."invoice_line_items" validate constraint "invoice_line_items_unit_amount_check";

alter table "public"."invoices" add constraint "invoices_booking_occurrence_id_fkey" FOREIGN KEY (booking_occurrence_id) REFERENCES public.legacy_amenity_booking_occurrences(id) ON DELETE SET NULL not valid;

alter table "public"."invoices" validate constraint "invoices_booking_occurrence_id_fkey";

alter table "public"."invoices" add constraint "invoices_check" CHECK ((due_at >= issued_at)) not valid;

alter table "public"."invoices" validate constraint "invoices_check";

alter table "public"."invoices" add constraint "invoices_community_id_invoice_number_key" UNIQUE using index "invoices_community_id_invoice_number_key";

alter table "public"."invoices" add constraint "invoices_created_by_membership_id_fkey" FOREIGN KEY (created_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."invoices" validate constraint "invoices_created_by_membership_id_fkey";

alter table "public"."invoices" add constraint "invoices_liable_unit_id_fkey" FOREIGN KEY (liable_unit_id) REFERENCES public.units(id) ON DELETE RESTRICT not valid;

alter table "public"."invoices" validate constraint "invoices_liable_unit_id_fkey";

alter table "public"."invoices" add constraint "invoices_subtotal_check" CHECK ((subtotal >= (0)::numeric)) not valid;

alter table "public"."invoices" validate constraint "invoices_subtotal_check";

alter table "public"."invoices" add constraint "invoices_tax_amount_check" CHECK ((tax_amount >= (0)::numeric)) not valid;

alter table "public"."invoices" validate constraint "invoices_tax_amount_check";

alter table "public"."invoices" add constraint "invoices_total_amount_check" CHECK ((total_amount >= (0)::numeric)) not valid;

alter table "public"."invoices" validate constraint "invoices_total_amount_check";

alter table "public"."legacy_amenity_booking_charges" add constraint "amenity_booking_charges_amount_check" CHECK ((amount >= (0)::numeric)) not valid;

alter table "public"."legacy_amenity_booking_charges" validate constraint "amenity_booking_charges_amount_check";

alter table "public"."legacy_amenity_booking_charges" add constraint "amenity_booking_charges_booking_occurrence_id_fkey" FOREIGN KEY (booking_occurrence_id) REFERENCES public.legacy_amenity_booking_occurrences(id) ON DELETE CASCADE not valid;

alter table "public"."legacy_amenity_booking_charges" validate constraint "amenity_booking_charges_booking_occurrence_id_fkey";

alter table "public"."legacy_amenity_booking_occurrences" add constraint "amenity_booking_occurrences_amenity_id_fkey" FOREIGN KEY (amenity_id) REFERENCES public.amenities(id) ON DELETE RESTRICT not valid;

alter table "public"."legacy_amenity_booking_occurrences" validate constraint "amenity_booking_occurrences_amenity_id_fkey";

alter table "public"."legacy_amenity_booking_occurrences" add constraint "amenity_booking_occurrences_approval_by_membership_id_fkey" FOREIGN KEY (approval_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."legacy_amenity_booking_occurrences" validate constraint "amenity_booking_occurrences_approval_by_membership_id_fkey";

alter table "public"."legacy_amenity_booking_occurrences" add constraint "amenity_booking_occurrences_booking_series_id_fkey" FOREIGN KEY (booking_series_id) REFERENCES public.legacy_amenity_booking_series(id) ON DELETE CASCADE not valid;

alter table "public"."legacy_amenity_booking_occurrences" validate constraint "amenity_booking_occurrences_booking_series_id_fkey";

alter table "public"."legacy_amenity_booking_occurrences" add constraint "amenity_booking_occurrences_check" CHECK ((ends_at > starts_at)) not valid;

alter table "public"."legacy_amenity_booking_occurrences" validate constraint "amenity_booking_occurrences_check";

alter table "public"."legacy_amenity_booking_occurrences" add constraint "amenity_booking_occurrences_no_approved_overlap" EXCLUDE USING gist (amenity_id WITH =, tstzrange(starts_at, ends_at, '[)'::text) WITH &&) WHERE ((status = 'approved'::public.booking_status));

alter table "public"."legacy_amenity_booking_series" add constraint "amenity_booking_series_amenity_id_fkey" FOREIGN KEY (amenity_id) REFERENCES public.amenities(id) ON DELETE RESTRICT not valid;

alter table "public"."legacy_amenity_booking_series" validate constraint "amenity_booking_series_amenity_id_fkey";

alter table "public"."legacy_amenity_booking_series" add constraint "amenity_booking_series_booked_by_membership_id_fkey" FOREIGN KEY (booked_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."legacy_amenity_booking_series" validate constraint "amenity_booking_series_booked_by_membership_id_fkey";

alter table "public"."legacy_amenity_booking_series" add constraint "amenity_booking_series_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."legacy_amenity_booking_series" validate constraint "amenity_booking_series_community_id_fkey";

alter table "public"."legacy_amenity_booking_series" add constraint "amenity_booking_series_liable_unit_id_fkey" FOREIGN KEY (liable_unit_id) REFERENCES public.units(id) ON DELETE RESTRICT not valid;

alter table "public"."legacy_amenity_booking_series" validate constraint "amenity_booking_series_liable_unit_id_fkey";

alter table "public"."legacy_amenity_financial_events" add constraint "amenity_financial_events_actor_membership_id_fkey" FOREIGN KEY (actor_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."legacy_amenity_financial_events" validate constraint "amenity_financial_events_actor_membership_id_fkey";

alter table "public"."legacy_amenity_financial_events" add constraint "amenity_financial_events_booking_occurrence_id_fkey" FOREIGN KEY (booking_occurrence_id) REFERENCES public.legacy_amenity_booking_occurrences(id) ON DELETE CASCADE not valid;

alter table "public"."legacy_amenity_financial_events" validate constraint "amenity_financial_events_booking_occurrence_id_fkey";

alter table "public"."legacy_notifications" add constraint "notifications_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."legacy_notifications" validate constraint "notifications_community_id_fkey";

alter table "public"."legacy_notifications" add constraint "notifications_recipient_membership_id_fkey" FOREIGN KEY (recipient_membership_id) REFERENCES public.community_memberships(id) ON DELETE CASCADE not valid;

alter table "public"."legacy_notifications" validate constraint "notifications_recipient_membership_id_fkey";

alter table "public"."legacy_visitor_events" add constraint "visitor_events_actor_membership_id_fkey" FOREIGN KEY (actor_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."legacy_visitor_events" validate constraint "visitor_events_actor_membership_id_fkey";

alter table "public"."legacy_visitor_events" add constraint "visitor_events_visitor_access_request_id_fkey" FOREIGN KEY (visitor_access_request_id) REFERENCES public.visitor_access_requests(id) ON DELETE CASCADE not valid;

alter table "public"."legacy_visitor_events" validate constraint "visitor_events_visitor_access_request_id_fkey";

alter table "public"."media_assets" add constraint "media_assets_byte_size_check" CHECK ((byte_size >= 0)) not valid;

alter table "public"."media_assets" validate constraint "media_assets_byte_size_check";

alter table "public"."media_assets" add constraint "media_assets_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."media_assets" validate constraint "media_assets_community_id_fkey";

alter table "public"."media_assets" add constraint "media_assets_storage_path_key" UNIQUE using index "media_assets_storage_path_key";

alter table "public"."media_assets" add constraint "media_assets_uploaded_by_membership_id_fkey" FOREIGN KEY (uploaded_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."media_assets" validate constraint "media_assets_uploaded_by_membership_id_fkey";

alter table "public"."notices" add constraint "notices_check" CHECK (((expires_at IS NULL) OR (published_at IS NULL) OR (expires_at > published_at))) not valid;

alter table "public"."notices" validate constraint "notices_check";

alter table "public"."notification_deliveries" add constraint "notification_deliveries_notification_id_fkey" FOREIGN KEY (notification_id) REFERENCES public.legacy_notifications(id) ON DELETE CASCADE not valid;

alter table "public"."notification_deliveries" validate constraint "notification_deliveries_notification_id_fkey";

alter table "public"."notifications" add constraint "notifications_recipient_membership_id_fkey1" FOREIGN KEY (recipient_membership_id) REFERENCES public.community_memberships(id) ON DELETE CASCADE not valid;

alter table "public"."notifications" validate constraint "notifications_recipient_membership_id_fkey1";

alter table "public"."payment_events" add constraint "payment_events_actor_membership_id_fkey" FOREIGN KEY (actor_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."payment_events" validate constraint "payment_events_actor_membership_id_fkey";

alter table "public"."payments" add constraint "payments_amount_check" CHECK ((amount > (0)::numeric)) not valid;

alter table "public"."payments" validate constraint "payments_amount_check";

alter table "public"."payments" add constraint "payments_payer_membership_id_fkey" FOREIGN KEY (payer_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."payments" validate constraint "payments_payer_membership_id_fkey";

alter table "public"."payments" add constraint "payments_provider_reference_key" UNIQUE using index "payments_provider_reference_key";

alter table "public"."payments" add constraint "payments_recorded_by_membership_id_fkey" FOREIGN KEY (recorded_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."payments" validate constraint "payments_recorded_by_membership_id_fkey";

alter table "public"."policies" add constraint "policies_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."policies" validate constraint "policies_community_id_fkey";

alter table "public"."policies" add constraint "policies_created_by_membership_id_fkey" FOREIGN KEY (created_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."policies" validate constraint "policies_created_by_membership_id_fkey";

alter table "public"."policies" add constraint "policies_current_revision_fkey" FOREIGN KEY (current_revision_id) REFERENCES public.policy_revisions(id) ON DELETE SET NULL not valid;

alter table "public"."policies" validate constraint "policies_current_revision_fkey";

alter table "public"."policy_revisions" add constraint "policy_revisions_authored_by_membership_id_fkey" FOREIGN KEY (authored_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."policy_revisions" validate constraint "policy_revisions_authored_by_membership_id_fkey";

alter table "public"."policy_revisions" add constraint "policy_revisions_policy_id_fkey" FOREIGN KEY (policy_id) REFERENCES public.policies(id) ON DELETE CASCADE not valid;

alter table "public"."policy_revisions" validate constraint "policy_revisions_policy_id_fkey";

alter table "public"."policy_revisions" add constraint "policy_revisions_policy_id_revision_number_key" UNIQUE using index "policy_revisions_policy_id_revision_number_key";

alter table "public"."policy_revisions" add constraint "policy_revisions_revision_number_check" CHECK ((revision_number > 0)) not valid;

alter table "public"."policy_revisions" validate constraint "policy_revisions_revision_number_check";

alter table "public"."profiles" add constraint "profiles_association_id_fkey" FOREIGN KEY (legacy_community_id) REFERENCES public.communities(id) ON DELETE SET NULL not valid;

alter table "public"."profiles" validate constraint "profiles_association_id_fkey";

alter table "public"."profiles" add constraint "profiles_avatar_media_fkey" FOREIGN KEY (avatar_media_id) REFERENCES public.media_assets(id) ON DELETE SET NULL not valid;

alter table "public"."profiles" validate constraint "profiles_avatar_media_fkey";

alter table "public"."resident_invites" add constraint "invitations_association_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."resident_invites" validate constraint "invitations_association_id_fkey";

alter table "public"."resident_invites" add constraint "invitations_created_by_fkey" FOREIGN KEY (legacy_created_by_profile_id) REFERENCES auth.users(id) ON DELETE SET NULL not valid;

alter table "public"."resident_invites" validate constraint "invitations_created_by_fkey";

alter table "public"."resident_invites" add constraint "invitations_token_hash_key" UNIQUE using index "invitations_token_hash_key";

alter table "public"."saved_visitors" add constraint "saved_visitors_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."saved_visitors" validate constraint "saved_visitors_community_id_fkey";

alter table "public"."saved_visitors" add constraint "saved_visitors_created_by_membership_id_fkey" FOREIGN KEY (created_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE CASCADE not valid;

alter table "public"."saved_visitors" validate constraint "saved_visitors_created_by_membership_id_fkey";

alter table "public"."staff_assignments" add constraint "staff_assignments_check" CHECK (((ended_at IS NULL) OR (ended_at >= started_at))) not valid;

alter table "public"."staff_assignments" validate constraint "staff_assignments_check";

alter table "public"."unit_residencies" add constraint "unit_residencies_check" CHECK (((ended_at IS NULL) OR (ended_at >= started_at))) not valid;

alter table "public"."unit_residencies" validate constraint "unit_residencies_check";

alter table "public"."unit_residencies" add constraint "unit_residencies_created_by_membership_id_fkey" FOREIGN KEY (created_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."unit_residencies" validate constraint "unit_residencies_created_by_membership_id_fkey";

alter table "public"."unit_residencies" add constraint "unit_residencies_nominated_successor_residency_id_fkey" FOREIGN KEY (nominated_successor_residency_id) REFERENCES public.unit_residencies(id) ON DELETE SET NULL not valid;

alter table "public"."unit_residencies" validate constraint "unit_residencies_nominated_successor_residency_id_fkey";

alter table "public"."units" add constraint "apartments_association_id_code_key" UNIQUE using index "apartments_association_id_code_key";

alter table "public"."units" add constraint "apartments_association_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."units" validate constraint "apartments_association_id_fkey";

alter table "public"."units" add constraint "apartments_unit_id_fkey" FOREIGN KEY (building_id) REFERENCES public.buildings(id) ON DELETE SET NULL not valid;

alter table "public"."units" validate constraint "apartments_unit_id_fkey";

alter table "public"."visitor_access_requests" add constraint "visitor_access_requests_check" CHECK (((expected_until IS NULL) OR (expected_until > expected_from))) not valid;

alter table "public"."visitor_access_requests" validate constraint "visitor_access_requests_check";

alter table "public"."visitor_access_requests" add constraint "visitor_access_requests_checked_in_by_membership_id_fkey" FOREIGN KEY (checked_in_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."visitor_access_requests" validate constraint "visitor_access_requests_checked_in_by_membership_id_fkey";

alter table "public"."visitor_access_requests" add constraint "visitor_access_requests_checked_out_by_membership_id_fkey" FOREIGN KEY (checked_out_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."visitor_access_requests" validate constraint "visitor_access_requests_checked_out_by_membership_id_fkey";

alter table "public"."visitor_access_requests" add constraint "visitor_access_requests_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."visitor_access_requests" validate constraint "visitor_access_requests_community_id_fkey";

alter table "public"."visitor_access_requests" add constraint "visitor_access_requests_decided_by_membership_id_fkey" FOREIGN KEY (decided_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."visitor_access_requests" validate constraint "visitor_access_requests_decided_by_membership_id_fkey";

alter table "public"."visitor_access_requests" add constraint "visitor_access_requests_requested_by_membership_id_fkey" FOREIGN KEY (requested_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."visitor_access_requests" validate constraint "visitor_access_requests_requested_by_membership_id_fkey";

alter table "public"."visitor_access_requests" add constraint "visitor_access_requests_saved_visitor_id_fkey" FOREIGN KEY (saved_visitor_id) REFERENCES public.saved_visitors(id) ON DELETE SET NULL not valid;

alter table "public"."visitor_access_requests" validate constraint "visitor_access_requests_saved_visitor_id_fkey";

alter table "public"."visitor_access_requests" add constraint "visitor_access_requests_unit_id_fkey" FOREIGN KEY (unit_id) REFERENCES public.units(id) ON DELETE RESTRICT not valid;

alter table "public"."visitor_access_requests" validate constraint "visitor_access_requests_unit_id_fkey";

alter table "public"."visitor_attachments" add constraint "visitor_attachments_attached_by_membership_id_fkey" FOREIGN KEY (attached_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."visitor_attachments" validate constraint "visitor_attachments_attached_by_membership_id_fkey";

alter table "public"."visitor_attachments" add constraint "visitor_attachments_media_asset_id_fkey" FOREIGN KEY (media_asset_id) REFERENCES public.media_assets(id) ON DELETE CASCADE not valid;

alter table "public"."visitor_attachments" validate constraint "visitor_attachments_media_asset_id_fkey";

alter table "public"."visitor_attachments" add constraint "visitor_attachments_visitor_access_request_id_fkey" FOREIGN KEY (visitor_access_request_id) REFERENCES public.visitor_access_requests(id) ON DELETE CASCADE not valid;

alter table "public"."visitor_attachments" validate constraint "visitor_attachments_visitor_access_request_id_fkey";

alter table "public"."visitor_events" add constraint "visitor_events_actor_membership_id_fkey1" FOREIGN KEY (actor_membership_id) REFERENCES public.community_memberships(id) not valid;

alter table "public"."visitor_events" validate constraint "visitor_events_actor_membership_id_fkey1";

alter table "public"."work_order_assignments" add constraint "work_order_assignments_assigned_by_membership_id_fkey" FOREIGN KEY (assigned_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."work_order_assignments" validate constraint "work_order_assignments_assigned_by_membership_id_fkey";

alter table "public"."work_order_assignments" add constraint "work_order_assignments_work_order_id_staff_assignment_id_key" UNIQUE using index "work_order_assignments_work_order_id_staff_assignment_id_key";

alter table "public"."work_order_attachments" add constraint "work_order_attachments_attached_by_membership_id_fkey" FOREIGN KEY (attached_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."work_order_attachments" validate constraint "work_order_attachments_attached_by_membership_id_fkey";

alter table "public"."work_order_attachments" add constraint "work_order_attachments_media_asset_id_fkey" FOREIGN KEY (media_asset_id) REFERENCES public.media_assets(id) ON DELETE CASCADE not valid;

alter table "public"."work_order_attachments" validate constraint "work_order_attachments_media_asset_id_fkey";

alter table "public"."work_order_attachments" add constraint "work_order_attachments_work_order_id_fkey" FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id) ON DELETE CASCADE not valid;

alter table "public"."work_order_attachments" validate constraint "work_order_attachments_work_order_id_fkey";

alter table "public"."work_order_completion_verifications" add constraint "work_order_completion_verificati_verified_by_membership_id_fkey" FOREIGN KEY (verified_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."work_order_completion_verifications" validate constraint "work_order_completion_verificati_verified_by_membership_id_fkey";

alter table "public"."work_order_completion_verifications" add constraint "work_order_completion_verifications_rating_check" CHECK (((rating >= 1) AND (rating <= 5))) not valid;

alter table "public"."work_order_completion_verifications" validate constraint "work_order_completion_verifications_rating_check";

alter table "public"."work_order_completion_verifications" add constraint "work_order_completion_verifications_work_order_id_fkey" FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id) ON DELETE CASCADE not valid;

alter table "public"."work_order_completion_verifications" validate constraint "work_order_completion_verifications_work_order_id_fkey";

alter table "public"."work_order_proposals" add constraint "work_order_proposals_check" CHECK (((proposed_end_at IS NULL) OR (proposed_start_at IS NULL) OR (proposed_end_at > proposed_start_at))) not valid;

alter table "public"."work_order_proposals" validate constraint "work_order_proposals_check";

alter table "public"."work_order_proposals" add constraint "work_order_proposals_proposed_by_membership_id_fkey" FOREIGN KEY (proposed_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."work_order_proposals" validate constraint "work_order_proposals_proposed_by_membership_id_fkey";

alter table "public"."work_order_proposals" add constraint "work_order_proposals_responded_by_membership_id_fkey" FOREIGN KEY (responded_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."work_order_proposals" validate constraint "work_order_proposals_responded_by_membership_id_fkey";

alter table "public"."work_order_proposals" add constraint "work_order_proposals_work_order_id_fkey" FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id) ON DELETE CASCADE not valid;

alter table "public"."work_order_proposals" validate constraint "work_order_proposals_work_order_id_fkey";

alter table "public"."work_order_views" add constraint "work_order_views_membership_id_fkey" FOREIGN KEY (membership_id) REFERENCES public.community_memberships(id) ON DELETE CASCADE not valid;

alter table "public"."work_order_views" validate constraint "work_order_views_membership_id_fkey";

alter table "public"."work_order_views" add constraint "work_order_views_work_order_id_fkey" FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id) ON DELETE CASCADE not valid;

alter table "public"."work_order_views" validate constraint "work_order_views_work_order_id_fkey";

alter table "public"."work_order_views" add constraint "work_order_views_work_order_id_membership_id_key" UNIQUE using index "work_order_views_work_order_id_membership_id_key";

alter table "public"."work_orders" add constraint "work_orders_check" CHECK (((scheduled_end_at IS NULL) OR (scheduled_start_at IS NULL) OR (scheduled_end_at > scheduled_start_at))) not valid;

alter table "public"."work_orders" validate constraint "work_orders_check";

alter table "public"."work_orders" add constraint "work_orders_created_by_membership_id_fkey" FOREIGN KEY (created_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."work_orders" validate constraint "work_orders_created_by_membership_id_fkey";

alter table "public"."worker_availability_rules" add constraint "worker_availability_rules_check" CHECK ((end_time > start_time)) not valid;

alter table "public"."worker_availability_rules" validate constraint "worker_availability_rules_check";

alter table "public"."worker_availability_rules" add constraint "worker_availability_rules_check1" CHECK (((effective_to IS NULL) OR (effective_to >= effective_from))) not valid;

alter table "public"."worker_availability_rules" validate constraint "worker_availability_rules_check1";

alter table "public"."worker_unavailability" add constraint "worker_unavailability_check" CHECK ((ends_at > starts_at)) not valid;

alter table "public"."worker_unavailability" validate constraint "worker_unavailability_check";

alter table "public"."access_requests" add constraint "access_requests_applicant_profile_id_fkey" FOREIGN KEY (applicant_profile_id) REFERENCES public.profiles(id) ON DELETE CASCADE not valid;

alter table "public"."access_requests" validate constraint "access_requests_applicant_profile_id_fkey";

alter table "public"."access_requests" add constraint "access_requests_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."access_requests" validate constraint "access_requests_community_id_fkey";

alter table "public"."access_requests" add constraint "access_requests_requested_unit_id_fkey" FOREIGN KEY (requested_unit_id) REFERENCES public.units(id) ON DELETE SET NULL not valid;

alter table "public"."access_requests" validate constraint "access_requests_requested_unit_id_fkey";

alter table "public"."access_requests" add constraint "access_requests_reviewed_by_membership_id_fkey" FOREIGN KEY (reviewed_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."access_requests" validate constraint "access_requests_reviewed_by_membership_id_fkey";

alter table "public"."amenities" add constraint "amenities_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."amenities" validate constraint "amenities_community_id_fkey";

alter table "public"."amenity_booking_charges" add constraint "amenity_booking_charges_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."amenity_booking_charges" validate constraint "amenity_booking_charges_community_id_fkey";

alter table "public"."amenity_booking_guests" add constraint "amenity_booking_guests_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."amenity_booking_guests" validate constraint "amenity_booking_guests_community_id_fkey";

alter table "public"."amenity_bookings" add constraint "amenity_bookings_amenity_id_fkey" FOREIGN KEY (amenity_id) REFERENCES public.amenities(id) ON DELETE CASCADE not valid;

alter table "public"."amenity_bookings" validate constraint "amenity_bookings_amenity_id_fkey";

alter table "public"."amenity_bookings" add constraint "amenity_bookings_amenity_id_tstzrange_excl" EXCLUDE USING gist (amenity_id WITH =, tstzrange(starts_at, ends_at, '[)'::text) WITH &&) WHERE ((status = ANY (ARRAY['requested'::public.booking_status, 'approved'::public.booking_status])));

alter table "public"."amenity_bookings" add constraint "amenity_bookings_booked_by_membership_id_fkey" FOREIGN KEY (booked_by_membership_id) REFERENCES public.community_memberships(id) not valid;

alter table "public"."amenity_bookings" validate constraint "amenity_bookings_booked_by_membership_id_fkey";

alter table "public"."amenity_bookings" add constraint "amenity_bookings_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."amenity_bookings" validate constraint "amenity_bookings_community_id_fkey";

alter table "public"."amenity_bookings" add constraint "amenity_bookings_unit_id_fkey" FOREIGN KEY (unit_id) REFERENCES public.units(id) ON DELETE SET NULL not valid;

alter table "public"."amenity_bookings" validate constraint "amenity_bookings_unit_id_fkey";

alter table "public"."amenity_financial_events" add constraint "amenity_financial_events_booking_charge_id_fkey" FOREIGN KEY (booking_charge_id) REFERENCES public.amenity_booking_charges(id) ON DELETE CASCADE not valid;

alter table "public"."amenity_financial_events" validate constraint "amenity_financial_events_booking_charge_id_fkey";

alter table "public"."amenity_financial_events" add constraint "amenity_financial_events_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."amenity_financial_events" validate constraint "amenity_financial_events_community_id_fkey";

alter table "public"."audit_events" add constraint "audit_events_actor_membership_id_fkey" FOREIGN KEY (actor_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."audit_events" validate constraint "audit_events_actor_membership_id_fkey";

alter table "public"."audit_events" add constraint "audit_events_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."audit_events" validate constraint "audit_events_community_id_fkey";

alter table "public"."blacklisted_residents" add constraint "blacklisted_residents_blacklisted_by_membership_id_fkey" FOREIGN KEY (blacklisted_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."blacklisted_residents" validate constraint "blacklisted_residents_blacklisted_by_membership_id_fkey";

alter table "public"."blacklisted_residents" add constraint "blacklisted_residents_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."blacklisted_residents" validate constraint "blacklisted_residents_community_id_fkey";

alter table "public"."blacklisted_residents" add constraint "blacklisted_residents_profile_id_fkey" FOREIGN KEY (profile_id) REFERENCES public.profiles(id) ON DELETE CASCADE not valid;

alter table "public"."blacklisted_residents" validate constraint "blacklisted_residents_profile_id_fkey";

alter table "public"."blacklisted_residents" add constraint "blacklisted_residents_revoked_by_membership_id_fkey" FOREIGN KEY (revoked_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."blacklisted_residents" validate constraint "blacklisted_residents_revoked_by_membership_id_fkey";

alter table "public"."blacklisted_service_providers" add constraint "blacklisted_service_providers_blacklisted_by_membership_id_fkey" FOREIGN KEY (blacklisted_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."blacklisted_service_providers" validate constraint "blacklisted_service_providers_blacklisted_by_membership_id_fkey";

alter table "public"."blacklisted_service_providers" add constraint "blacklisted_service_providers_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."blacklisted_service_providers" validate constraint "blacklisted_service_providers_community_id_fkey";

alter table "public"."blacklisted_service_providers" add constraint "blacklisted_service_providers_revoked_by_membership_id_fkey" FOREIGN KEY (revoked_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."blacklisted_service_providers" validate constraint "blacklisted_service_providers_revoked_by_membership_id_fkey";

alter table "public"."blacklisted_service_providers" add constraint "blacklisted_service_providers_service_provider_id_fkey" FOREIGN KEY (service_provider_id) REFERENCES public.service_providers(id) ON DELETE CASCADE not valid;

alter table "public"."blacklisted_service_providers" validate constraint "blacklisted_service_providers_service_provider_id_fkey";

alter table "public"."booking_charges" add constraint "booking_charges_booking_id_fkey" FOREIGN KEY (booking_id) REFERENCES public.amenity_bookings(id) ON DELETE CASCADE not valid;

alter table "public"."booking_charges" validate constraint "booking_charges_booking_id_fkey";

alter table "public"."booking_refunds" add constraint "booking_refunds_booking_charge_id_fkey" FOREIGN KEY (booking_charge_id) REFERENCES public.booking_charges(id) ON DELETE CASCADE not valid;

alter table "public"."booking_refunds" validate constraint "booking_refunds_booking_charge_id_fkey";

alter table "public"."community_admin_terms" add constraint "community_admin_terms_admin_membership_id_fkey" FOREIGN KEY (admin_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."community_admin_terms" validate constraint "community_admin_terms_admin_membership_id_fkey";

alter table "public"."community_admin_terms" add constraint "community_admin_terms_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."community_admin_terms" validate constraint "community_admin_terms_community_id_fkey";

alter table "public"."community_admin_terms" add constraint "community_admin_terms_transferred_by_membership_id_fkey" FOREIGN KEY (transferred_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."community_admin_terms" validate constraint "community_admin_terms_transferred_by_membership_id_fkey";

alter table "public"."community_billing_settings" add constraint "community_billing_settings_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."community_billing_settings" validate constraint "community_billing_settings_community_id_fkey";

alter table "public"."community_features" add constraint "community_features_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."community_features" validate constraint "community_features_community_id_fkey";

alter table "public"."community_features" add constraint "community_features_feature_code_fkey" FOREIGN KEY (feature_code) REFERENCES public.feature_catalog(code) not valid;

alter table "public"."community_features" validate constraint "community_features_feature_code_fkey";

alter table "public"."community_memberships" add constraint "community_memberships_check" CHECK (((status = 'ended'::public.membership_status) = (ended_at IS NOT NULL))) not valid;

alter table "public"."community_memberships" validate constraint "community_memberships_check";

alter table "public"."community_memberships" add constraint "community_memberships_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."community_memberships" validate constraint "community_memberships_community_id_fkey";

alter table "public"."community_memberships" add constraint "community_memberships_department_id_fkey" FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL not valid;

alter table "public"."community_memberships" validate constraint "community_memberships_department_id_fkey";

alter table "public"."community_memberships" add constraint "community_memberships_profile_id_fkey" FOREIGN KEY (profile_id) REFERENCES public.profiles(id) ON DELETE CASCADE not valid;

alter table "public"."community_memberships" validate constraint "community_memberships_profile_id_fkey";

alter table "public"."community_settings" add constraint "community_settings_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."community_settings" validate constraint "community_settings_community_id_fkey";

alter table "public"."community_settings" add constraint "community_settings_updated_by_membership_id_fkey" FOREIGN KEY (updated_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."community_settings" validate constraint "community_settings_updated_by_membership_id_fkey";

alter table "public"."complaint_categories" add constraint "complaint_categories_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."complaint_categories" validate constraint "complaint_categories_community_id_fkey";

alter table "public"."complaint_categories" add constraint "complaint_categories_skill_id_fkey" FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE SET NULL not valid;

alter table "public"."complaint_categories" validate constraint "complaint_categories_skill_id_fkey";

alter table "public"."complaint_comments" add constraint "complaint_comments_author_membership_id_fkey" FOREIGN KEY (author_membership_id) REFERENCES public.community_memberships(id) not valid;

alter table "public"."complaint_comments" validate constraint "complaint_comments_author_membership_id_fkey";

alter table "public"."complaint_comments" add constraint "complaint_comments_complaint_id_fkey" FOREIGN KEY (complaint_id) REFERENCES public.complaints(id) ON DELETE CASCADE not valid;

alter table "public"."complaint_comments" validate constraint "complaint_comments_complaint_id_fkey";

alter table "public"."complaint_department_requests" add constraint "complaint_department_requests_complaint_id_fkey" FOREIGN KEY (complaint_id) REFERENCES public.complaints(id) ON DELETE CASCADE not valid;

alter table "public"."complaint_department_requests" validate constraint "complaint_department_requests_complaint_id_fkey";

alter table "public"."complaint_department_requests" add constraint "complaint_department_requests_decided_by_membership_id_fkey" FOREIGN KEY (decided_by_membership_id) REFERENCES public.community_memberships(id) not valid;

alter table "public"."complaint_department_requests" validate constraint "complaint_department_requests_decided_by_membership_id_fkey";

alter table "public"."complaint_department_requests" add constraint "complaint_department_requests_from_department_id_fkey" FOREIGN KEY (from_department_id) REFERENCES public.departments(id) ON DELETE SET NULL not valid;

alter table "public"."complaint_department_requests" validate constraint "complaint_department_requests_from_department_id_fkey";

alter table "public"."complaint_department_requests" add constraint "complaint_department_requests_requested_by_membership_id_fkey" FOREIGN KEY (requested_by_membership_id) REFERENCES public.community_memberships(id) not valid;

alter table "public"."complaint_department_requests" validate constraint "complaint_department_requests_requested_by_membership_id_fkey";

alter table "public"."complaint_department_requests" add constraint "complaint_department_requests_to_department_id_fkey" FOREIGN KEY (to_department_id) REFERENCES public.departments(id) ON DELETE SET NULL not valid;

alter table "public"."complaint_department_requests" validate constraint "complaint_department_requests_to_department_id_fkey";

alter table "public"."complaint_events" add constraint "complaint_events_actor_membership_id_fkey" FOREIGN KEY (actor_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."complaint_events" validate constraint "complaint_events_actor_membership_id_fkey";

alter table "public"."complaint_events" add constraint "complaint_events_complaint_id_fkey" FOREIGN KEY (complaint_id) REFERENCES public.complaints(id) ON DELETE CASCADE not valid;

alter table "public"."complaint_events" validate constraint "complaint_events_complaint_id_fkey";

alter table "public"."complaint_read_state" add constraint "complaint_read_state_complaint_id_fkey" FOREIGN KEY (complaint_id) REFERENCES public.complaints(id) ON DELETE CASCADE not valid;

alter table "public"."complaint_read_state" validate constraint "complaint_read_state_complaint_id_fkey";

alter table "public"."complaint_read_state" add constraint "complaint_read_state_membership_id_fkey" FOREIGN KEY (membership_id) REFERENCES public.community_memberships(id) ON DELETE CASCADE not valid;

alter table "public"."complaint_read_state" validate constraint "complaint_read_state_membership_id_fkey";

alter table "public"."complaints" add constraint "complaints_assigned_to_membership_id_fkey" FOREIGN KEY (assigned_to_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."complaints" validate constraint "complaints_assigned_to_membership_id_fkey";

alter table "public"."complaints" add constraint "complaints_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."complaints" validate constraint "complaints_community_id_fkey";

alter table "public"."complaints" add constraint "complaints_department_id_fkey" FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL not valid;

alter table "public"."complaints" validate constraint "complaints_department_id_fkey";

alter table "public"."complaints" add constraint "complaints_raised_by_membership_id_fkey" FOREIGN KEY (raised_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."complaints" validate constraint "complaints_raised_by_membership_id_fkey";

alter table "public"."complaints" add constraint "complaints_skill_id_fkey" FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE SET NULL not valid;

alter table "public"."complaints" validate constraint "complaints_skill_id_fkey";

alter table "public"."conversation_messages" add constraint "conversation_messages_author_membership_id_fkey" FOREIGN KEY (author_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."conversation_messages" validate constraint "conversation_messages_author_membership_id_fkey";

alter table "public"."conversation_messages" add constraint "conversation_messages_author_provider_id_fkey" FOREIGN KEY (author_provider_id) REFERENCES public.service_providers(id) ON DELETE SET NULL not valid;

alter table "public"."conversation_messages" validate constraint "conversation_messages_author_provider_id_fkey";

alter table "public"."conversation_messages" add constraint "conversation_messages_conversation_id_fkey" FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE not valid;

alter table "public"."conversation_messages" validate constraint "conversation_messages_conversation_id_fkey";

alter table "public"."conversations" add constraint "conversations_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."conversations" validate constraint "conversations_community_id_fkey";

alter table "public"."conversations" add constraint "conversations_department_id_fkey" FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE CASCADE not valid;

alter table "public"."conversations" validate constraint "conversations_department_id_fkey";

alter table "public"."conversations" add constraint "conversations_department_tenant_fkey" FOREIGN KEY (department_id, community_id) REFERENCES public.departments(id, community_id) ON DELETE CASCADE not valid;

alter table "public"."conversations" validate constraint "conversations_department_tenant_fkey";

alter table "public"."conversations" add constraint "conversations_service_provider_id_fkey" FOREIGN KEY (service_provider_id) REFERENCES public.service_providers(id) ON DELETE CASCADE not valid;

alter table "public"."conversations" validate constraint "conversations_service_provider_id_fkey";

alter table "public"."department_categories" add constraint "department_categories_category_id_fkey" FOREIGN KEY (category_id) REFERENCES public.complaint_categories(id) ON DELETE CASCADE not valid;

alter table "public"."department_categories" validate constraint "department_categories_category_id_fkey";

alter table "public"."department_categories" add constraint "department_categories_department_id_fkey" FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE CASCADE not valid;

alter table "public"."department_categories" validate constraint "department_categories_department_id_fkey";

alter table "public"."department_skills" add constraint "department_skills_department_id_fkey" FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE CASCADE not valid;

alter table "public"."department_skills" validate constraint "department_skills_department_id_fkey";

alter table "public"."department_skills" add constraint "department_skills_skill_id_fkey" FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE RESTRICT not valid;

alter table "public"."department_skills" validate constraint "department_skills_skill_id_fkey";

alter table "public"."departments" add constraint "departments_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."departments" validate constraint "departments_community_id_fkey";

alter table "public"."dispatch_tasks" add constraint "dispatch_tasks_complaint_id_fkey" FOREIGN KEY (complaint_id) REFERENCES public.complaints(id) ON DELETE CASCADE not valid;

alter table "public"."dispatch_tasks" validate constraint "dispatch_tasks_complaint_id_fkey";

alter table "public"."dispatch_tasks" add constraint "dispatch_tasks_departure_id_fkey" FOREIGN KEY (departure_id) REFERENCES public.staff_departures(id) ON DELETE CASCADE not valid;

alter table "public"."dispatch_tasks" validate constraint "dispatch_tasks_departure_id_fkey";

alter table "public"."dispatch_tasks" add constraint "dispatch_tasks_work_order_id_fkey" FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id) ON DELETE CASCADE not valid;

alter table "public"."dispatch_tasks" validate constraint "dispatch_tasks_work_order_id_fkey";

alter table "public"."dm_messages" add constraint "dm_messages_author_profile_id_fkey" FOREIGN KEY (author_profile_id) REFERENCES public.profiles(id) ON DELETE SET NULL not valid;

alter table "public"."dm_messages" validate constraint "dm_messages_author_profile_id_fkey";

alter table "public"."dm_messages" add constraint "dm_messages_thread_id_fkey" FOREIGN KEY (thread_id) REFERENCES public.dm_threads(id) ON DELETE CASCADE not valid;

alter table "public"."dm_messages" validate constraint "dm_messages_thread_id_fkey";

alter table "public"."dm_threads" add constraint "dm_threads_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."dm_threads" validate constraint "dm_threads_community_id_fkey";

alter table "public"."dm_threads" add constraint "dm_threads_participant_a_profile_id_fkey" FOREIGN KEY (participant_a_profile_id) REFERENCES public.profiles(id) ON DELETE CASCADE not valid;

alter table "public"."dm_threads" validate constraint "dm_threads_participant_a_profile_id_fkey";

alter table "public"."dm_threads" add constraint "dm_threads_participant_b_profile_id_fkey" FOREIGN KEY (participant_b_profile_id) REFERENCES public.profiles(id) ON DELETE CASCADE not valid;

alter table "public"."dm_threads" validate constraint "dm_threads_participant_b_profile_id_fkey";

alter table "public"."dm_threads" add constraint "dm_threads_work_order_id_fkey" FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id) ON DELETE CASCADE not valid;

alter table "public"."dm_threads" validate constraint "dm_threads_work_order_id_fkey";

alter table "public"."invoice_line_items" add constraint "invoice_line_items_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."invoice_line_items" validate constraint "invoice_line_items_community_id_fkey";

alter table "public"."invoice_line_items" add constraint "invoice_line_items_invoice_id_fkey" FOREIGN KEY (invoice_id) REFERENCES public.invoices(id) ON DELETE CASCADE not valid;

alter table "public"."invoice_line_items" validate constraint "invoice_line_items_invoice_id_fkey";

alter table "public"."invoice_line_items" add constraint "invoice_line_items_quantity_check" CHECK ((quantity > (0)::numeric)) not valid;

alter table "public"."invoice_line_items" validate constraint "invoice_line_items_quantity_check";

alter table "public"."invoices" add constraint "invoices_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."invoices" validate constraint "invoices_community_id_fkey";

alter table "public"."invoices" add constraint "invoices_membership_id_fkey" FOREIGN KEY (membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."invoices" validate constraint "invoices_membership_id_fkey";

alter table "public"."invoices" add constraint "invoices_unit_id_fkey" FOREIGN KEY (unit_id) REFERENCES public.units(id) ON DELETE SET NULL not valid;

alter table "public"."invoices" validate constraint "invoices_unit_id_fkey";

alter table "public"."material_movements" add constraint "material_movements_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."material_movements" validate constraint "material_movements_community_id_fkey";

alter table "public"."material_movements" add constraint "material_movements_post_id_fkey" FOREIGN KEY (post_id) REFERENCES public.security_posts(id) ON DELETE SET NULL not valid;

alter table "public"."material_movements" validate constraint "material_movements_post_id_fkey";

alter table "public"."material_movements" add constraint "material_movements_recorded_by_membership_id_fkey" FOREIGN KEY (recorded_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."material_movements" validate constraint "material_movements_recorded_by_membership_id_fkey";

alter table "public"."material_movements" add constraint "material_movements_unit_id_fkey" FOREIGN KEY (unit_id) REFERENCES public.units(id) ON DELETE SET NULL not valid;

alter table "public"."material_movements" validate constraint "material_movements_unit_id_fkey";

alter table "public"."notices" add constraint "notices_author_membership_id_fkey" FOREIGN KEY (author_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."notices" validate constraint "notices_author_membership_id_fkey";

alter table "public"."notices" add constraint "notices_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."notices" validate constraint "notices_community_id_fkey";

alter table "public"."notifications" add constraint "notifications_recipient_profile_id_fkey" FOREIGN KEY (recipient_profile_id) REFERENCES public.profiles(id) ON DELETE CASCADE not valid;

alter table "public"."notifications" validate constraint "notifications_recipient_profile_id_fkey";

alter table "public"."offline_reconcile_log" add constraint "offline_reconcile_log_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."offline_reconcile_log" validate constraint "offline_reconcile_log_community_id_fkey";

alter table "public"."offline_reconcile_log" add constraint "offline_reconcile_log_submitted_by_membership_id_fkey" FOREIGN KEY (submitted_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."offline_reconcile_log" validate constraint "offline_reconcile_log_submitted_by_membership_id_fkey";

alter table "public"."offline_reconcile_log" add constraint "offline_reconcile_log_visitor_request_id_fkey" FOREIGN KEY (visitor_request_id) REFERENCES public.visitor_requests(id) ON DELETE SET NULL not valid;

alter table "public"."offline_reconcile_log" validate constraint "offline_reconcile_log_visitor_request_id_fkey";

alter table "public"."payment_events" add constraint "payment_events_payment_id_fkey" FOREIGN KEY (payment_id) REFERENCES public.payments(id) ON DELETE CASCADE not valid;

alter table "public"."payment_events" validate constraint "payment_events_payment_id_fkey";

alter table "public"."payments" add constraint "payments_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."payments" validate constraint "payments_community_id_fkey";

alter table "public"."payments" add constraint "payments_failure_code_check" CHECK (((failure_code IS NULL) OR (status = 'failed'::public.payment_status))) not valid;

alter table "public"."payments" validate constraint "payments_failure_code_check";

alter table "public"."payments" add constraint "payments_invoice_id_fkey" FOREIGN KEY (invoice_id) REFERENCES public.invoices(id) ON DELETE RESTRICT not valid;

alter table "public"."payments" validate constraint "payments_invoice_id_fkey";

alter table "public"."payments" add constraint "payments_payer_profile_id_fkey" FOREIGN KEY (payer_profile_id) REFERENCES public.profiles(id) ON DELETE SET NULL not valid;

alter table "public"."payments" validate constraint "payments_payer_profile_id_fkey";

alter table "public"."payments" add constraint "payments_received_by_membership_id_fkey" FOREIGN KEY (received_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."payments" validate constraint "payments_received_by_membership_id_fkey";

alter table "public"."push_subscriptions" add constraint "push_subscriptions_profile_id_fkey" FOREIGN KEY (profile_id) REFERENCES public.profiles(id) ON DELETE CASCADE not valid;

alter table "public"."push_subscriptions" validate constraint "push_subscriptions_profile_id_fkey";

alter table "public"."resident_invites" add constraint "resident_invites_created_by_membership_id_fkey" FOREIGN KEY (created_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."resident_invites" validate constraint "resident_invites_created_by_membership_id_fkey";

alter table "public"."resident_invites" add constraint "resident_invites_intended_unit_id_fkey" FOREIGN KEY (intended_unit_id) REFERENCES public.units(id) ON DELETE RESTRICT not valid;

alter table "public"."resident_invites" validate constraint "resident_invites_intended_unit_id_fkey";

alter table "public"."resident_invites" add constraint "resident_invites_redeemed_by_profile_id_fkey" FOREIGN KEY (redeemed_by_profile_id) REFERENCES public.profiles(id) ON DELETE SET NULL not valid;

alter table "public"."resident_invites" validate constraint "resident_invites_redeemed_by_profile_id_fkey";

alter table "public"."security_incidents" add constraint "security_incidents_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."security_incidents" validate constraint "security_incidents_community_id_fkey";

alter table "public"."security_incidents" add constraint "security_incidents_post_id_fkey" FOREIGN KEY (post_id) REFERENCES public.security_posts(id) ON DELETE SET NULL not valid;

alter table "public"."security_incidents" validate constraint "security_incidents_post_id_fkey";

alter table "public"."security_incidents" add constraint "security_incidents_reported_by_membership_id_fkey" FOREIGN KEY (reported_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."security_incidents" validate constraint "security_incidents_reported_by_membership_id_fkey";

alter table "public"."security_posts" add constraint "security_posts_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."security_posts" validate constraint "security_posts_community_id_fkey";

alter table "public"."security_posts" add constraint "security_posts_department_tenant_fkey" FOREIGN KEY (department_id, community_id) REFERENCES public.departments(id, community_id) ON DELETE CASCADE not valid;

alter table "public"."security_posts" validate constraint "security_posts_department_tenant_fkey";

alter table "public"."security_shifts" add constraint "security_shifts_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."security_shifts" validate constraint "security_shifts_community_id_fkey";

alter table "public"."security_shifts" add constraint "security_shifts_created_by_membership_id_fkey" FOREIGN KEY (created_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."security_shifts" validate constraint "security_shifts_created_by_membership_id_fkey";

alter table "public"."security_shifts" add constraint "security_shifts_department_tenant_fkey" FOREIGN KEY (department_id, community_id) REFERENCES public.departments(id, community_id) ON DELETE CASCADE not valid;

alter table "public"."security_shifts" validate constraint "security_shifts_department_tenant_fkey";

alter table "public"."security_shifts" add constraint "security_shifts_post_id_fkey" FOREIGN KEY (post_id) REFERENCES public.security_posts(id) ON DELETE SET NULL not valid;

alter table "public"."security_shifts" validate constraint "security_shifts_post_id_fkey";

alter table "public"."security_shifts" add constraint "security_shifts_staff_assignment_id_fkey" FOREIGN KEY (staff_assignment_id) REFERENCES public.staff_assignments(id) ON DELETE CASCADE not valid;

alter table "public"."security_shifts" validate constraint "security_shifts_staff_assignment_id_fkey";

alter table "public"."service_applications" add constraint "service_applications_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."service_applications" validate constraint "service_applications_community_id_fkey";

alter table "public"."service_applications" add constraint "service_applications_created_by_membership_id_fkey" FOREIGN KEY (created_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."service_applications" validate constraint "service_applications_created_by_membership_id_fkey";

alter table "public"."service_applications" add constraint "service_applications_decided_by_membership_id_fkey" FOREIGN KEY (decided_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."service_applications" validate constraint "service_applications_decided_by_membership_id_fkey";

alter table "public"."service_applications" add constraint "service_applications_department_id_fkey" FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE CASCADE not valid;

alter table "public"."service_applications" validate constraint "service_applications_department_id_fkey";

alter table "public"."service_applications" add constraint "service_applications_department_tenant_fkey" FOREIGN KEY (department_id, community_id) REFERENCES public.departments(id, community_id) ON DELETE CASCADE not valid;

alter table "public"."service_applications" validate constraint "service_applications_department_tenant_fkey";

alter table "public"."service_applications" add constraint "service_applications_service_provider_id_fkey" FOREIGN KEY (service_provider_id) REFERENCES public.service_providers(id) ON DELETE CASCADE not valid;

alter table "public"."service_applications" validate constraint "service_applications_service_provider_id_fkey";

alter table "public"."service_provider_skills" add constraint "service_provider_skills_service_provider_id_fkey" FOREIGN KEY (service_provider_id) REFERENCES public.service_providers(id) ON DELETE CASCADE not valid;

alter table "public"."service_provider_skills" validate constraint "service_provider_skills_service_provider_id_fkey";

alter table "public"."service_provider_skills" add constraint "service_provider_skills_skill_id_fkey" FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE RESTRICT not valid;

alter table "public"."service_provider_skills" validate constraint "service_provider_skills_skill_id_fkey";

alter table "public"."service_providers" add constraint "service_providers_profile_id_fkey" FOREIGN KEY (profile_id) REFERENCES public.profiles(id) ON DELETE CASCADE not valid;

alter table "public"."service_providers" validate constraint "service_providers_profile_id_fkey";

alter table "public"."sse_events" add constraint "sse_events_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."sse_events" validate constraint "sse_events_community_id_fkey";

alter table "public"."sse_events" add constraint "sse_events_recipient_membership_id_fkey" FOREIGN KEY (recipient_membership_id) REFERENCES public.community_memberships(id) ON DELETE CASCADE not valid;

alter table "public"."sse_events" validate constraint "sse_events_recipient_membership_id_fkey";

alter table "public"."staff_assignments" add constraint "staff_assignments_department_id_fkey" FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE SET NULL not valid;

alter table "public"."staff_assignments" validate constraint "staff_assignments_department_id_fkey";

alter table "public"."staff_assignments" add constraint "staff_assignments_department_tenant_fkey" FOREIGN KEY (department_id, community_id) REFERENCES public.departments(id, community_id) ON DELETE CASCADE not valid;

alter table "public"."staff_assignments" validate constraint "staff_assignments_department_tenant_fkey";

alter table "public"."staff_assignments" add constraint "staff_assignments_membership_id_fkey" FOREIGN KEY (membership_id) REFERENCES public.community_memberships(id) ON DELETE CASCADE not valid;

alter table "public"."staff_assignments" validate constraint "staff_assignments_membership_id_fkey";

alter table "public"."staff_assignments" add constraint "staff_assignments_service_provider_id_fkey" FOREIGN KEY (service_provider_id) REFERENCES public.service_providers(id) ON DELETE SET NULL not valid;

alter table "public"."staff_assignments" validate constraint "staff_assignments_service_provider_id_fkey";

alter table "public"."staff_departures" add constraint "staff_departures_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."staff_departures" validate constraint "staff_departures_community_id_fkey";

alter table "public"."staff_departures" add constraint "staff_departures_decided_by_membership_id_fkey" FOREIGN KEY (decided_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."staff_departures" validate constraint "staff_departures_decided_by_membership_id_fkey";

alter table "public"."staff_departures" add constraint "staff_departures_department_tenant_fkey" FOREIGN KEY (department_id, community_id) REFERENCES public.departments(id, community_id) ON DELETE CASCADE not valid;

alter table "public"."staff_departures" validate constraint "staff_departures_department_tenant_fkey";

alter table "public"."staff_departures" add constraint "staff_departures_requested_by_membership_id_fkey" FOREIGN KEY (requested_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."staff_departures" validate constraint "staff_departures_requested_by_membership_id_fkey";

alter table "public"."staff_departures" add constraint "staff_departures_service_provider_id_fkey" FOREIGN KEY (service_provider_id) REFERENCES public.service_providers(id) ON DELETE SET NULL not valid;

alter table "public"."staff_departures" validate constraint "staff_departures_service_provider_id_fkey";

alter table "public"."staff_departures" add constraint "staff_departures_staff_assignment_id_fkey" FOREIGN KEY (staff_assignment_id) REFERENCES public.staff_assignments(id) ON DELETE CASCADE not valid;

alter table "public"."staff_departures" validate constraint "staff_departures_staff_assignment_id_fkey";

alter table "public"."staff_invitations" add constraint "staff_invitations_claimed_by_profile_id_fkey" FOREIGN KEY (claimed_by_profile_id) REFERENCES public.profiles(id) ON DELETE SET NULL not valid;

alter table "public"."staff_invitations" validate constraint "staff_invitations_claimed_by_profile_id_fkey";

alter table "public"."staff_invitations" add constraint "staff_invitations_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."staff_invitations" validate constraint "staff_invitations_community_id_fkey";

alter table "public"."staff_invitations" add constraint "staff_invitations_created_by_membership_id_fkey" FOREIGN KEY (created_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE RESTRICT not valid;

alter table "public"."staff_invitations" validate constraint "staff_invitations_created_by_membership_id_fkey";

alter table "public"."staff_invitations" add constraint "staff_invitations_department_id_fkey" FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE CASCADE not valid;

alter table "public"."staff_invitations" validate constraint "staff_invitations_department_id_fkey";

alter table "public"."unit_contacts" add constraint "unit_contacts_added_by_membership_id_fkey" FOREIGN KEY (added_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."unit_contacts" validate constraint "unit_contacts_added_by_membership_id_fkey";

alter table "public"."unit_contacts" add constraint "unit_contacts_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."unit_contacts" validate constraint "unit_contacts_community_id_fkey";

alter table "public"."unit_contacts" add constraint "unit_contacts_unit_id_fkey" FOREIGN KEY (unit_id) REFERENCES public.units(id) ON DELETE CASCADE not valid;

alter table "public"."unit_contacts" validate constraint "unit_contacts_unit_id_fkey";

alter table "public"."unit_residencies" add constraint "unit_residencies_membership_id_fkey" FOREIGN KEY (membership_id) REFERENCES public.community_memberships(id) ON DELETE CASCADE not valid;

alter table "public"."unit_residencies" validate constraint "unit_residencies_membership_id_fkey";

alter table "public"."unit_residencies" add constraint "unit_residencies_unit_id_fkey" FOREIGN KEY (unit_id) REFERENCES public.units(id) ON DELETE CASCADE not valid;

alter table "public"."unit_residencies" validate constraint "unit_residencies_unit_id_fkey";

alter table "public"."visitor_events" add constraint "visitor_events_visitor_request_id_fkey" FOREIGN KEY (visitor_request_id) REFERENCES public.visitor_requests(id) ON DELETE CASCADE not valid;

alter table "public"."visitor_events" validate constraint "visitor_events_visitor_request_id_fkey";

alter table "public"."visitor_requests" add constraint "visitor_requests_approved_by_membership_id_fkey" FOREIGN KEY (approved_by_membership_id) REFERENCES public.community_memberships(id) not valid;

alter table "public"."visitor_requests" validate constraint "visitor_requests_approved_by_membership_id_fkey";

alter table "public"."visitor_requests" add constraint "visitor_requests_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."visitor_requests" validate constraint "visitor_requests_community_id_fkey";

alter table "public"."visitor_requests" add constraint "visitor_requests_requested_by_membership_id_fkey" FOREIGN KEY (requested_by_membership_id) REFERENCES public.community_memberships(id) not valid;

alter table "public"."visitor_requests" validate constraint "visitor_requests_requested_by_membership_id_fkey";

alter table "public"."water_tanker_logs" add constraint "water_tanker_logs_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."water_tanker_logs" validate constraint "water_tanker_logs_community_id_fkey";

alter table "public"."water_tanker_logs" add constraint "water_tanker_logs_post_id_fkey" FOREIGN KEY (post_id) REFERENCES public.security_posts(id) ON DELETE SET NULL not valid;

alter table "public"."water_tanker_logs" validate constraint "water_tanker_logs_post_id_fkey";

alter table "public"."water_tanker_logs" add constraint "water_tanker_logs_recorded_by_membership_id_fkey" FOREIGN KEY (recorded_by_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."water_tanker_logs" validate constraint "water_tanker_logs_recorded_by_membership_id_fkey";

alter table "public"."work_order_assignments" add constraint "work_order_assignments_staff_assignment_id_fkey" FOREIGN KEY (staff_assignment_id) REFERENCES public.staff_assignments(id) ON DELETE RESTRICT not valid;

alter table "public"."work_order_assignments" validate constraint "work_order_assignments_staff_assignment_id_fkey";

alter table "public"."work_order_assignments" add constraint "work_order_assignments_work_order_id_fkey" FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id) ON DELETE CASCADE not valid;

alter table "public"."work_order_assignments" validate constraint "work_order_assignments_work_order_id_fkey";

alter table "public"."work_orders" add constraint "work_orders_community_id_fkey" FOREIGN KEY (community_id) REFERENCES public.communities(id) ON DELETE CASCADE not valid;

alter table "public"."work_orders" validate constraint "work_orders_community_id_fkey";

alter table "public"."work_orders" add constraint "work_orders_complaint_id_fkey" FOREIGN KEY (complaint_id) REFERENCES public.complaints(id) ON DELETE CASCADE not valid;

alter table "public"."work_orders" validate constraint "work_orders_complaint_id_fkey";

alter table "public"."work_orders" add constraint "work_orders_department_tenant_fkey" FOREIGN KEY (department_id, community_id) REFERENCES public.departments(id, community_id) ON DELETE CASCADE not valid;

alter table "public"."work_orders" validate constraint "work_orders_department_tenant_fkey";

alter table "public"."work_orders" add constraint "work_orders_skill_id_fkey" FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE SET NULL not valid;

alter table "public"."work_orders" validate constraint "work_orders_skill_id_fkey";

alter table "public"."work_orders" add constraint "work_orders_supervisor_membership_id_fkey" FOREIGN KEY (supervisor_membership_id) REFERENCES public.community_memberships(id) ON DELETE SET NULL not valid;

alter table "public"."work_orders" validate constraint "work_orders_supervisor_membership_id_fkey";

alter table "public"."worker_availability_rules" add constraint "worker_availability_rules_service_provider_id_fkey" FOREIGN KEY (service_provider_id) REFERENCES public.service_providers(id) ON DELETE CASCADE not valid;

alter table "public"."worker_availability_rules" validate constraint "worker_availability_rules_service_provider_id_fkey";

alter table "public"."worker_availability_rules" add constraint "worker_availability_rules_staff_assignment_id_fkey" FOREIGN KEY (staff_assignment_id) REFERENCES public.staff_assignments(id) ON DELETE CASCADE not valid;

alter table "public"."worker_availability_rules" validate constraint "worker_availability_rules_staff_assignment_id_fkey";

alter table "public"."worker_unavailability" add constraint "worker_unavailability_service_provider_id_fkey" FOREIGN KEY (service_provider_id) REFERENCES public.service_providers(id) ON DELETE CASCADE not valid;

alter table "public"."worker_unavailability" validate constraint "worker_unavailability_service_provider_id_fkey";

alter table "public"."worker_unavailability" add constraint "worker_unavailability_staff_assignment_id_fkey" FOREIGN KEY (staff_assignment_id) REFERENCES public.staff_assignments(id) ON DELETE CASCADE not valid;

alter table "public"."worker_unavailability" validate constraint "worker_unavailability_staff_assignment_id_fkey";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.approve_access_request(p_access_request_id uuid, p_profile_id uuid, p_default_invoice_amount numeric, p_due_at timestamp with time zone)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  request_row public.access_requests%rowtype;
  approver_membership_id uuid;
  new_membership_id uuid;
  invoice_id uuid;
begin
  select * into request_row
  from public.access_requests
  where id = p_access_request_id
  for update;

  if request_row.id is null or request_row.status <> 'pending' then
    raise exception 'Access request is not pending';
  end if;
  if request_row.requested_unit_id is null then
    raise exception 'Access request needs a unit before approval';
  end if;

  select cm.id into approver_membership_id
  from public.community_memberships cm
  where cm.community_id = request_row.community_id
    and cm.profile_id = auth.uid()
    and cm.role = 'admin'
    and cm.status = 'active'
    and cm.ended_at is null;
  if approver_membership_id is null then
    raise exception 'Only the community admin can approve an access request';
  end if;

  insert into public.community_memberships (
    community_id, profile_id, role, status, joined_at, is_default_community
  ) values (
    request_row.community_id, p_profile_id, 'resident', 'active', now(), true
  ) returning id into new_membership_id;

  insert into public.unit_residencies (
    unit_id, membership_id, relationship_type, is_primary_contact, started_at,
    created_by_membership_id
  ) values (
    request_row.requested_unit_id, new_membership_id,
    request_row.requested_relationship, false, current_date, approver_membership_id
  );

  insert into public.invoices (
    community_id, liable_unit_id, invoice_number, invoice_type, status,
    issued_at, due_at, subtotal, tax_amount, total_amount, created_by_membership_id
  ) values (
    request_row.community_id, request_row.requested_unit_id,
    'MNT-' || to_char(now(), 'YYYYMMDD') || '-' || replace(p_access_request_id::text, '-', ''),
    'maintenance', 'issued', now(), p_due_at,
    p_default_invoice_amount, 0, p_default_invoice_amount, approver_membership_id
  ) returning id into invoice_id;

  update public.access_requests
  set status = 'approved', reviewed_by_membership_id = approver_membership_id,
      reviewed_at = now(), created_profile_id = p_profile_id
  where id = request_row.id;

  return invoice_id;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.approve_access_request(p_request_id uuid, p_reviewer_profile_id uuid, p_unit_id uuid DEFAULT NULL::uuid, p_relationship public.residency_relationship DEFAULT NULL::public.residency_relationship)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  request_row public.access_requests%rowtype;
  reviewer_membership_id uuid;
  resident_membership_id uuid;
  target_unit_id uuid := p_unit_id;
begin
  select * into request_row
  from public.access_requests
  where id = p_request_id
  for update;
  if request_row.id is null then
    raise exception 'Access request not found';
  end if;

  select id into reviewer_membership_id
  from public.community_memberships
  where profile_id = p_reviewer_profile_id
    and community_id = request_row.community_id
    and role = 'admin'
    and status = 'active'
    and ended_at is null
  limit 1;
  if reviewer_membership_id is null then
    raise exception 'Active administrator membership required';
  end if;

  if request_row.status = 'approved' then
    select id into resident_membership_id
    from public.community_memberships
    where community_id = request_row.community_id
      and profile_id = request_row.applicant_profile_id
      and role = 'resident'
      and status = 'active'
      and ended_at is null
    limit 1;
    return jsonb_build_object(
      'request_id', request_row.id,
      'membership_id', resident_membership_id,
      'status', 'approved'
    );
  end if;
  if request_row.status <> 'pending' then
    raise exception 'Access request is no longer pending';
  end if;

  if target_unit_id is null then
    target_unit_id := request_row.requested_unit_id;
  end if;
  if target_unit_id is not null and not exists (
    select 1 from public.units
    where id = target_unit_id
      and community_id = request_row.community_id
      and status = 'active'
  ) then
    raise exception 'Selected unit does not belong to this community';
  end if;

  begin
    insert into public.community_memberships(
      community_id, profile_id, role, status, is_default_community
    ) values (
      request_row.community_id,
      request_row.applicant_profile_id,
      'resident',
      'active',
      not exists (
        select 1 from public.community_memberships
        where profile_id = request_row.applicant_profile_id
          and status = 'active'
          and ended_at is null
          and is_default_community
      )
    ) returning id into resident_membership_id;
  exception
    when unique_violation then
      resident_membership_id := null;
  end;

  if resident_membership_id is null then
    select id into resident_membership_id
    from public.community_memberships
    where community_id = request_row.community_id
      and profile_id = request_row.applicant_profile_id
      and role = 'resident'
      and status = 'active'
      and ended_at is null
    limit 1;
    if resident_membership_id is null then
      raise exception 'Applicant already has an incompatible membership';
    end if;
  end if;

  if target_unit_id is not null then
    begin
      insert into public.unit_residencies(
        unit_id, membership_id, relationship_type, created_by_membership_id
      ) values (
        target_unit_id,
        resident_membership_id,
        coalesce(p_relationship, request_row.requested_relationship),
        reviewer_membership_id
      );
    exception
      when unique_violation then null;
    end;
  end if;

  update public.access_requests
  set status = 'approved',
      reviewed_by_membership_id = reviewer_membership_id,
      reviewed_at = now(),
      rejection_reason = null,
      updated_at = now()
  where id = request_row.id;

  return jsonb_build_object(
    'request_id', request_row.id,
    'membership_id', resident_membership_id,
    'status', 'approved'
  );
end;
$function$
;

CREATE OR REPLACE FUNCTION public.claim_resident_invite(p_invite_id uuid, p_profile_id uuid)
 RETURNS TABLE(membership_id uuid, community_id uuid, unit_id uuid)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  invite public.resident_invites%rowtype;
  created_membership_id uuid;
begin
  select * into invite
  from public.resident_invites
  where id = p_invite_id
  for update;

  if invite.id is null or invite.status <> 'issued' then
    raise exception 'Invite is not redeemable';
  end if;
  if invite.expires_at <= now() then
    update public.resident_invites set status = 'expired' where id = invite.id;
    raise exception 'Invite has expired';
  end if;
  if invite.intended_role <> 'resident' or invite.intended_unit_id is null then
    raise exception 'Invite is not a complete resident invite';
  end if;

  insert into public.community_memberships (
    community_id, profile_id, role, status, joined_at, is_default_community
  ) values (
    invite.community_id, p_profile_id, 'resident', 'active', now(), true
  ) returning id into created_membership_id;

  insert into public.unit_residencies (
    unit_id, membership_id, relationship_type, is_primary_contact, started_at
  ) values (
    invite.intended_unit_id, created_membership_id, 'tenant', false, current_date
  );

  update public.resident_invites
  set status = 'redeemed', redeemed_at = now(), redeemed_by_profile_id = p_profile_id
  where id = invite.id;

  return query select created_membership_id, invite.community_id, invite.intended_unit_id;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.current_user_can_access_booking(p_booking_occurrence_id uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select exists (
    select 1
    from public.amenity_booking_occurrences occurrence
    join public.amenity_booking_series series on series.id = occurrence.booking_series_id
    where occurrence.id = p_booking_occurrence_id
      and (
        public.current_user_owns_membership(series.booked_by_membership_id, series.community_id)
        or public.current_user_has_community_role(series.community_id, array['manager', 'admin']::public.membership_role[])
      )
  );
$function$
;

CREATE OR REPLACE FUNCTION public.current_user_can_access_complaint(p_complaint_id uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select exists (
    select 1
    from public.complaints c
    where c.id = p_complaint_id
      and (
        public.current_user_owns_membership(c.raised_by_membership_id, c.community_id)
        or public.current_user_has_community_role(c.community_id, array['manager', 'admin']::public.membership_role[])
        or exists (
          select 1
          from public.work_orders wo
          join public.work_order_assignments wa on wa.work_order_id = wo.id
          join public.staff_assignments sa on sa.id = wa.staff_assignment_id
          join public.community_memberships cm on cm.id = sa.membership_id
          where wo.complaint_id = c.id
            and wa.unassigned_at is null
            and cm.profile_id = auth.uid()
            and cm.status = 'active'
            and cm.ended_at is null
        )
      )
  );
$function$
;

CREATE OR REPLACE FUNCTION public.current_user_can_access_invoice(p_invoice_id uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select exists (
    select 1
    from public.invoices i
    where i.id = p_invoice_id
      and (
        public.current_user_is_active_unit_resident(i.liable_unit_id)
        or public.current_user_has_community_role(i.community_id, array['admin']::public.membership_role[])
      )
  );
$function$
;

CREATE OR REPLACE FUNCTION public.current_user_can_access_visitor(p_visitor_request_id uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select exists (
    select 1
    from public.visitor_access_requests var
    where var.id = p_visitor_request_id
      and (
        public.current_user_owns_membership(var.requested_by_membership_id, var.community_id)
        or public.current_user_is_active_unit_resident(var.unit_id)
        or public.current_user_has_community_role(var.community_id, array['security', 'manager', 'admin']::public.membership_role[])
      )
  );
$function$
;

CREATE OR REPLACE FUNCTION public.current_user_can_access_work_order(p_work_order_id uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select exists (
    select 1
    from public.work_orders wo
    join public.complaints c on c.id = wo.complaint_id
    where wo.id = p_work_order_id
      and (
        public.current_user_owns_membership(c.raised_by_membership_id, c.community_id)
        or public.current_user_has_community_role(c.community_id, array['manager', 'admin']::public.membership_role[])
        or exists (
          select 1
          from public.work_order_assignments wa
          join public.staff_assignments sa on sa.id = wa.staff_assignment_id
          join public.community_memberships cm on cm.id = sa.membership_id
          where wa.work_order_id = wo.id
            and wa.unassigned_at is null
            and cm.profile_id = auth.uid()
            and cm.status = 'active'
            and cm.ended_at is null
        )
      )
  );
$function$
;

CREATE OR REPLACE FUNCTION public.current_user_has_community_role(p_community_id uuid, p_roles public.membership_role[])
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select exists (
    select 1
    from public.community_memberships cm
    where cm.community_id = p_community_id
      and cm.profile_id = auth.uid()
      and cm.status = 'active'
      and cm.ended_at is null
      and cm.role = any (p_roles)
  );
$function$
;

CREATE OR REPLACE FUNCTION public.current_user_is_active_member(p_community_id uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select exists (
    select 1
    from public.community_memberships cm
    where cm.community_id = p_community_id
      and cm.profile_id = auth.uid()
      and cm.status = 'active'
      and cm.ended_at is null
  );
$function$
;

CREATE OR REPLACE FUNCTION public.current_user_is_active_unit_resident(p_unit_id uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select exists (
    select 1
    from public.unit_residencies ur
    join public.community_memberships cm on cm.id = ur.membership_id
    where ur.unit_id = p_unit_id
      and ur.ended_at is null
      and cm.profile_id = auth.uid()
      and cm.status = 'active'
      and cm.ended_at is null
  );
$function$
;

CREATE OR REPLACE FUNCTION public.current_user_owns_membership(p_membership_id uuid, p_community_id uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select exists (
    select 1
    from public.community_memberships cm
    where cm.id = p_membership_id
      and cm.community_id = p_community_id
      and cm.profile_id = auth.uid()
      and cm.status = 'active'
      and cm.ended_at is null
  );
$function$
;

CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  claims jsonb;
  effective_role text;
begin
  select upper(cm.role::text)
  into effective_role
  from public.community_memberships cm
  where cm.profile_id = (event ->> 'user_id')::uuid
    and cm.status = 'active'
    and cm.ended_at is null
  order by case cm.role
    when 'admin' then 1
    when 'manager' then 2
    when 'security' then 3
    when 'worker' then 4
    else 5
  end
  limit 1;

  claims := event -> 'claims';
  claims := jsonb_set(
    claims,
    '{user_role}',
    to_jsonb(coalesce(effective_role, 'RESIDENT'))
  );
  return jsonb_set(event, '{claims}', claims);
end;
$function$
;

CREATE OR REPLACE FUNCTION public.handle_new_user()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  insert into public.profiles (id, full_name, phone_e164, display_email)
  values (
    new.id,
    new.raw_user_meta_data ->> 'full_name',
    new.phone,
    new.email
  )
  on conflict (id) do update
    set full_name = coalesce(excluded.full_name, public.profiles.full_name),
        phone_e164 = coalesce(excluded.phone_e164, public.profiles.phone_e164),
        display_email = coalesce(excluded.display_email, public.profiles.display_email),
        updated_at = now();
  return new;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.is_admin()
 RETURNS boolean
 LANGUAGE sql
 STABLE
AS $function$
  select public.jwt_role() = 'admin';
$function$
;

CREATE OR REPLACE FUNCTION public.jwt_role()
 RETURNS text
 LANGUAGE sql
 STABLE
AS $function$
  select lower(coalesce(
    nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'user_role',
    ''
  ));
$function$
;

CREATE OR REPLACE FUNCTION public.rls_auto_enable()
 RETURNS event_trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog'
AS $function$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN
    SELECT *
    FROM pg_event_trigger_ddl_commands()
    WHERE command_tag IN ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
      AND object_type IN ('table','partitioned table')
  LOOP
     IF cmd.schema_name IS NOT NULL AND cmd.schema_name IN ('public') AND cmd.schema_name NOT IN ('pg_catalog','information_schema') AND cmd.schema_name NOT LIKE 'pg_toast%' AND cmd.schema_name NOT LIKE 'pg_temp%' THEN
      BEGIN
        EXECUTE format('alter table if exists %s enable row level security', cmd.object_identity);
        RAISE LOG 'rls_auto_enable: enabled RLS on %', cmd.object_identity;
      EXCEPTION
        WHEN OTHERS THEN
          RAISE LOG 'rls_auto_enable: failed to enable RLS on %', cmd.object_identity;
      END;
     ELSE
        RAISE LOG 'rls_auto_enable: skip % (either system schema or not in enforced list: %.)', cmd.object_identity, cmd.schema_name;
     END IF;
  END LOOP;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.transfer_community_admin(p_community_id uuid, p_successor_membership_id uuid, p_transfer_note text DEFAULT NULL::text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  caller_membership_id uuid;
  previous_term public.community_admin_terms%rowtype;
  successor_previous_role public.membership_role;
begin
  select cm.id into caller_membership_id
  from public.community_memberships cm
  where cm.community_id = p_community_id
    and cm.profile_id = auth.uid()
    and cm.role = 'admin'
    and cm.status = 'active'
    and cm.ended_at is null;

  if caller_membership_id is null then
    raise exception 'Only the active community admin can transfer administration';
  end if;

  select * into previous_term
  from public.community_admin_terms
  where community_id = p_community_id and ended_at is null
  for update;

  if previous_term.id is null then
    raise exception 'Community has no active admin term';
  end if;

  select role into successor_previous_role
  from public.community_memberships
  where id = p_successor_membership_id
    and community_id = p_community_id
    and status = 'active'
    and ended_at is null
  for update;

  if successor_previous_role is null then
    raise exception 'Successor must be an active membership in the same community';
  end if;
  if p_successor_membership_id = caller_membership_id then
    raise exception 'Successor must be a different membership';
  end if;

  update public.community_admin_terms
  set ended_at = now(),
      transferred_by_membership_id = caller_membership_id,
      transfer_note = p_transfer_note
  where id = previous_term.id;

  update public.community_memberships
  set role = previous_term.role_before_term,
      updated_at = now()
  where id = caller_membership_id;

  update public.community_memberships
  set role = 'admin', updated_at = now()
  where id = p_successor_membership_id;

  insert into public.community_admin_terms (
    community_id, admin_membership_id, role_before_term, started_at,
    transferred_by_membership_id, transfer_note
  ) values (
    p_community_id, p_successor_membership_id, successor_previous_role, now(),
    caller_membership_id, p_transfer_note
  );
end;
$function$
;

CREATE OR REPLACE FUNCTION public.validate_community_admin_term()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
begin
  if not exists (
    select 1
    from public.community_memberships cm
    where cm.id = new.admin_membership_id
      and cm.community_id = new.community_id
      and cm.role = 'admin'
      and cm.status = 'active'
      and cm.ended_at is null
  ) then
    raise exception 'An active admin term must reference an active admin membership in the same community';
  end if;
  return new;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.accept_work_order_offer(p_work_order_id uuid)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_order      public.work_orders%rowtype;
  v_assign     public.work_order_assignments%rowtype;
  v_staff      public.staff_assignments%rowtype;
  v_complaint  public.complaints%rowtype;
  v_actor      uuid;
begin
  -- The whole race is settled on this line. See the header.
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  select * into v_assign
    from public.work_order_assignments a
   where a.work_order_id = p_work_order_id
     and public.is_own_staff_assignment(a.staff_assignment_id)
   order by a.offered_at desc
   limit 1;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  -- Idempotent on the caller's own second tap: they already hold it, so this is
  -- the answer they were asking for rather than a conflict to explain.
  if v_assign.status = 'accepted' then
    return v_assign.id;
  end if;

  if v_assign.status <> 'offered' then
    raise exception 'That offer is no longer open.' using errcode = 'HB409';
  end if;

  if v_order.status <> 'offered' then
    raise exception 'Somebody has already taken this job.' using errcode = 'HB409';
  end if;

  if v_order.scheduled_start_at is null or v_order.scheduled_end_at is null then
    raise exception 'This job has no scheduled time yet.' using errcode = 'HB409';
  end if;

  select * into v_staff
    from public.staff_assignments where id = v_assign.staff_assignment_id;

  -- The sweep checked this when it made the offer; between then and now the
  -- caller may have been booked elsewhere by a supervisor. Named here so the
  -- worker is told which of their own jobs is in the way, rather than reading a
  -- 23P01 about an exclusion constraint.
  if exists (
    select 1
      from public.work_order_assignments busy
     where busy.staff_assignment_id = v_assign.staff_assignment_id
       and busy.status = 'accepted'
       and busy.work_order_id <> v_order.id
       and busy.scheduled_start_at is not null
       and tstzrange(busy.scheduled_start_at, busy.scheduled_end_at, '[)')
           && tstzrange(v_order.scheduled_start_at, v_order.scheduled_end_at, '[)')
  ) then
    raise exception 'You are already booked during that time.'
      using errcode = 'HB409';
  end if;

  -- Everybody else's offer is withdrawn, not deleted -- `0036` §6 and `0037` §5
  -- both made this call, and the history of who was asked is the answer to the
  -- question a supervisor asks when a job goes wrong.
  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now(), ended_at = now()
   where work_order_id = v_order.id
     and id <> v_assign.id
     and status in ('offered', 'accepted');

  update public.work_order_assignments
     set status             = 'accepted',
         responded_at       = now(),
         scheduled_start_at = coalesce(scheduled_start_at, v_order.scheduled_start_at),
         scheduled_end_at   = coalesce(scheduled_end_at, v_order.scheduled_end_at)
   where id = v_assign.id;

  -- Which retires the pending `auto_assign` through `0037`'s trigger, and is the
  -- whole of why "somebody already took it" needs no second mechanism.
  update public.work_orders
     set status = 'scheduled', updated_at = now()
   where id = v_order.id;

  v_actor := public.my_membership_in(v_order.community_id);
  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  -- `job_assigned` rather than a new `job_accepted`: from the resident's side
  -- the fact is the same fact -- somebody is now coming, and their name is this.
  -- A second event type would render as a second sentence saying it again.
  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_actor, 'job_assigned',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assignmentId', v_assign.id,
      'assigneeName', v_staff.display_name,
      'startsAt', v_order.scheduled_start_at,
      'endsAt', v_order.scheduled_end_at,
      'accepted', true)
  );

  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.assigned',
      jsonb_build_object(
        'title', 'Someone is coming for your complaint',
        'body', v_staff.display_name,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_order.scheduled_start_at));
  end if;

  -- The supervisor asked a question and this is the answer to it. Skipped when
  -- the supervisor is the accepting worker, which a small department makes
  -- entirely possible.
  if v_order.supervisor_membership_id is not null
     and v_order.supervisor_membership_id is distinct from v_actor then
    perform public.notify_member(
      v_order.supervisor_membership_id, 'work_order.accepted',
      jsonb_build_object(
        'title', 'A job was accepted',
        'body', v_staff.display_name,
        -- CHANGED: the triage screen, filtered to this job.
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_order.scheduled_start_at));
  end if;

  return v_assign.id;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.add_complaint_comment(p_complaint_id uuid, p_body text, p_visibility text, p_author_membership uuid, p_author_label text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_community_id uuid;
  v_raised_by    uuid;
  v_title        text;
  v_visibility   text := coalesce(nullif(btrim(coalesce(p_visibility, '')), ''), 'public');
  v_id           uuid;
begin
  select c.community_id, c.raised_by_membership_id, c.title
    into v_community_id, v_raised_by, v_title
    from public.complaints c where c.id = p_complaint_id;

  if v_community_id is null then
    raise exception 'Complaint not found.' using errcode = 'P0002';
  end if;

  if not public.is_community_member(v_community_id) then
    raise exception 'Only a member of this community may comment.'
      using errcode = '42501';
  end if;

  if v_visibility = 'internal' and not public.is_community_admin(v_community_id) then
    raise exception 'Only an admin may leave an internal comment.'
      using errcode = '42501';
  end if;

  if nullif(btrim(coalesce(p_body, '')), '') is null then
    raise exception 'A comment cannot be empty.' using errcode = '23514';
  end if;

  insert into public.complaint_comments
    (complaint_id, author_membership_id, author_label, body, visibility)
  values
    (p_complaint_id, p_author_membership, p_author_label, btrim(p_body), v_visibility)
  returning id into v_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, actor_label, event_type, payload)
  values (
    p_complaint_id, p_author_membership, p_author_label, 'comment_added',
    jsonb_build_object('comment_id', v_id, 'visibility', v_visibility)
  );

  update public.complaints
     set aggregate_version = aggregate_version + 1,
         updated_at        = now()
   where id = p_complaint_id;

  -- >>> 0031: tell the other party a comment landed.
  --
  -- An **internal** comment notifies nobody. The whole point of the flag is
  -- that the resident does not see it, and a notification saying "new comment
  -- on your complaint" that leads to a thread where nothing new is visible is a
  -- worse leak than showing the comment would have been -- it tells the
  -- resident something was said about them and refuses to say what.
  --
  -- The comment body is not copied into the payload. `notifications_service`
  -- renders exactly `title`, `body` and `url`, and `body` here is the complaint
  -- title -- the thing the resident already knows -- so a push on a locked
  -- screen never carries someone else's words about them.
  if v_visibility = 'public' then
    if v_raised_by is distinct from p_author_membership then
      perform public.notify_member(
        v_raised_by,
        'complaint.commented',
        jsonb_build_object(
          'title', 'New comment on your complaint',
          'body',  v_title,
          'url',   '/resident/complaints?complaint=' || p_complaint_id::text,
          'complaint_id', p_complaint_id
        )
      );
    else
      -- The resident commented. Staff hear about it instead, otherwise a
      -- resident chasing their own complaint is talking into an empty room.
      -- CHANGED: was `notify_community_staff(v_community_id, …)`.
      perform public.notify_complaint_staff(
        p_complaint_id,
        'complaint.commented',
        jsonb_build_object(
          'title', 'New comment on a complaint',
          'body',  v_title,
          'url',   '/admin/complaints?complaint=' || p_complaint_id::text,
          'complaint_id', p_complaint_id
        ),
        p_author_membership
      );
    end if;
  end if;
  -- <<< 0031

  return v_id;
end $function$
;

CREATE OR REPLACE FUNCTION public.add_department_skill(p_department_id uuid, p_name text)
 RETURNS TABLE(id uuid, name text, category text, description text, created boolean)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_skill record;
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  -- create_skill raises HB403/HB422 itself, and returns exactly one row.
  select c.id, c.name, c.category, c.description, c.created
    into v_skill
    from public.create_skill(p_name) c;

  insert into public.department_skills (department_id, skill_id)
  values (p_department_id, v_skill.id)
  on conflict do nothing;

  return query select v_skill.id, v_skill.name, v_skill.category,
                      v_skill.description, v_skill.created;
end;
$function$
;

create or replace view "public"."amenity_booking_overview" as  SELECT bk.id,
    bk.community_id,
    COALESCE(bk.booking_group_id, bk.id) AS booking_series_id,
    bk.amenity_id,
    am.name AS amenity_name,
    am.booking_mode,
    ((bk.starts_at AT TIME ZONE COALESCE(cs.timezone, c.timezone, 'Asia/Kolkata'::text)))::date AS booking_date,
    bk.starts_at,
    bk.ends_at,
    bk.is_exclusive,
    bk.buffer_minutes,
    bk.occupant_count,
        CASE bk.status
            WHEN 'requested'::public.booking_status THEN 'Pending'::text
            WHEN 'approved'::public.booking_status THEN 'Approved'::text
            WHEN 'rejected'::public.booking_status THEN 'Rejected'::text
            WHEN 'cancelled'::public.booking_status THEN 'Cancelled'::text
            WHEN 'completed'::public.booking_status THEN 'Completed'::text
            WHEN 'no_show'::public.booking_status THEN 'No Show'::text
            ELSE initcap((bk.status)::text)
        END AS status,
    (bk.status)::text AS stored_status,
    bk.cancelled_at,
    bk.cancellation_reason_code,
    bk.cancellation_reason,
    bk.cancelled_by_resident,
    bk.force_cancelled,
    bk.aggregate_version AS version,
    bk.created_at,
    bk.updated_at,
    bk.title,
    bk.booking_type,
    bk.source,
    bk.is_private,
    am.approval_required AS requires_approval,
    bk.guest_count,
    bk.notes,
    bk.charge_override,
    bk.department,
    grp.series_status,
    grp.day_count,
    bk.requested_at,
    bk.approved_at,
    bk.rejected_at,
    bk.rejection_reason,
    bk.rejection_reason_code,
    bk.unit_id,
    u.unit_code,
    bldg.name AS tower,
    bk.booked_by_membership_id AS requested_by_membership_id,
    m.profile_id AS resident_profile_id,
    pr.full_name AS resident_name,
    lower(concat_ws(' '::text, am.name, bk.title, u.unit_code, pr.full_name)) AS search_text
   FROM ((((((((public.amenity_bookings bk
     JOIN public.amenities am ON ((am.id = bk.amenity_id)))
     JOIN public.communities c ON ((c.id = bk.community_id)))
     LEFT JOIN public.community_settings cs ON ((cs.community_id = bk.community_id)))
     LEFT JOIN public.units u ON ((u.id = bk.unit_id)))
     LEFT JOIN public.buildings bldg ON ((bldg.id = u.building_id)))
     LEFT JOIN public.community_memberships m ON ((m.id = bk.booked_by_membership_id)))
     LEFT JOIN public.profiles pr ON ((pr.id = m.profile_id)))
     LEFT JOIN LATERAL ( SELECT
                CASE
                    WHEN (count(*) FILTER (WHERE (g.status = 'requested'::public.booking_status)) > 0) THEN 'pending'::text
                    WHEN (count(*) FILTER (WHERE (g.status = 'approved'::public.booking_status)) > 0) THEN 'approved'::text
                    WHEN (count(*) FILTER (WHERE (g.status = 'rejected'::public.booking_status)) > 0) THEN 'rejected'::text
                    ELSE 'cancelled'::text
                END AS series_status,
            count(*) AS day_count
           FROM public.amenity_bookings g
          WHERE (COALESCE(g.booking_group_id, g.id) = COALESCE(bk.booking_group_id, bk.id))) grp ON (true));


create or replace view "public"."amenity_ledger_overview" as  SELECT bk.id,
    bk.community_id,
    bk.id AS booking_id,
    COALESCE(bk.booking_group_id, bk.id) AS booking_series_id,
    bk.amenity_id,
    am.name AS amenity_name,
    bk.unit_id,
    u.unit_code,
    m.profile_id AS resident_profile_id,
    pr.full_name AS resident_name,
    bk.booked_by_membership_id AS requested_by_membership_id,
    ((bk.starts_at AT TIME ZONE COALESCE(c.timezone, 'Asia/Kolkata'::text)))::date AS booking_date,
    bk.starts_at,
    bk.ends_at,
    bk.booking_type,
    bk.title,
    bk.notes,
    (bk.status)::text AS booking_status,
    bk.force_cancelled,
    bk.cancelled_at,
    bk.cancellation_reason,
    bk.approved_at,
    bk.created_at,
    bk.updated_at,
    ev.payment_reference,
    COALESCE(ch.deposit_amount, (0)::numeric) AS deposit_amount,
    ((COALESCE(ev.amount_paid, (0)::numeric) >= COALESCE(ch.deposit_amount, (0)::numeric)) AND (COALESCE(ch.deposit_amount, (0)::numeric) > (0)::numeric)) AS deposit_paid,
    COALESCE(ch.booking_charges, (0)::numeric) AS booking_charges,
    COALESCE(ch.additional_charges, (0)::numeric) AS additional_charges,
    COALESCE(ev.amount_paid, (0)::numeric) AS amount_paid,
    COALESCE(ev.refund_amount, (0)::numeric) AS refund_amount,
    COALESCE(ev.damage_amount, (0)::numeric) AS damage_amount,
    COALESCE(ch.total_amount, (0)::numeric) AS total_amount,
    GREATEST((COALESCE(ch.deposit_amount, (0)::numeric) - COALESCE(ev.amount_paid, (0)::numeric)), (0)::numeric) AS outstanding_deposit,
    GREATEST((((COALESCE(ev.amount_paid, (0)::numeric) - COALESCE(ev.refund_amount, (0)::numeric)) - COALESCE(ev.damage_amount, (0)::numeric)) - COALESCE(ch.non_refundable, (0)::numeric)), (0)::numeric) AS remaining_refund,
        CASE
            WHEN (COALESCE(ch.total_amount, (0)::numeric) = (0)::numeric) THEN 'not_applicable'::text
            WHEN (COALESCE(ev.amount_paid, (0)::numeric) >= COALESCE(ch.total_amount, (0)::numeric)) THEN 'paid'::text
            WHEN (COALESCE(ev.amount_paid, (0)::numeric) > (0)::numeric) THEN 'partial'::text
            ELSE 'unpaid'::text
        END AS payment_status
   FROM (((((((public.amenity_bookings bk
     JOIN public.amenities am ON ((am.id = bk.amenity_id)))
     JOIN public.communities c ON ((c.id = bk.community_id)))
     LEFT JOIN public.units u ON ((u.id = bk.unit_id)))
     LEFT JOIN public.community_memberships m ON ((m.id = bk.booked_by_membership_id)))
     LEFT JOIN public.profiles pr ON ((pr.id = m.profile_id)))
     LEFT JOIN LATERAL ( SELECT sum(x.amount) AS total_amount,
            sum(x.amount) FILTER (WHERE (x.charge_type = ANY (ARRAY['deposit'::text, 'damage_deposit'::text]))) AS deposit_amount,
            sum(x.amount) FILTER (WHERE (x.charge_type = 'booking_fee'::text)) AS booking_charges,
            sum(x.amount) FILTER (WHERE (x.charge_type = 'additional'::text)) AS additional_charges,
            sum(x.amount) FILTER (WHERE (x.charge_type = ANY (ARRAY['booking_fee'::text, 'late_cancellation'::text, 'additional'::text]))) AS non_refundable
           FROM public.amenity_booking_charges x
          WHERE (x.booking_occurrence_id = bk.id)) ch ON (true))
     LEFT JOIN LATERAL ( SELECT sum(e.amount) FILTER (WHERE (e.event_type = 'payment'::text)) AS amount_paid,
            sum(e.amount) FILTER (WHERE (e.event_type = 'refund'::text)) AS refund_amount,
            sum(e.amount) FILTER (WHERE (e.event_type = 'damage_deduction'::text)) AS damage_amount,
            (array_agg(e.payment_reference ORDER BY e.created_at DESC) FILTER (WHERE ((e.event_type = 'payment'::text) AND (e.payment_reference IS NOT NULL))))[1] AS payment_reference
           FROM (public.amenity_financial_events e
             JOIN public.amenity_booking_charges xc ON ((xc.id = e.booking_charge_id)))
          WHERE (xc.booking_occurrence_id = bk.id)) ev ON (true));


create or replace view "public"."amenity_ledger_summary" as  SELECT community_id,
    amenity_id,
    count(*) AS total_bookings,
    COALESCE(sum(amount_paid), (0)::numeric) AS total_revenue,
    COALESCE(sum(outstanding_deposit), (0)::numeric) AS pending_deposits,
    COALESCE(sum(remaining_refund), (0)::numeric) AS refund_pending,
    COALESCE(sum(refund_amount), (0)::numeric) AS refund_completed,
    COALESCE(sum(damage_amount), (0)::numeric) AS damage_deductions,
    COALESCE(sum(remaining_refund), (0)::numeric) AS outstanding_refunds,
    count(*) FILTER (WHERE (payment_status = 'paid'::text)) AS completed_transactions
   FROM public.amenity_ledger_overview l
  GROUP BY community_id, amenity_id;


create or replace view "public"."amenity_overview" as  SELECT a.id,
    a.community_id,
    a.name,
    a.description,
    a.category,
    a.location,
    a.image_url,
    a.capacity,
    a.booking_mode,
    a.approval_required,
    a.status,
    a.is_active,
    a.version,
    a.created_at,
    a.updated_at,
    a.opening_time,
    a.closing_time,
    a.slot_duration_minutes,
    a.cleaning_buffer_minutes,
    a.max_active_bookings_per_resident,
    a.allow_private_booking,
    a.allow_recurring_booking,
    a.allow_guest_booking,
    a.allow_same_day_booking,
    a.enable_waitlist,
    a.enable_auto_approval,
    a.booking_fee,
    a.security_deposit,
    a.late_cancellation_charge,
    a.damage_deposit,
    a.refund_policy,
    a.currency_code,
    a.closed_days,
    a.maintenance_days,
    a.holiday_overrides,
    a.temporary_closure,
    a.minimum_booking_duration_minutes,
    a.maximum_booking_duration_minutes,
    a.advance_booking_window_days,
    a.maintenance_interval,
    a.default_maintenance_duration_minutes,
    a.auto_block_maintenance_slots,
    a.maintenance_notes,
    COALESCE(b.upcoming_booking_count, (0)::bigint) AS upcoming_booking_count,
    COALESCE(b.pending_booking_count, (0)::bigint) AS pending_booking_count,
    COALESCE(b.pending_booking_count, (0)::bigint) AS pending_requests,
    COALESCE(d.outstanding_dues, (0)::numeric) AS outstanding_dues,
    lower(concat_ws(' '::text, a.name, a.description, a.category, a.location)) AS search_text
   FROM ((public.amenities a
     LEFT JOIN LATERAL ( SELECT count(*) FILTER (WHERE ((bk.starts_at >= now()) AND (bk.status = 'approved'::public.booking_status))) AS upcoming_booking_count,
            count(*) FILTER (WHERE (bk.status = 'requested'::public.booking_status)) AS pending_booking_count
           FROM public.amenity_bookings bk
          WHERE (bk.amenity_id = a.id)) b ON (true))
     LEFT JOIN LATERAL ( SELECT GREATEST((COALESCE(ch.raised, (0)::numeric) - COALESCE(pd.paid, (0)::numeric)), (0)::numeric) AS outstanding_dues
           FROM (( SELECT sum(x.amount) AS raised
                   FROM (public.amenity_booking_charges x
                     JOIN public.amenity_bookings bx ON ((bx.id = x.booking_occurrence_id)))
                  WHERE (bx.amenity_id = a.id)) ch
             CROSS JOIN ( SELECT sum(e.amount) AS paid
                   FROM ((public.amenity_financial_events e
                     JOIN public.amenity_booking_charges xc ON ((xc.id = e.booking_charge_id)))
                     JOIN public.amenity_bookings bx ON ((bx.id = xc.booking_occurrence_id)))
                  WHERE ((bx.amenity_id = a.id) AND (e.event_type = 'payment'::text))) pd)) d ON (true));


CREATE OR REPLACE FUNCTION public.assign_complaint_department(p_membership_id uuid, p_complaint_id uuid, p_department_id uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_complaint record;
  v_target    record;
  v_payload   jsonb;
  v_manager   record;
begin
  select c.id, c.community_id, c.department_id, c.title
    into v_complaint
    from public.complaints c
   where c.id = p_complaint_id;

  if v_complaint.id is null then
    raise exception 'No such complaint.' using errcode = 'HB404';
  end if;

  if not public.is_own_membership(p_membership_id) then
    raise exception 'That is not your membership.' using errcode = 'HB403';
  end if;

  if v_complaint.department_id is null then
    if not public.is_community_admin(v_complaint.community_id) then
      raise exception 'Only an administrator may allot an unrouted complaint.'
        using errcode = 'HB403';
    end if;
  elsif not public.can_manage_department(v_complaint.department_id) then
    raise exception 'You do not manage the department holding this complaint.'
      using errcode = 'HB403';
  end if;

  select d.id, d.name, d.community_id
    into v_target
    from public.departments d
   where d.id = p_department_id
     and d.community_id = v_complaint.community_id;

  if v_target.id is null then
    raise exception 'No such department in this community.' using errcode = 'HB404';
  end if;

  if v_target.id = v_complaint.department_id then
    return;   -- already there; a no-op is kinder than a 409 on a double click
  end if;

  update public.complaints
     set department_id = v_target.id,
         updated_at    = now()
   where id = p_complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    p_complaint_id, p_membership_id, 'department_assigned',
    jsonb_build_object(
      'from_department_id', v_complaint.department_id,
      'to_department_id',   v_target.id,
      'to_department_name', v_target.name
    )
  );

  v_payload := jsonb_build_object(
    'title', 'A complaint was assigned to your department',
    'body',  v_complaint.title,
    'url',   '/admin/complaints?complaint=' || p_complaint_id::text,
    'complaint_id', p_complaint_id
  );

  for v_manager in
    select m.id
      from public.community_memberships m
     where m.community_id  = v_complaint.community_id
       and m.department_id = v_target.id
       and m.role::text    = 'manager'
       and m.status        = 'active'
       and m.ended_at is null
       and m.id <> p_membership_id
  loop
    perform public.notify_member(v_manager.id, 'complaint.assigned', v_payload);
  end loop;
end;
$function$
;

create or replace view "public"."bookable_amenity" as  SELECT id,
    community_id,
    name,
    description,
    category,
    location,
    image_url,
    capacity,
    booking_mode,
    approval_required,
    opening_time,
    closing_time,
    slot_duration_minutes,
    minimum_booking_duration_minutes,
    maximum_booking_duration_minutes,
    advance_booking_window_days,
    max_active_bookings_per_resident,
    closed_days,
    allow_private_booking,
    allow_guest_booking,
    allow_recurring_booking,
    allow_same_day_booking,
    booking_fee,
    security_deposit,
    currency_code,
    refund_policy,
    temporary_closure
   FROM public.amenities a
  WHERE ((status = 'active'::text) AND is_active AND ((temporary_closure IS NULL) OR (temporary_closure = ANY (ARRAY['null'::jsonb, '{}'::jsonb, '[]'::jsonb, '""'::jsonb, '0'::jsonb, 'false'::jsonb]))));


CREATE OR REPLACE FUNCTION public.can_author_skills()
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select exists (
    select 1
      from public.community_memberships m
     where m.profile_id = auth.uid()
       and m.status = 'active'
       and m.ended_at is null
       and m.role in ('admin', 'manager')
  );
$function$
;

CREATE OR REPLACE FUNCTION public.claim_staff_invitations(p_profile_id uuid, p_email text)
 RETURNS TABLE(membership_id uuid, community_id uuid, department_id uuid, role text, rank text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_email citext := lower(btrim(coalesce(p_email, '')))::citext;
  v_row   record;
  v_kind  text;
  v_role  text;
  v_membership uuid;
begin
  if p_profile_id is null or v_email = '' then
    return;
  end if;

  for v_row in
    select s.*
      from public.staff_invitations s
     where s.invitee_email = v_email
       and s.status = 'pending'
     order by s.created_at
  loop
    select d.kind into v_kind
      from public.departments d
     where d.id = v_row.department_id;

    -- Already a member of that community: leave the invitation pending rather
    -- than claiming it into a membership that cannot be created. An admin
    -- looking at the department sees it still outstanding, which is true.
    if exists (
      select 1 from public.community_memberships m
       where m.community_id = v_row.community_id
         and m.profile_id = p_profile_id
         and m.status = 'active'
         and m.ended_at is null
    ) then
      continue;
    end if;

    -- Derived, never stored -- see the header's table. A manager runs a
    -- department whatever its kind; a supervisor is a senior member of the
    -- workforce, so they take the workforce role and _portal_for reads their
    -- rank to decide where they land.
    if v_row.rank = 'manager' then
      v_role := 'manager';
    elsif v_kind = 'security' then
      v_role := 'security';
    else
      v_role := 'worker';
    end if;

    insert into public.community_memberships (
      community_id, profile_id, department_id, role, status, joined_at
    )
    values (
      v_row.community_id, p_profile_id, v_row.department_id,
      v_role::public.membership_role, 'active', now()
    )
    returning id into v_membership;

    insert into public.staff_assignments (
      community_id, department_id, membership_id, display_name, phone_e164,
      job_title, rank, status, employment_type, started_at
    )
    values (
      v_row.community_id, v_row.department_id, v_membership,
      v_row.invitee_name, v_row.invitee_phone_e164, v_row.job_title,
      v_row.rank, 'active', 'staff', current_date
    );

    update public.staff_invitations
       set status = 'claimed',
           claimed_by_profile_id = p_profile_id,
           claimed_at = now(),
           updated_at = now()
     where id = v_row.id;

    membership_id := v_membership;
    community_id  := v_row.community_id;
    department_id := v_row.department_id;
    role          := v_role;
    rank          := v_row.rank;
    return next;
  end loop;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.community_categories(p_membership_id uuid)
 RETURNS TABLE(id uuid, name text, skill_id uuid, skill_name text, department_count integer)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_community uuid;
begin
  select m.community_id into v_community
    from public.community_memberships m
   where m.id = p_membership_id
     and m.profile_id = auth.uid()
     and m.status = 'active'
     and m.ended_at is null
   limit 1;

  if v_community is null then
    raise exception 'You are not a member of this community.'
      using errcode = 'HB403';
  end if;

  return query
    select
      cc.id,
      cc.name,
      cc.skill_id,
      s.name,
      (select count(*)::integer
         from public.department_categories dc
        where dc.category_id = cc.id) as department_count
      from public.complaint_categories cc
      left join public.skills s on s.id = cc.skill_id and s.is_active
     where cc.community_id = v_community
     order by lower(cc.name);
end;
$function$
;

CREATE OR REPLACE FUNCTION public.community_departments(p_community_id uuid)
 RETURNS TABLE(id uuid, name text, kind text)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  if not exists (
    select 1
      from public.community_memberships m
     where m.community_id = p_community_id
       and m.profile_id   = auth.uid()
       and m.status       = 'active'
       and m.ended_at is null
  ) then
    raise exception 'You do not belong to this community.' using errcode = 'HB403';
  end if;

  return query
    select d.id, d.name, d.kind
      from public.departments d
     where d.community_id = p_community_id
       and coalesce(d.status, 'active') = 'active'
     order by lower(d.name);
end;
$function$
;

create or replace view "public"."community_module_overview" as  SELECT c.id AS community_id,
    fc.code AS module_key,
    fc.name AS display_name,
    fc.description,
    fc.sort_order,
    fc.backend_status,
    fc.backend_note,
    fc.default_enabled,
    COALESCE(cf.is_enabled, fc.default_enabled) AS enabled,
    (cf.community_id IS NULL) AS is_default,
    cf.updated_at,
    cf.updated_by_membership_id,
    pr.full_name AS updated_by_name
   FROM ((((public.communities c
     CROSS JOIN public.feature_catalog fc)
     LEFT JOIN public.community_features cf ON (((cf.community_id = c.id) AND (cf.feature_code = fc.code))))
     LEFT JOIN public.community_memberships m ON ((m.id = cf.updated_by_membership_id)))
     LEFT JOIN public.profiles pr ON ((pr.id = m.profile_id)))
  WHERE fc.is_active;


create or replace view "public"."community_settings_overview" as  SELECT c.id AS community_id,
    c.name AS community_name,
    c.community_type,
    c.status AS community_status,
    c.created_at AS community_created_at,
    COALESCE(cs.timezone, c.timezone, 'Asia/Kolkata'::text) AS timezone,
    COALESCE(cs.unit_label_singular,
        CASE c.community_type
            WHEN 'apartment'::text THEN 'Flat'::text
            ELSE 'Villa'::text
        END) AS unit_label_singular,
    (cs.unit_label_singular IS NULL) AS unit_label_is_derived,
    COALESCE(cs.invite_ttl_hours, 72) AS invite_ttl_hours,
    COALESCE(cs.visitor_code_ttl_minutes, 120) AS visitor_code_ttl_minutes,
    COALESCE(cs.require_visitor_preapproval, true) AS require_visitor_preapproval,
    COALESCE(cs.notice_sms_broadcast_enabled, false) AS notice_sms_broadcast_enabled,
    (cs.community_id IS NOT NULL) AS has_saved_settings,
    COALESCE(cs.version, 0) AS version,
    cs.updated_at AS settings_updated_at,
    pr.full_name AS settings_updated_by_name,
    COALESCE(bs.auto_billing_enabled, false) AS auto_billing_enabled,
    COALESCE((bs.auto_billing_day)::integer, 1) AS auto_billing_day,
    COALESCE(bs.late_fee_enabled, false) AS late_fee_enabled,
    bs.late_fee_amount,
    COALESCE((bs.late_fee_grace_days)::integer, 10) AS late_fee_grace_days,
    COALESCE(bs.late_fee_period, 'weekly'::text) AS late_fee_period,
    bs.default_maintenance_amount,
    COALESCE(mo.modules_total, (0)::bigint) AS modules_total,
    COALESCE(mo.modules_enabled, (0)::bigint) AS modules_enabled,
    COALESCE(mo.modules_enabled_without_backend, (0)::bigint) AS modules_enabled_without_backend,
    c.latitude,
    c.longitude
   FROM (((((public.communities c
     LEFT JOIN public.community_settings cs ON ((cs.community_id = c.id)))
     LEFT JOIN public.community_billing_settings bs ON ((bs.community_id = c.id)))
     LEFT JOIN public.community_memberships m ON ((m.id = cs.updated_by_membership_id)))
     LEFT JOIN public.profiles pr ON ((pr.id = m.profile_id)))
     LEFT JOIN LATERAL ( SELECT count(*) AS modules_total,
            count(*) FILTER (WHERE v.enabled) AS modules_enabled,
            count(*) FILTER (WHERE (v.enabled AND (v.backend_status = 'absent'::text))) AS modules_enabled_without_backend
           FROM public.community_module_overview v
          WHERE (v.community_id = c.id)) mo ON (true));


create or replace view "public"."complaint_overview" as  SELECT c.id,
    c.community_id,
    c.raised_by_membership_id,
    c.title,
    c.description,
    c.category,
    c.status,
    c.priority,
    c.location,
    c.progress_percent,
    c.assignee_label,
    c.expected_resolution_at,
    c.reopened_count,
    c.resolution_rating,
    c.resident_feedback,
    c.created_at,
    c.updated_at,
    c.resolved_at,
    ((c.expected_resolution_at IS NOT NULL) AND (c.expected_resolution_at < now()) AND (c.status <> ALL (ARRAY['resolved'::public.complaint_status, 'closed'::public.complaint_status, 'cancelled'::public.complaint_status]))) AS is_overdue,
    COALESCE(cm.comment_count, 0) AS comment_count,
    GREATEST(c.updated_at, COALESCE(cm.last_comment_at, c.updated_at)) AS last_activity_at,
    ((rs.last_read_at IS NULL) OR (rs.last_read_at < GREATEST(c.updated_at, COALESCE(cm.last_comment_at, c.updated_at)))) AS is_unread
   FROM ((public.complaints c
     LEFT JOIN LATERAL ( SELECT (count(*))::integer AS comment_count,
            max(cc.created_at) AS last_comment_at
           FROM public.complaint_comments cc
          WHERE ((cc.complaint_id = c.id) AND (cc.visibility = 'public'::text))) cm ON (true))
     LEFT JOIN LATERAL ( SELECT max(rs0.last_read_at) AS last_read_at
           FROM public.complaint_read_state rs0
          WHERE ((rs0.complaint_id = c.id) AND public.is_own_membership(rs0.membership_id))) rs ON (true));


CREATE OR REPLACE FUNCTION public.complete_work_order(p_work_order_id uuid, p_notes text DEFAULT NULL::text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_order     public.work_orders%rowtype;
  v_assign    public.work_order_assignments%rowtype;
  v_staff     public.staff_assignments%rowtype;
  v_complaint public.complaints%rowtype;
  v_notes     text := nullif(btrim(coalesce(p_notes, '')), '');
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  select * into v_assign
    from public.work_order_assignments a
   where a.work_order_id = p_work_order_id
     and a.status = 'accepted'
     and public.is_own_staff_assignment(a.staff_assignment_id)
   limit 1;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  if v_order.status = 'completed' then
    return;
  end if;

  -- `scheduled` is accepted as well as `in_progress`, and not out of leniency: a
  -- worker who fixed the tap and forgot to press *start* has done the work, and
  -- an API that refuses to record it teaches them the app is lying about what
  -- happened. The timeline still shows only what was actually reported.
  if v_order.status not in ('scheduled', 'in_progress') then
    raise exception 'This job cannot be completed from here.' using errcode = 'HB409';
  end if;

  update public.work_order_assignments
     set status = 'completed', ended_at = now()
   where id = v_assign.id;

  update public.work_orders
     set status = 'completed', updated_at = now()
   where id = v_order.id;

  select * into v_staff
    from public.staff_assignments where id = v_assign.staff_assignment_id;
  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_staff.membership_id, 'job_completed',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assigneeName', v_staff.display_name,
      'notes', v_notes)
  );

  -- **The complaint is not resolved by this.** See the header: the person who
  -- decides whether the problem is gone is the person who has the problem.
  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.completed',
      jsonb_build_object(
        'title', 'The visit for your complaint is finished',
        'body', coalesce(v_notes, v_staff.display_name),
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id));
  end if;

  if v_order.supervisor_membership_id is not null
     and v_order.supervisor_membership_id is distinct from v_staff.membership_id then
    perform public.notify_member(
      v_order.supervisor_membership_id, 'work_order.completed',
      jsonb_build_object(
        'title', 'A job was completed',
        'body', v_staff.display_name,
        -- CHANGED: the triage screen, filtered to this job.
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id));
  end if;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.confirm_complaint_resolution(p_complaint_id uuid, p_rating smallint, p_feedback text DEFAULT NULL::text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_row public.complaints%rowtype;
begin
  select * into v_row from public.complaints where id = p_complaint_id;

  if v_row.id is null then
    raise exception 'Complaint not found.' using errcode = 'P0002';
  end if;

  if not public.is_own_membership(v_row.raised_by_membership_id) then
    raise exception 'Only the resident who raised a complaint may confirm it.'
      using errcode = '42501';
  end if;

  if v_row.status <> 'resolved' then
    raise exception 'Only a resolved complaint can be confirmed.'
      using errcode = '23514';
  end if;

  if p_rating is null or p_rating < 1 or p_rating > 5 then
    raise exception 'A resolution rating must be between 1 and 5.'
      using errcode = '23514';
  end if;

  update public.complaints
     set status            = 'closed',
         resolution_rating = p_rating,
         resident_feedback = nullif(btrim(coalesce(p_feedback, '')), ''),
         resolved_at       = coalesce(resolved_at, now()),
         progress_percent  = 100,
         aggregate_version = aggregate_version + 1,
         updated_at        = now()
   where id = p_complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    p_complaint_id, v_row.raised_by_membership_id, 'resolution_confirmed',
    jsonb_build_object(
      'rating', p_rating,
      'feedback', nullif(btrim(coalesce(p_feedback, '')), '')
    )
  );

  -- CHANGED: was `notify_community_staff(v_row.community_id, …)`.
  perform public.notify_complaint_staff(
    p_complaint_id,
    'complaint.resolution_confirmed',
    jsonb_build_object(
      'title', 'A resident confirmed a resolution',
      'body',  v_row.title,
      'url',   '/admin/complaints?complaint=' || p_complaint_id::text,
      'complaint_id', p_complaint_id
    ),
    v_row.raised_by_membership_id
  );
end;
$function$
;

create or replace view "public"."conversation_message_overview" as  SELECT cm.id,
    cm.conversation_id,
    cm.body,
    cm.created_at,
        CASE
            WHEN (cm.author_provider_id IS NOT NULL) THEN 'provider'::text
            ELSE 'department'::text
        END AS author_side,
    COALESCE(p.display_name, pf.full_name, 'Unknown'::text) AS author_name,
    COALESCE(p.profile_id, mem.profile_id) AS author_profile_id
   FROM (((public.conversation_messages cm
     LEFT JOIN public.service_providers p ON ((p.id = cm.author_provider_id)))
     LEFT JOIN public.community_memberships mem ON ((mem.id = cm.author_membership_id)))
     LEFT JOIN public.profiles pf ON ((pf.id = mem.profile_id)));


create or replace view "public"."conversation_overview" as  SELECT c.id,
    c.community_id,
    c.department_id,
    c.service_provider_id,
    c.created_at,
    c.last_message_at,
    com.name AS community_name,
    d.name AS department_name,
    d.kind AS department_kind,
    p.display_name AS provider_display_name,
    p.headline AS provider_headline,
    p.profile_id AS provider_profile_id,
    m.last_body AS last_message_body,
    COALESCE(m.message_count, (0)::bigint) AS message_count
   FROM ((((public.conversations c
     JOIN public.communities com ON ((com.id = c.community_id)))
     JOIN public.departments d ON ((d.id = c.department_id)))
     JOIN public.service_providers p ON ((p.id = c.service_provider_id)))
     LEFT JOIN LATERAL ( SELECT ( SELECT cm.body
                   FROM public.conversation_messages cm
                  WHERE (cm.conversation_id = c.id)
                  ORDER BY cm.created_at DESC
                 LIMIT 1) AS last_body,
            ( SELECT count(*) AS count
                   FROM public.conversation_messages cm2
                  WHERE (cm2.conversation_id = c.id)) AS message_count) m ON (true));


CREATE OR REPLACE FUNCTION public.create_skill(p_name text, p_category text DEFAULT NULL::text, p_description text DEFAULT NULL::text)
 RETURNS TABLE(id uuid, name text, category text, description text, created boolean)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_name text := btrim(coalesce(p_name, ''));
  v_row  public.skills%rowtype;
begin
  if not public.can_author_skills() then
    raise exception 'You may not add to the skill catalogue.'
      using errcode = 'HB403';
  end if;

  if v_name = '' or length(v_name) > 80 then
    raise exception 'A skill name of 1 to 80 characters is required.'
      using errcode = 'HB422';
  end if;

  select * into v_row
    from public.skills s
   where lower(btrim(s.name)) = lower(v_name)
   limit 1;

  if found then
    -- A retired trade being asked for again is a request to bring it back, not
    -- a request for a duplicate under a different capitalisation.
    if not v_row.is_active then
      update public.skills set is_active = true
       where public.skills.id = v_row.id
      returning * into v_row;
    end if;
    return query select v_row.id, v_row.name, v_row.category, v_row.description,
                        false;
    return;
  end if;

  -- `category` and `description` are NOT NULL on the wire (Skill in
  -- service_provider_schemas.py) even though the columns are nullable, and the
  -- worker's registration screen groups its chip grid by category. A created
  -- skill with a null category would 500 GET /skills for every service person,
  -- so the defaults are filled here rather than at the edge: 'other' earns a
  -- visible group in that grid, which is honest -- nobody classified it.
  insert into public.skills (name, category, description)
  values (v_name,
          coalesce(nullif(btrim(coalesce(p_category, '')), ''), 'other'),
          coalesce(nullif(btrim(coalesce(p_description, '')), ''), ''))
  returning * into v_row;

  return query select v_row.id, v_row.name, v_row.category, v_row.description,
                      true;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.decide_complaint_department_change(p_membership_id uuid, p_request_id uuid, p_decision text, p_to_department_id uuid DEFAULT NULL::uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_request  record;
  v_decision text := lower(btrim(coalesce(p_decision, '')));
  v_target   uuid;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'That is not your membership.' using errcode = 'HB403';
  end if;

  if v_decision not in ('accept', 'reject') then
    raise exception 'Decision must be accept or reject.' using errcode = 'HB422';
  end if;

  select r.*, c.community_id
    into v_request
    from public.complaint_department_requests r
    join public.complaints c on c.id = r.complaint_id
   where r.id = p_request_id;

  if v_request.id is null then
    raise exception 'No such request.' using errcode = 'HB404';
  end if;

  if v_request.status <> 'pending' then
    raise exception 'That request has already been decided.' using errcode = 'HB409';
  end if;

  -- The manager of the department being asked to give the complaint up. Not the
  -- supervisor who raised it, even though can_supervise_department would admit
  -- them -- the whole point of the request is that somebody else answers it.
  if not public.can_manage_department(v_request.from_department_id) then
    raise exception 'Only this department''s manager may answer that request.'
      using errcode = 'HB403';
  end if;

  update public.complaint_department_requests
     set status                   = case when v_decision = 'accept'
                                         then 'accepted' else 'rejected' end,
         decided_by_membership_id = p_membership_id,
         decided_at               = now(),
         to_department_id         = coalesce(p_to_department_id, to_department_id)
   where id = p_request_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_request.complaint_id, p_membership_id, 'department_change_' || v_decision || 'ed',
    jsonb_build_object('request_id', p_request_id)
  );

  if v_decision = 'accept' then
    v_target := coalesce(p_to_department_id, v_request.to_department_id);

    if v_target is null then
      -- Accepted with nowhere to send it: back to the admin's triage queue,
      -- which is the honest state. "Not ours, and I do not know whose" is a
      -- legitimate answer and this is what it looks like.
      update public.complaints
         set department_id = null, updated_at = now()
       where id = v_request.complaint_id;

      insert into public.complaint_events
        (complaint_id, actor_membership_id, event_type, payload)
      values (
        v_request.complaint_id, p_membership_id, 'department_assigned',
        jsonb_build_object(
          'from_department_id', v_request.from_department_id,
          'to_department_id',   null
        )
      );

      perform public.notify_community_roles(
        v_request.community_id, array['admin'], 'complaint.unassigned',
        jsonb_build_object(
          'title', 'A complaint needs a department',
          'body',  'A manager returned it for reassignment.',
          -- The triage queue, not the complaints screen. This notification says
          -- "nobody owns this", and the screen that answers that is the one
          -- listing everything nobody owns.
          'url',   '/admin/complaint-triage',
          'complaint_id', v_request.complaint_id
        )
      );
    else
      -- assign_complaint_department re-checks that the caller manages the
      -- department the complaint is leaving, which is exactly what was just
      -- established -- so the move, its timeline entry and the receiving
      -- manager's notification all come from the one place that does them.
      perform public.assign_complaint_department(
        p_membership_id, v_request.complaint_id, v_target
      );
    end if;
  end if;

  -- The supervisor who asked, either way. A request that is silently rejected
  -- is a request they will raise again next week.
  perform public.notify_member(
    v_request.requested_by_membership_id,
    'complaint.department_change_decided',
    jsonb_build_object(
      'title', case when v_decision = 'accept'
                    then 'Your department change was accepted'
                    else 'Your department change was declined' end,
      'body',  'The complaint you flagged has been answered.',
      'url',   '/admin/complaints?complaint=' || v_request.complaint_id::text,
      'complaint_id', v_request.complaint_id
    )
  );
end;
$function$
;

CREATE OR REPLACE FUNCTION public.department_change_requests(p_department_id uuid)
 RETURNS TABLE(id uuid, complaint_id uuid, complaint_title text, to_department_id uuid, to_department_name text, requested_by text, reason text, created_at timestamp with time zone)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'Only this department''s manager sees its change requests.'
      using errcode = 'HB403';
  end if;

  return query
    select
      r.id, r.complaint_id, c.title, r.to_department_id, d.name,
      coalesce(p.full_name, 'A supervisor'), r.reason, r.created_at
    from public.complaint_department_requests r
    join public.complaints c                  on c.id = r.complaint_id
    left join public.departments d            on d.id = r.to_department_id
    left join public.community_memberships m  on m.id = r.requested_by_membership_id
    left join public.profiles p               on p.id = m.profile_id
   where r.from_department_id = p_department_id
     and r.status = 'pending'
   order by r.created_at;
end;
$function$
;

create or replace view "public"."department_overview" as  SELECT d.id,
    d.community_id,
    d.name,
    d.description,
    d.contact_email,
    d.contact_phone_e164,
    d.opens_at,
    d.closes_at,
    d.sla_hours,
    d.kind,
    d.status,
    d.created_at,
    d.updated_at,
    head.display_name AS head_name,
    head.id AS head_staff_id,
    COALESCE(st.staff_count, (0)::bigint) AS staff_count,
    COALESCE(cx.active_complaint_count, (0)::bigint) AS active_complaint_count,
    COALESCE(cx.resolved_complaint_count, (0)::bigint) AS resolved_complaint_count,
    COALESCE(cx.overdue_complaint_count, (0)::bigint) AS overdue_complaint_count,
    COALESCE(cat.category_ids, '{}'::uuid[]) AS category_ids,
    COALESCE(cat.category_names, '{}'::text[]) AS category_names,
    COALESCE(sk.skill_ids, '{}'::uuid[]) AS skill_ids,
    COALESCE(sk.skill_names, '{}'::text[]) AS skill_names,
    lower(concat_ws(' '::text, d.name, d.description, d.contact_email, head.display_name, array_to_string(COALESCE(cat.category_names, '{}'::text[]), ' '::text), array_to_string(COALESCE(sk.skill_names, '{}'::text[]), ' '::text), st.staff_names)) AS search_text
   FROM (((((public.departments d
     LEFT JOIN LATERAL ( SELECT s.id,
            s.display_name
           FROM public.staff_assignments s
          WHERE ((s.department_id = d.id) AND (s.rank = 'manager'::text) AND (s.status = 'active'::text))
         LIMIT 1) head ON (true))
     LEFT JOIN LATERAL ( SELECT count(*) AS staff_count,
            string_agg(s.display_name, ' '::text) AS staff_names
           FROM public.staff_assignments s
          WHERE ((s.department_id = d.id) AND (s.status = 'active'::text))) st ON (true))
     LEFT JOIN LATERAL ( SELECT count(*) FILTER (WHERE (c.status = ANY (ARRAY['open'::public.complaint_status, 'acknowledged'::public.complaint_status, 'in_progress'::public.complaint_status]))) AS active_complaint_count,
            count(*) FILTER (WHERE (c.status = ANY (ARRAY['resolved'::public.complaint_status, 'closed'::public.complaint_status]))) AS resolved_complaint_count,
            count(*) FILTER (WHERE ((c.status = ANY (ARRAY['open'::public.complaint_status, 'acknowledged'::public.complaint_status, 'in_progress'::public.complaint_status])) AND (c.due_at IS NOT NULL) AND (c.due_at < now()))) AS overdue_complaint_count
           FROM public.complaints c
          WHERE (c.department_id = d.id)) cx ON (true))
     LEFT JOIN LATERAL ( SELECT array_agg(cc.id ORDER BY cc.name) AS category_ids,
            array_agg(cc.name ORDER BY cc.name) AS category_names
           FROM (public.department_categories dc
             JOIN public.complaint_categories cc ON ((cc.id = dc.category_id)))
          WHERE (dc.department_id = d.id)) cat ON (true))
     LEFT JOIN LATERAL ( SELECT array_agg(s.id ORDER BY s.name) AS skill_ids,
            array_agg(s.name ORDER BY s.name) AS skill_names
           FROM (public.department_skills ds
             JOIN public.skills s ON ((s.id = ds.skill_id)))
          WHERE ((ds.department_id = d.id) AND s.is_active)) sk ON (true));


CREATE OR REPLACE FUNCTION public.department_skill_list(p_department_id uuid)
 RETURNS TABLE(id uuid, name text, category text, description text, created_at timestamp with time zone)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  return query
    select s.id, s.name, s.category, s.description, ds.created_at
      from public.department_skills ds
      join public.skills s on s.id = ds.skill_id
     where ds.department_id = p_department_id
       and s.is_active
     order by lower(s.name);
end;
$function$
;

CREATE OR REPLACE FUNCTION public.department_staff_invitations(p_department_id uuid, p_status text DEFAULT NULL::text)
 RETURNS TABLE(id uuid, department_id uuid, invitee_email text, invitee_name text, invitee_phone_e164 character varying, rank text, job_title text, status text, claimed_at timestamp with time zone, created_at timestamp with time zone)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  return query
    select
      s.id, s.department_id, s.invitee_email::text, s.invitee_name,
      s.invitee_phone_e164, s.rank, s.job_title, s.status, s.claimed_at,
      s.created_at
      from public.staff_invitations s
     where s.department_id = p_department_id
       and (p_status is null or s.status = p_status)
     order by s.created_at desc;
end;
$function$
;

create or replace view "public"."department_staff_overview" as  SELECT s.id,
    s.community_id,
    s.department_id,
    s.membership_id,
    s.service_provider_id,
    s.display_name,
    s.phone_e164,
    s.job_title,
    s.rank,
    s.shift,
    s.status,
    s.created_at,
    s.updated_at,
    COALESCE(a.active_assignment_count, (0)::bigint) AS active_assignment_count,
    public.staff_open_commitment_count(s.id) AS open_commitment_count,
    dep.status AS departure_status,
    dep.effective_at AS departure_effective_at
   FROM ((public.staff_assignments s
     LEFT JOIN LATERAL ( SELECT count(*) AS active_assignment_count
           FROM public.complaints c
          WHERE ((c.department_id = s.department_id) AND (c.status = ANY (ARRAY['open'::public.complaint_status, 'acknowledged'::public.complaint_status, 'in_progress'::public.complaint_status])) AND (((s.membership_id IS NOT NULL) AND (c.assigned_to_membership_id = s.membership_id)) OR ((s.display_name IS NOT NULL) AND (length(s.display_name) > 0) AND (c.assignee_label IS NOT NULL) AND ("left"(c.assignee_label, length(s.display_name)) = s.display_name))))) a ON (true))
     LEFT JOIN LATERAL ( SELECT d.status,
            COALESCE(d.effective_at, d.requested_effective_at) AS effective_at
           FROM public.staff_departures d
          WHERE ((d.staff_assignment_id = s.id) AND ((d.status = 'pending'::text) OR ((d.status = 'approved'::text) AND (d.effective_at IS NOT NULL) AND (d.effective_at > now()))))
          ORDER BY d.created_at DESC
         LIMIT 1) dep ON (true));


CREATE OR REPLACE FUNCTION public.dispatch_auto_assign(p_work_order_id uuid)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_order      public.work_orders%rowtype;
  v_complaint  public.complaints%rowtype;
  v_pick       record;
  v_assignment uuid;
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    return null;
  end if;

  if v_order.status <> 'offered' or v_order.scheduled_start_at is null then
    return null;
  end if;

  select * into v_pick from public.dispatch_candidates(p_work_order_id, 1);
  if not found then
    -- Same posture as the ping: tell the supervisor, leave the job where a human
    -- can see it, and do not requeue.
    if v_order.supervisor_membership_id is not null then
      perform public.notify_member(
        v_order.supervisor_membership_id, 'work_order.no_candidates',
        jsonb_build_object(
          'title', 'Nobody could be assigned',
          -- CHANGED: the triage screen, filtered to this job.
          'url', '/admin/departments/' || v_order.department_id::text
                 || '/work-orders?job=' || v_order.id::text,
          'work_order_id', v_order.id,
          'complaint_id', v_order.complaint_id,
          'starts_at', v_order.scheduled_start_at));
    end if;
    return null;
  end if;

  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  -- Withdrawn, not deleted: "we asked five people and gave it to Anil" is the
  -- history a supervisor asks about, and section 5 of `0036` made the same call.
  update public.work_order_assignments
     set status = 'withdrawn', responded_at = now()
   where work_order_id = v_order.id
     and status = 'offered';

  -- `work_order_assignments_no_overlap` can still refuse this if somebody was
  -- booked between the sweep and here. That surfaces as a failed task with the
  -- reason in `last_error` and a retry on the next tick, which is the correct
  -- outcome -- the constraint is the guarantee and the sweep is only the guess.
  insert into public.work_order_assignments (
    work_order_id, staff_assignment_id, status, offered_at, responded_at,
    is_auto_assigned, scheduled_start_at, scheduled_end_at
  )
  values (
    v_order.id, v_pick.staff_assignment_id, 'accepted', now(), now(),
    true, v_order.scheduled_start_at, v_order.scheduled_end_at
  )
  returning id into v_assignment;

  update public.work_orders
     set status = 'scheduled', updated_at = now()
   where id = v_order.id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_order.supervisor_membership_id, 'job_assigned',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assigneeName', v_pick.display_name,
      'startsAt', v_order.scheduled_start_at,
      'endsAt', v_order.scheduled_end_at,
      'automatic', true)
  );

  perform public.notify_member(
    v_pick.membership_id, 'work_order.assigned',
    jsonb_build_object(
      'title', 'You have been assigned a job',
      'body', coalesce(v_complaint.title, 'Scheduled work'),
      'url', '/worker?job=' || v_order.id::text,
      'work_order_id', v_order.id,
      'starts_at', v_order.scheduled_start_at,
      'ends_at', v_order.scheduled_end_at));

  -- The resident finds out who is coming, which is the whole point of the
  -- feature from their side and the answer to the phone call it exists to
  -- prevent.
  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.assigned',
      jsonb_build_object(
        'title', 'Someone is coming for your complaint',
        'body', v_pick.display_name,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'starts_at', v_order.scheduled_start_at));
  end if;

  return v_assignment;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.dispatch_failed_visit_escalation(p_work_order_id uuid)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_order     public.work_orders%rowtype;
  v_complaint public.complaints%rowtype;
  v_manager   uuid;
  v_sent      integer := 0;
begin
  select * into v_order from public.work_orders where id = p_work_order_id;
  if not found then
    return false;
  end if;

  -- Not a status check, and the header says why: the failed job stays failed
  -- for good, because the answer to a failed visit is a NEW work order (D5) and
  -- not an edit to this one. So the question this asks is "has a human already
  -- done something about it", and the evidence for that is a newer job on the
  -- same complaint.
  if v_order.complaint_id is not null and exists (
    select 1
      from public.work_orders newer
     where newer.complaint_id = v_order.complaint_id
       and newer.id <> v_order.id
       and newer.created_at > v_order.created_at
  ) then
    return false;
  end if;

  -- Or the complaint itself was settled some other way -- resolved on the phone,
  -- closed as a duplicate. Escalating a visit for a complaint nobody has any
  -- longer is the false alarm that teaches people to ignore the real ones.
  select * into v_complaint from public.complaints where id = v_order.complaint_id;
  if v_complaint.status::text in ('resolved', 'closed') then
    return false;
  end if;

  -- The department's manager first, because the escalation is theirs: a
  -- supervisor who has not rescheduled in two hours is the person being escalated
  -- past, so notifying them again would be telling somebody what they already
  -- decided not to do.
  select m.id into v_manager
    from public.staff_assignments sa
    join public.community_memberships m on m.id = sa.membership_id
   where sa.department_id = v_order.department_id
     and sa.rank = 'manager'
     and sa.status = 'active'
     and m.status = 'active'
     and m.ended_at is null
   limit 1;

  if v_manager is not null then
    perform public.notify_member(
      v_manager, 'work_order.escalated',
      jsonb_build_object(
        'title', 'A visit failed and has not been rebooked',
        'body', coalesce(v_complaint.title, 'Scheduled work'),
        -- CHANGED: the triage screen, filtered to this job. This is the reader
        -- the repoint is most for -- a department manager, whose portal mounts
        -- the same route and who `portalUrl.js` now rewrites for.
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'attempts', v_order.failed_attempt_count));
    v_sent := 1;
  end if;

  -- A department with no manager on its roster is not a rare misconfiguration;
  -- it is every department created through the departments form before anybody
  -- was hired. The community's admins are the fallback, and there is always at
  -- least one of those.
  if v_sent = 0 then
    perform public.notify_community_roles(
      v_order.community_id, array['admin'], 'work_order.escalated',
      jsonb_build_object(
        'title', 'A visit failed and has not been rebooked',
        'body', coalesce(v_complaint.title, 'Scheduled work'),
        -- CHANGED: the triage screen, filtered to this job.
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'attempts', v_order.failed_attempt_count));
  end if;

  return true;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.dispatch_ping_candidates(p_work_order_id uuid)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_order     public.work_orders%rowtype;
  v_complaint public.complaints%rowtype;
  v_row       record;
  v_sent      integer := 0;
begin
  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    return 0;
  end if;

  -- The idempotency check. A second delivery of this task after somebody has
  -- already accepted must not re-offer a job that is taken.
  if v_order.status <> 'offered' or v_order.scheduled_start_at is null then
    return 0;
  end if;

  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  for v_row in
    select * from public.dispatch_candidates(p_work_order_id, 5)
  loop
    -- Not re-offering to somebody still holding an open offer. There is no
    -- unique constraint to lean on here and there should not be: a worker who
    -- declined last week may legitimately be asked again.
    if not exists (
      select 1 from public.work_order_assignments a
       where a.work_order_id = v_order.id
         and a.staff_assignment_id = v_row.staff_assignment_id
         and a.status = 'offered'
    ) then
      insert into public.work_order_assignments (
        work_order_id, staff_assignment_id, status, offered_at,
        is_auto_assigned, scheduled_start_at, scheduled_end_at
      )
      values (
        v_order.id, v_row.staff_assignment_id, 'offered', now(),
        true, v_order.scheduled_start_at, v_order.scheduled_end_at
      );

      perform public.notify_member(
        v_row.membership_id, 'work_order.offered',
        jsonb_build_object(
          'title', 'A job is available',
          'body', coalesce(v_complaint.title, 'Scheduled work'),
          'url', '/worker?job=' || v_order.id::text,
          'work_order_id', v_order.id,
          'complaint_id', v_order.complaint_id,
          'starts_at', v_order.scheduled_start_at,
          'ends_at', v_order.scheduled_end_at));

      v_sent := v_sent + 1;
    end if;
  end loop;

  if v_sent = 0 then
    -- Nobody free, which is an ordinary Tuesday in a department of two and must
    -- not look like a fault. The supervisor is told once and the job stays
    -- `offered` for a human to place by hand. Nothing is re-queued: a retry
    -- loop against an empty roster is a busy loop that never learns anything.
    if v_order.supervisor_membership_id is not null then
      perform public.notify_member(
        v_order.supervisor_membership_id, 'work_order.no_candidates',
        jsonb_build_object(
          'title', 'Nobody is free for that visit',
          'body', coalesce(v_complaint.title, 'Scheduled work'),
          -- CHANGED: the triage screen, filtered to this job.
          'url', '/admin/departments/' || v_order.department_id::text
                 || '/work-orders?job=' || v_order.id::text,
          'work_order_id', v_order.id,
          'complaint_id', v_order.complaint_id,
          'starts_at', v_order.scheduled_start_at));
    end if;
    return 0;
  end if;

  -- Ask, wait, decide. If one of them accepts first, the job moves to
  -- `scheduled` and the trigger in section 2 retires this task before it fires
  -- -- which is why there is no second mechanism for "somebody already took it".
  perform public.enqueue_dispatch_task(
    v_order.id, 'auto_assign', now() + interval '30 minutes');

  return v_sent;
end;
$function$
;

create or replace view "public"."dm_message_overview" as  SELECT id,
    thread_id,
    author_profile_id,
    body,
    created_at
   FROM public.dm_messages m;


create or replace view "public"."dm_thread_overview" as  SELECT t.id,
    t.community_id,
    c.name AS community_name,
    t.kind,
    t.work_order_id,
    t.participant_a_profile_id,
    t.participant_b_profile_id,
    t.participant_a_name,
    t.participant_b_name,
    t.locked_at,
    t.last_message_at,
    t.created_at,
    last_m.body AS last_message_body
   FROM ((public.dm_threads t
     JOIN public.communities c ON ((c.id = t.community_id)))
     LEFT JOIN LATERAL ( SELECT m.body
           FROM public.dm_messages m
          WHERE (m.thread_id = t.id)
          ORDER BY m.created_at DESC
         LIMIT 1) last_m ON (true));


CREATE OR REPLACE FUNCTION public.enforce_professional_membership_mode()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  -- CHANGED: the other half of the separate-account rule. This runs before the
  -- early return below, which exists precisely to ignore the roles it refuses.
  if new.role not in ('worker', 'security')
     and new.status = 'active'
     and new.ended_at is null
     and exists (select 1 from public.service_providers where profile_id = new.profile_id) then
    raise exception 'This account is registered as a service professional. Use a separate account to join a community as a resident, manager or administrator.'
      using errcode = 'HBSEP';
  end if;

  if new.role not in ('worker', 'security')
     or new.status <> 'active'
     or new.ended_at is not null
     or not exists (select 1 from public.service_providers where profile_id = new.profile_id) then
    return new;
  end if;

  if exists (
    select 1 from public.community_memberships m
     where m.profile_id = new.profile_id
       and m.id <> new.id
       and m.role in ('worker', 'security')
       and m.role <> new.role
       and m.status = 'active'
       and m.ended_at is null
  ) then
    raise exception 'A professional account cannot mix worker and security memberships.' using errcode = 'HB409';
  end if;
  return new;
end;
$function$
;

create or replace view "public"."household_overview" as  SELECT (m.id)::text AS id,
    'member'::text AS source,
    r.unit_id,
    m.community_id,
    COALESCE(pr.full_name, 'Resident'::text) AS full_name,
    pr.phone_e164,
    initcap((r.relationship_type)::text) AS relationship,
    r.is_primary_contact,
        CASE m.status
            WHEN 'active'::public.membership_status THEN 'Active'::text
            WHEN 'pending'::public.membership_status THEN 'Pending'::text
            WHEN 'suspended'::public.membership_status THEN 'Suspended'::text
            ELSE 'Ended'::text
        END AS status,
    (r.started_at)::timestamp with time zone AS since
   FROM ((public.unit_residencies r
     JOIN public.community_memberships m ON ((m.id = r.membership_id)))
     LEFT JOIN public.profiles pr ON ((pr.id = m.profile_id)))
  WHERE (r.ended_at IS NULL)
UNION ALL
 SELECT (uc.id)::text AS id,
    'contact'::text AS source,
    uc.unit_id,
    uc.community_id,
    uc.full_name,
    uc.phone_e164,
    COALESCE(NULLIF(btrim(uc.relationship), ''::text), 'Contact'::text) AS relationship,
    false AS is_primary_contact,
    'Contact'::text AS status,
    uc.created_at AS since
   FROM public.unit_contacts uc
  WHERE uc.is_active;


CREATE OR REPLACE FUNCTION public.invite_staff_member(p_department_id uuid, p_email text, p_name text, p_rank text, p_phone text DEFAULT NULL::text, p_job_title text DEFAULT NULL::text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_email      citext := lower(btrim(coalesce(p_email, '')))::citext;
  v_name       text   := btrim(coalesce(p_name, ''));
  v_rank       text   := lower(btrim(coalesce(p_rank, '')));
  v_department record;
  v_actor      uuid;
  v_id         uuid;
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  if v_email = '' or position('@' in v_email::text) = 0 then
    raise exception 'A valid email address is required.' using errcode = 'HB422';
  end if;

  if v_name = '' then
    raise exception 'A name is required.' using errcode = 'HB422';
  end if;

  if v_rank not in ('manager', 'supervisor') then
    raise exception 'Rank must be manager or supervisor.' using errcode = 'HB422';
  end if;

  select d.id, d.community_id, d.kind into v_department
    from public.departments d
   where d.id = p_department_id;

  select m.id into v_actor
    from public.community_memberships m
   where m.community_id = v_department.community_id
     and m.profile_id = auth.uid()
     and m.status = 'active'
     and m.ended_at is null
   limit 1;

  -- Already a member of this community, under any role. The claim would fail on
  -- the same check, so offering the invitation would be offering a dead end --
  -- the same reasoning search_hireable_service_providers uses to hide people
  -- who already belong (0035 601-608).
  -- `display_email`, not `email`: that is the column name on profiles, and it
  -- is citext, so this comparison is case-insensitive without a lower() that
  -- would defeat the index. `upsert_profile` writes the GoTrue identity's email
  -- into it on first sign-in (profiles_repository.py:52), which is the same
  -- value claim_staff_invitations matches on below.
  if exists (
    select 1
      from public.community_memberships m
      join public.profiles p on p.id = m.profile_id
     where m.community_id = v_department.community_id
       and p.display_email = v_email
       and m.status = 'active'
       and m.ended_at is null
  ) then
    raise exception 'That person already belongs to this community.'
      using errcode = 'HB409';
  end if;

  insert into public.staff_invitations (
    community_id, department_id, invitee_email, invitee_name,
    invitee_phone_e164, rank, job_title, created_by_membership_id
  )
  values (
    v_department.community_id, p_department_id, v_email, v_name,
    nullif(btrim(coalesce(p_phone, '')), ''), v_rank,
    nullif(btrim(coalesce(p_job_title, '')), ''), v_actor
  )
  returning id into v_id;

  return v_id;
end;
$function$
;

create or replace view "public"."invoice_overview" as  SELECT i.id,
    i.community_id,
    i.unit_id,
    i.invoice_number,
    i.invoice_type,
    i.title,
    (i.status)::text AS status,
    i.billing_period_start,
    i.billing_period_end,
    i.issued_on,
    i.due_on,
    i.subtotal_amount,
    i.tax_amount,
    i.total_amount,
    GREATEST((i.total_amount - COALESCE(p.amount_paid, (0)::numeric)), (0)::numeric) AS outstanding_amount,
    COALESCE(p.amount_paid, (0)::numeric) AS amount_paid,
    i.currency_code,
    i.notes,
    i.created_at,
    i.updated_at,
    u.unit_code,
    b.name AS tower,
    res.membership_id AS resident_membership_id,
    res.profile_id AS resident_profile_id,
    res.full_name AS resident_name,
    p.paid_on,
    p.payment_method,
    ((i.status <> 'void'::public.invoice_status) AND (i.due_on IS NOT NULL) AND (i.due_on < CURRENT_DATE) AND ((i.total_amount - COALESCE(p.amount_paid, (0)::numeric)) > (0)::numeric)) AS is_overdue,
    lower(concat_ws(' '::text, i.title, i.invoice_number, u.unit_code, b.name, res.full_name)) AS search_text
   FROM ((((public.invoices i
     LEFT JOIN public.units u ON ((u.id = i.unit_id)))
     LEFT JOIN public.buildings b ON ((b.id = u.building_id)))
     LEFT JOIN LATERAL ( SELECT sum(pay.amount) AS amount_paid,
            max(pay.paid_at) AS paid_on,
            (array_agg(pay.payment_method ORDER BY pay.paid_at DESC) FILTER (WHERE (pay.payment_method IS NOT NULL)))[1] AS payment_method
           FROM public.payments pay
          WHERE ((pay.invoice_id = i.id) AND (pay.status = 'succeeded'::public.payment_status))) p ON (true))
     LEFT JOIN LATERAL ( SELECT m.id AS membership_id,
            m.profile_id,
            pr.full_name
           FROM ((public.unit_residencies r
             JOIN public.community_memberships m ON ((m.id = r.membership_id)))
             LEFT JOIN public.profiles pr ON ((pr.id = m.profile_id)))
          WHERE ((r.unit_id = i.unit_id) AND (r.ended_at IS NULL))
          ORDER BY r.is_primary_contact DESC, r.started_at DESC
         LIMIT 1) res ON (true));


create or replace view "public"."management_contact_overview" as  SELECT d.id,
    d.community_id,
    d.name,
    COALESCE(NULLIF(btrim(d.category), ''::text), 'Management'::text) AS category,
    d.description,
    d.contact_phone_e164 AS phone_e164,
    (d.contact_email)::text AS email,
    d.opens_at,
    d.closes_at,
    d.hours,
    pr.full_name AS head_name,
    pr.phone_e164 AS head_phone_e164
   FROM ((public.departments d
     LEFT JOIN public.community_memberships hm ON ((hm.id = d.manager_membership_id)))
     LEFT JOIN public.profiles pr ON ((pr.id = hm.profile_id)))
  WHERE (d.is_active AND (d.status = 'active'::text));


create or replace view "public"."material_movement_overview" as  SELECT m.id,
    m.community_id,
    m.direction,
    m.description,
    m.quantity,
    m.unit,
    m.is_returnable,
    m.expected_return_at,
    m.returned_at,
    m.carrier_name,
    m.vehicle_number,
    m.unit_id,
    u.unit_code,
    m.post_id,
    p.name AS post_name,
    m.notes,
    m.recorded_by_membership_id,
    m.recorded_at,
    m.source_client_id,
    (m.is_returnable AND (m.returned_at IS NULL)) AS is_outstanding,
    (m.is_returnable AND (m.returned_at IS NULL) AND (m.expected_return_at IS NOT NULL) AND (m.expected_return_at < now())) AS is_overdue
   FROM ((public.material_movements m
     LEFT JOIN public.units u ON ((u.id = m.unit_id)))
     LEFT JOIN public.security_posts p ON ((p.id = m.post_id)));


create or replace view "public"."my_worker_availability_rule" as  SELECT r.id,
    r.weekday,
    r.start_time,
    r.end_time,
    r.effective_from,
    r.effective_to,
    r.service_provider_id,
    r.staff_assignment_id,
        CASE
            WHEN (r.service_provider_id IS NOT NULL) THEN 'provider'::text
            ELSE 'roster'::text
        END AS scope,
    d.name AS department_name
   FROM ((public.worker_availability_rules r
     LEFT JOIN public.staff_assignments sa ON ((sa.id = r.staff_assignment_id)))
     LEFT JOIN public.departments d ON ((d.id = sa.department_id)))
  WHERE (((r.service_provider_id IS NOT NULL) AND (EXISTS ( SELECT 1
           FROM public.service_providers p
          WHERE ((p.id = r.service_provider_id) AND (p.profile_id = auth.uid()))))) OR ((r.staff_assignment_id IS NOT NULL) AND public.is_own_staff_assignment(r.staff_assignment_id)));


create or replace view "public"."my_worker_job" as  SELECT a.id AS assignment_id,
    a.work_order_id,
    a.staff_assignment_id,
    a.status AS assignment_status,
    a.offered_at,
    a.responded_at,
    a.decline_reason,
    a.is_auto_assigned,
    a.is_forced,
    COALESCE(a.scheduled_start_at, w.scheduled_start_at) AS scheduled_start_at,
    COALESCE(a.scheduled_end_at, w.scheduled_end_at) AS scheduled_end_at,
    w.status AS work_order_status,
    w.priority,
    w.subject_kind,
    w.location_text,
    w.failed_attempt_count,
    w.cancelled_reason,
    w.community_id,
    cm.name AS community_name,
    w.department_id,
    d.name AS department_name,
    d.kind AS department_kind,
    w.complaint_id,
    c.title AS complaint_title,
    c.description AS complaint_description,
    c.category AS complaint_category,
    sk.name AS skill_name,
    res.full_name AS resident_name,
    res.phone_e164 AS resident_phone_e164,
    res.unit_code AS resident_unit_code
   FROM ((((((public.work_order_assignments a
     JOIN public.work_orders w ON ((w.id = a.work_order_id)))
     LEFT JOIN public.communities cm ON ((cm.id = w.community_id)))
     LEFT JOIN public.departments d ON ((d.id = w.department_id)))
     LEFT JOIN public.complaints c ON ((c.id = w.complaint_id)))
     LEFT JOIN public.skills sk ON ((sk.id = w.skill_id)))
     LEFT JOIN LATERAL ( SELECT p.full_name,
            p.phone_e164,
            u.unit_code
           FROM ((public.community_memberships m
             JOIN public.profiles p ON ((p.id = m.profile_id)))
             LEFT JOIN LATERAL ( SELECT un.unit_code
                   FROM (public.unit_residencies ur
                     JOIN public.units un ON ((un.id = ur.unit_id)))
                  WHERE ((ur.membership_id = m.id) AND (ur.ended_at IS NULL))
                  ORDER BY ur.is_primary_contact DESC, ur.started_at
                 LIMIT 1) u ON (true))
          WHERE ((m.id = c.raised_by_membership_id) AND (w.subject_kind = 'resident'::text))) res ON (true))
  WHERE public.is_own_staff_assignment(a.staff_assignment_id);


create or replace view "public"."my_worker_unavailability" as  SELECT u.id,
    u.starts_at,
    u.ends_at,
    u.reason,
    u.created_at,
    u.service_provider_id,
    u.staff_assignment_id,
        CASE
            WHEN (u.service_provider_id IS NOT NULL) THEN 'provider'::text
            ELSE 'roster'::text
        END AS scope,
    d.name AS department_name
   FROM ((public.worker_unavailability u
     LEFT JOIN public.staff_assignments sa ON ((sa.id = u.staff_assignment_id)))
     LEFT JOIN public.departments d ON ((d.id = sa.department_id)))
  WHERE (((u.service_provider_id IS NOT NULL) AND (EXISTS ( SELECT 1
           FROM public.service_providers p
          WHERE ((p.id = u.service_provider_id) AND (p.profile_id = auth.uid()))))) OR ((u.staff_assignment_id IS NOT NULL) AND public.is_own_staff_assignment(u.staff_assignment_id)));


create or replace view "public"."notification_overview" as  SELECT n.id,
    n.recipient_membership_id,
    n.recipient_profile_id,
    m.community_id,
    n.kind,
    n.payload,
    n.read_at,
    (n.read_at IS NULL) AS is_unread,
    n.created_at
   FROM (public.notifications n
     LEFT JOIN public.community_memberships m ON ((m.id = n.recipient_membership_id)));


CREATE OR REPLACE FUNCTION public.notify_complaint_staff(p_complaint_id uuid, p_kind text, p_payload jsonb, p_exclude_membership uuid DEFAULT NULL::uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_complaint record;
  v_manager   record;
begin
  select c.community_id, c.department_id into v_complaint
    from public.complaints c
   where c.id = p_complaint_id;

  if v_complaint.community_id is null then
    return;
  end if;

  perform public.notify_community_roles(
    v_complaint.community_id, array['admin'], p_kind, p_payload,
    p_exclude_membership
  );

  if v_complaint.department_id is null then
    return;
  end if;

  for v_manager in
    select m.id
      from public.community_memberships m
     where m.community_id  = v_complaint.community_id
       and m.department_id = v_complaint.department_id
       and m.role::text    = 'manager'
       and m.status        = 'active'
       and m.ended_at is null
       and (p_exclude_membership is null or m.id <> p_exclude_membership)
  loop
    perform public.notify_member(v_manager.id, p_kind, p_payload);
  end loop;
end;
$function$
;

create or replace view "public"."payment_overview" as  SELECT pay.id,
    pay.community_id,
    pay.invoice_id,
    pay.amount,
    pay.currency_code,
    pay.payment_method,
    pay.provider_reference,
    (pay.status)::text AS status,
    pay.paid_at,
    pay.notes,
    pay.created_at,
    i.invoice_number,
    i.title AS invoice_title,
    i.unit_id,
    u.unit_code,
    pay.payer_profile_id,
    pr.full_name AS payer_name,
    pay.received_by_membership_id,
    lower(concat_ws(' '::text, i.invoice_number, i.title, u.unit_code, pr.full_name, pay.provider_reference)) AS search_text
   FROM (((public.payments pay
     LEFT JOIN public.invoices i ON ((i.id = pay.invoice_id)))
     LEFT JOIN public.units u ON ((u.id = i.unit_id)))
     LEFT JOIN public.profiles pr ON ((pr.id = pay.payer_profile_id)));


create or replace view "public"."pending_access_request_overview" as  SELECT ar.id,
    ar.community_id,
    ar.applicant_name,
    (ar.applicant_email)::text AS applicant_email,
    ar.applicant_phone_e164,
    (ar.requested_relationship)::text AS requested_relationship,
    ar.status,
    ar.created_at,
    ar.requested_unit_id,
    u.unit_code AS requested_unit_code,
    c.name AS community_name
   FROM ((public.access_requests ar
     JOIN public.communities c ON ((c.id = ar.community_id)))
     LEFT JOIN public.units u ON ((u.id = ar.requested_unit_id)))
  WHERE (ar.status = 'pending'::public.request_status);


CREATE OR REPLACE FUNCTION public.professional_membership_role(p_department_kind text)
 RETURNS public.membership_role
 LANGUAGE sql
 IMMUTABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select case when p_department_kind = 'security' then 'security' else 'worker' end
         ::public.membership_role;
$function$
;

CREATE OR REPLACE FUNCTION public.record_security_incident(p_membership_id uuid, p_summary text, p_category text DEFAULT 'other'::text, p_severity text DEFAULT 'medium'::text, p_details text DEFAULT NULL::text, p_location_text text DEFAULT NULL::text, p_post_id uuid DEFAULT NULL::uuid, p_occurred_at timestamp with time zone DEFAULT NULL::timestamp with time zone, p_source_client_id text DEFAULT NULL::text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_community uuid := public.gate_community_for(p_membership_id);
  v_summary   text := nullif(btrim(coalesce(p_summary, '')), '');
  v_severity  text := lower(btrim(coalesce(p_severity, 'medium')));
  v_client    text := nullif(btrim(coalesce(p_source_client_id, '')), '');
  v_id        uuid;
  v_payload   jsonb;   -- CHANGED: both new, for the split audience below.
  v_manager   record;
begin
  if v_summary is null then
    raise exception 'Say what happened.' using errcode = '22004';
  end if;

  if v_client is not null then
    select id into v_id
      from public.security_incidents
     where community_id = v_community and source_client_id = v_client;
    if v_id is not null then
      return v_id;
    end if;
  end if;

  insert into public.security_incidents
    (community_id, category, severity, summary, details, location_text,
     post_id, occurred_at, reported_by_membership_id, source_client_id)
  values (
    v_community, coalesce(nullif(btrim(lower(coalesce(p_category, ''))), ''), 'other'),
    v_severity, v_summary, nullif(btrim(coalesce(p_details, '')), ''),
    nullif(btrim(coalesce(p_location_text, '')), ''), p_post_id,
    coalesce(p_occurred_at, now()), p_membership_id, v_client)
  returning id into v_id;

  -- The one register write that notifies. A tanker arriving is a record;
  -- something going wrong at the gate at 2am is a message, and `high` or
  -- `critical` is the line between the two.
  if v_severity in ('high', 'critical') then
    -- CHANGED: was one `notify_community_roles(…, array['admin', 'manager'], …)`.
    v_payload := jsonb_build_object(
      'title', 'Security incident reported',
      'body',  v_summary,
      'url',   '/admin/security/incidents'
    );

    perform public.notify_community_roles(
      v_community, array['admin'], 'security.incident', v_payload
    );

    for v_manager in
      select m.id
        from public.community_memberships m
        join public.departments d on d.id = m.department_id
       where m.community_id = v_community
         and m.role::text   = 'manager'
         and m.status       = 'active'
         and m.ended_at is null
         and d.kind         = 'security'
    loop
      perform public.notify_member(v_manager.id, 'security.incident', v_payload);
    end loop;
  end if;

  return v_id;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.remove_department_skill(p_department_id uuid, p_skill_id uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  delete from public.department_skills
   where department_id = p_department_id
     and skill_id = p_skill_id;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.reopen_complaint(p_complaint_id uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_row    public.complaints%rowtype;
  v_reason text := nullif(btrim(coalesce(p_reason, '')), '');
begin
  select * into v_row from public.complaints where id = p_complaint_id;

  if v_row.id is null then
    raise exception 'Complaint not found.' using errcode = 'P0002';
  end if;

  if not public.is_own_membership(v_row.raised_by_membership_id) then
    raise exception 'Only the resident who raised a complaint may reopen it.'
      using errcode = '42501';
  end if;

  if v_row.status not in ('resolved', 'closed') then
    -- The message says "resolved" and the check accepts `closed` as well
    -- because both render as `Resolved` on the wire (`vocabularies.py`). A
    -- message naming a status the resident's screen never shows would be
    -- describing a state they cannot see themselves in.
    raise exception 'Only a resolved complaint can be reopened.'
      using errcode = '23514';
  end if;

  if v_reason is null then
    raise exception 'Reopening a complaint needs a reason.' using errcode = '23514';
  end if;

  update public.complaints
     set status                 = 'open',
         progress_percent       = 0,
         resolved_at            = null,
         resolution_rating      = null,
         resident_feedback      = null,
         reopened_count         = reopened_count + 1,
         expected_resolution_at = now()
           + make_interval(hours => public.complaint_sla_hours(priority)),
         aggregate_version      = aggregate_version + 1,
         updated_at             = now()
   where id = p_complaint_id;

  -- Two events, because two things happened. `0020`'s reader counts reopenings
  -- by looking for a `status_changed` whose `from` is terminal, and that query
  -- must keep working; the `reopened` event is what carries the resident's
  -- reason.
  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values
    (p_complaint_id, v_row.raised_by_membership_id, 'status_changed',
     jsonb_build_object('from', v_row.status::text, 'to', 'open')),
    (p_complaint_id, v_row.raised_by_membership_id, 'reopened',
     jsonb_build_object('reason', v_reason));

  -- CHANGED: was `notify_community_staff(v_row.community_id, …)`.
  perform public.notify_complaint_staff(
    p_complaint_id,
    'complaint.reopened',
    jsonb_build_object(
      'title', 'A complaint was reopened',
      'body',  v_row.title,
      'url',   '/admin/complaints?complaint=' || p_complaint_id::text,
      'complaint_id', p_complaint_id
    ),
    v_row.raised_by_membership_id
  );
end;
$function$
;

CREATE OR REPLACE FUNCTION public.report_work_order_failure(p_work_order_id uuid, p_reason text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_order     public.work_orders%rowtype;
  v_assign    public.work_order_assignments%rowtype;
  v_staff     public.staff_assignments%rowtype;
  v_complaint public.complaints%rowtype;
  v_reason    text := nullif(btrim(coalesce(p_reason, '')), '');
begin
  -- Required, unlike the completion note. "Could not be done" with no reason is
  -- the report that guarantees a second wasted visit: nobody downstream can tell
  -- *nobody was home* from *the part is out of stock*, and those need opposite
  -- responses.
  if v_reason is null then
    raise exception 'Say what went wrong.' using errcode = '22004';
  end if;

  select * into v_order from public.work_orders where id = p_work_order_id
    for update;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  select * into v_assign
    from public.work_order_assignments a
   where a.work_order_id = p_work_order_id
     and a.status = 'accepted'
     and public.is_own_staff_assignment(a.staff_assignment_id)
   limit 1;
  if not found then
    raise exception 'No such job.' using errcode = 'HB404';
  end if;

  if v_order.status not in ('scheduled', 'in_progress') then
    raise exception 'This job cannot be reported from here.' using errcode = 'HB409';
  end if;

  update public.work_order_assignments
     set status = 'failed', ended_at = now(), decline_reason = v_reason
   where id = v_assign.id;

  -- Which arms `failed_visit_escalation` through `0037`'s trigger. Nothing here
  -- names the queue.
  update public.work_orders
     set status               = 'failed',
         failed_attempt_count = failed_attempt_count + 1,
         updated_at           = now()
   where id = v_order.id;

  select * into v_staff
    from public.staff_assignments where id = v_assign.staff_assignment_id;
  select * into v_complaint from public.complaints where id = v_order.complaint_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    v_order.complaint_id, v_staff.membership_id, 'job_failed',
    jsonb_build_object(
      'workOrderId', v_order.id,
      'assigneeName', v_staff.display_name,
      'reason', v_reason,
      'attempt', v_order.failed_attempt_count + 1)
  );

  if v_order.supervisor_membership_id is not null
     and v_order.supervisor_membership_id is distinct from v_staff.membership_id then
    perform public.notify_member(
      v_order.supervisor_membership_id, 'work_order.failed',
      jsonb_build_object(
        'title', 'A visit could not be completed',
        'body', v_reason,
        -- CHANGED: the triage screen, filtered to this job.
        'url', '/admin/departments/' || v_order.department_id::text
               || '/work-orders?job=' || v_order.id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id,
        'attempts', v_order.failed_attempt_count + 1));
  end if;

  -- The resident waited in for this. Telling them it did not happen is the
  -- whole difference between a bad afternoon and the phone call this feature
  -- exists to prevent -- and the reason is theirs to read, because half the
  -- reasons a visit fails are things only they can fix.
  if v_complaint.raised_by_membership_id is not null then
    perform public.notify_member(
      v_complaint.raised_by_membership_id, 'work_order.failed',
      jsonb_build_object(
        'title', 'The visit for your complaint could not be completed',
        'body', v_reason,
        'url', '/resident/complaints?complaint=' || v_order.complaint_id::text,
        'work_order_id', v_order.id,
        'complaint_id', v_order.complaint_id));
  end if;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.request_complaint_department_change(p_membership_id uuid, p_complaint_id uuid, p_to_department_id uuid DEFAULT NULL::uuid, p_reason text DEFAULT NULL::text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_complaint record;
  v_id        uuid;
  v_manager   record;
begin
  if not public.is_own_membership(p_membership_id) then
    raise exception 'That is not your membership.' using errcode = 'HB403';
  end if;

  select c.id, c.community_id, c.department_id, c.title
    into v_complaint
    from public.complaints c
   where c.id = p_complaint_id;

  if v_complaint.id is null then
    raise exception 'No such complaint.' using errcode = 'HB404';
  end if;

  -- Nothing to move it out of. An unrouted complaint is the admin's to allot,
  -- and there is no manager whose inbox this request would land in.
  if v_complaint.department_id is null then
    raise exception 'That complaint has not been assigned to a department yet.'
      using errcode = 'HB409';
  end if;

  if not public.can_supervise_department(v_complaint.department_id) then
    raise exception 'You do not work on this department''s complaints.'
      using errcode = 'HB403';
  end if;

  if p_to_department_id is not null
     and not exists (
       select 1 from public.departments d
        where d.id = p_to_department_id
          and d.community_id = v_complaint.community_id
     ) then
    raise exception 'No such department in this community.' using errcode = 'HB404';
  end if;

  if p_to_department_id = v_complaint.department_id then
    raise exception 'That complaint is already with that department.'
      using errcode = 'HB409';
  end if;

  insert into public.complaint_department_requests (
    complaint_id, from_department_id, to_department_id,
    requested_by_membership_id, reason
  )
  values (
    p_complaint_id, v_complaint.department_id, p_to_department_id,
    p_membership_id, nullif(btrim(coalesce(p_reason, '')), '')
  )
  returning id into v_id;

  insert into public.complaint_events
    (complaint_id, actor_membership_id, event_type, payload)
  values (
    p_complaint_id, p_membership_id, 'department_change_requested',
    jsonb_build_object(
      'request_id', v_id,
      'to_department_id', p_to_department_id,
      'reason', nullif(btrim(coalesce(p_reason, '')), '')
    )
  );

  -- The manager of the department that currently holds it -- the one person who
  -- can answer. `_portal_for`'s predicate again, for the same reason.
  for v_manager in
    select m.id
      from public.community_memberships m
     where m.community_id  = v_complaint.community_id
       and m.department_id = v_complaint.department_id
       and m.role::text    = 'manager'
       and m.status        = 'active'
       and m.ended_at is null
  loop
    perform public.notify_member(
      v_manager.id,
      'complaint.department_change_requested',
      jsonb_build_object(
        'title', 'A supervisor says a complaint is not yours',
        'body',  v_complaint.title,
        'url',   '/admin/complaints?complaint=' || p_complaint_id::text,
        'complaint_id', p_complaint_id
      )
    );
  end loop;

  return v_id;
end;
$function$
;

create or replace view "public"."resident_booking_overview" as  SELECT bk.id,
    bk.community_id,
    COALESCE(bk.booking_group_id, bk.id) AS booking_series_id,
    bk.booked_by_membership_id AS requested_by_membership_id,
    bk.amenity_id,
    am.name AS amenity_name,
    bk.title,
    bk.starts_at,
    bk.ends_at,
    ((bk.starts_at AT TIME ZONE COALESCE(cs.timezone, c.timezone, 'Asia/Kolkata'::text)))::date AS booking_date,
        CASE bk.status
            WHEN 'requested'::public.booking_status THEN 'Pending'::text
            WHEN 'approved'::public.booking_status THEN 'Approved'::text
            WHEN 'rejected'::public.booking_status THEN 'Rejected'::text
            WHEN 'cancelled'::public.booking_status THEN 'Cancelled'::text
            WHEN 'completed'::public.booking_status THEN 'Completed'::text
            WHEN 'no_show'::public.booking_status THEN 'No Show'::text
            ELSE initcap((bk.status)::text)
        END AS status,
    (bk.status)::text AS stored_status,
    bk.guest_count,
    bk.is_private,
    bk.notes,
    bk.cancelled_at,
    bk.cancellation_reason,
    bk.rejection_reason,
    bk.created_at,
    COALESCE(ch.total_amount, (0)::numeric) AS total_amount,
    COALESCE(ev.amount_paid, (0)::numeric) AS amount_paid,
    GREATEST((COALESCE(ch.total_amount, (0)::numeric) - COALESCE(ev.amount_paid, (0)::numeric)), (0)::numeric) AS outstanding_amount,
    ((bk.status = ANY (ARRAY['requested'::public.booking_status, 'approved'::public.booking_status])) AND ((COALESCE(ch.total_amount, (0)::numeric) - COALESCE(ev.amount_paid, (0)::numeric)) > (0)::numeric)) AS is_payable,
    (bk.starts_at >= now()) AS is_upcoming
   FROM (((((public.amenity_bookings bk
     JOIN public.amenities am ON ((am.id = bk.amenity_id)))
     JOIN public.communities c ON ((c.id = bk.community_id)))
     LEFT JOIN public.community_settings cs ON ((cs.community_id = bk.community_id)))
     LEFT JOIN LATERAL ( SELECT sum(x.amount) AS total_amount
           FROM public.amenity_booking_charges x
          WHERE (x.booking_occurrence_id = bk.id)) ch ON (true))
     LEFT JOIN LATERAL ( SELECT sum(e.amount) AS amount_paid
           FROM (public.amenity_financial_events e
             JOIN public.amenity_booking_charges x ON ((x.id = e.booking_charge_id)))
          WHERE ((x.booking_occurrence_id = bk.id) AND (e.event_type = 'payment'::text))) ev ON (true));


create or replace view "public"."resident_invoice_overview" as  SELECT i.id,
    i.community_id,
    i.membership_id,
    i.unit_id,
    i.invoice_number,
    i.invoice_type,
    COALESCE(NULLIF(btrim(i.title), ''::text), 'Maintenance'::text) AS title,
        CASE i.status
            WHEN 'paid'::public.invoice_status THEN 'Paid'::text
            WHEN 'void'::public.invoice_status THEN 'Cancelled'::text
            ELSE 'Unpaid'::text
        END AS status,
    (i.status)::text AS stored_status,
    i.issued_on,
    i.due_on,
    i.total_amount,
    COALESCE(p.amount_paid, (0)::numeric) AS amount_paid,
    GREATEST((i.total_amount - COALESCE(p.amount_paid, (0)::numeric)), (0)::numeric) AS outstanding_amount,
    i.currency_code,
    i.notes,
    i.created_at,
    p.paid_at,
    p.payment_method,
    p.instrument_label,
    ((i.status <> 'void'::public.invoice_status) AND (i.due_on IS NOT NULL) AND (i.due_on < CURRENT_DATE) AND ((i.total_amount - COALESCE(p.amount_paid, (0)::numeric)) > (0)::numeric)) AS is_overdue,
    ((i.status <> ALL (ARRAY['paid'::public.invoice_status, 'void'::public.invoice_status, 'draft'::public.invoice_status])) AND ((i.total_amount - COALESCE(p.amount_paid, (0)::numeric)) > (0)::numeric)) AS is_payable,
    public.is_own_invoice(i.id) AS is_mine
   FROM (public.invoices i
     LEFT JOIN LATERAL ( SELECT sum(pay.amount) AS amount_paid,
            max(pay.paid_at) AS paid_at,
            (array_agg(pay.payment_method ORDER BY pay.paid_at DESC))[1] AS payment_method,
            (array_agg(pay.instrument_label ORDER BY pay.paid_at DESC))[1] AS instrument_label
           FROM public.payments pay
          WHERE ((pay.invoice_id = i.id) AND (pay.status = 'succeeded'::public.payment_status))) p ON (true))
  WHERE (i.status <> 'draft'::public.invoice_status);


create or replace view "public"."resident_notice_overview" as  SELECT n.id,
    n.community_id,
    n.title,
    n.body,
    n.category,
    initcap(n.urgency) AS urgency,
    n.urgency AS stored_urgency,
    COALESCE(n.published_at, n.created_at) AS published_at,
    n.created_at,
    pr.full_name AS author_name
   FROM ((public.notices n
     LEFT JOIN public.community_memberships m ON ((m.id = n.author_membership_id)))
     LEFT JOIN public.profiles pr ON ((pr.id = m.profile_id)))
  WHERE (n.published_at IS NOT NULL);


CREATE OR REPLACE FUNCTION public.revoke_staff_invitation(p_invitation_id uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_department uuid;
  v_status     text;
begin
  select s.department_id, s.status into v_department, v_status
    from public.staff_invitations s
   where s.id = p_invitation_id;

  if v_department is null then
    raise exception 'No such invitation.' using errcode = 'HB404';
  end if;

  if not public.can_manage_department(v_department) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  if v_status = 'claimed' then
    raise exception 'That invitation has already been claimed.'
      using errcode = 'HB409';
  end if;

  update public.staff_invitations
     set status = 'revoked', updated_at = now()
   where id = p_invitation_id;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.search_hireable_service_providers(p_department_id uuid, p_query text DEFAULT NULL::text, p_limit integer DEFAULT 20, p_offset integer DEFAULT 0)
 RETURNS TABLE(id uuid, display_name text, headline text, phone_e164 character varying, status text, is_available boolean, service_radius_km numeric, distance_km numeric, matching_skill_names text[], skill_names text[], community_count integer, has_open_application boolean)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
#variable_conflict use_column
declare
  v_department public.departments%rowtype;
  v_community public.communities%rowtype;
  v_role text;
begin
  if not public.can_hire_for_department(p_department_id) then
    raise exception 'You may not hire for this department.' using errcode = 'HB403';
  end if;
  select * into v_department from public.departments where id = p_department_id and is_active;
  if not found then raise exception 'No such department.' using errcode = 'HB404'; end if;
  select * into v_community from public.communities where id = v_department.community_id;
  if v_community.location is null then
    return;
  end if;
  v_role := public.professional_membership_role(v_department.kind::text);

  return query
  with needed as (
    -- CHANGED: was the category path alone. Now the union of it with the
    -- department's own declared skills.
    select distinct cc.skill_id
      from public.department_categories dc
      join public.complaint_categories cc on cc.id = dc.category_id
     where dc.department_id = p_department_id and cc.skill_id is not null
    union
    select distinct ds.skill_id
      from public.department_skills ds
     where ds.department_id = p_department_id
  )
  select p.id, p.display_name, p.headline, p.phone_e164, p.status, p.is_available,
         p.service_radius_km,
         round((extensions.st_distance(v_community.location, p.location) / 1000)::numeric, 2),
         array_agg(distinct ms.name order by ms.name),
         coalesce((
           select array_agg(s2.name order by s2.name)
             from public.service_provider_skills x
             join public.skills s2 on s2.id = x.skill_id and s2.is_active
            where x.service_provider_id = p.id
         ), '{}'::text[]),
         (select count(*)::integer from public.community_memberships m
           where m.profile_id = p.profile_id and m.role in ('worker', 'security')
             and m.status = 'active' and m.ended_at is null),
         exists(select 1 from public.service_applications a
           where a.department_id = p_department_id and a.service_provider_id = p.id and a.status = 'pending')
    from public.service_providers p
    join public.service_provider_skills sps on sps.service_provider_id = p.id and sps.skill_id in (select skill_id from needed)
    join public.skills ms on ms.id = sps.skill_id and ms.is_active
   where p.status = 'active'
     and p.is_available
     and p.location is not null
     -- Constant outer bound lets the GiST index prune the global provider set;
     -- the next predicate applies each professional's stricter chosen radius.
     and extensions.st_dwithin(p.location, v_community.location, 500000)
     and extensions.st_dwithin(p.location, v_community.location, p.service_radius_km * 1000)
     and (p_query is null or p.display_name ilike '%' || btrim(p_query) || '%')
     and not exists (select 1 from public.blacklisted_service_providers b
       where b.community_id = v_department.community_id and b.service_provider_id = p.id and b.revoked_at is null)
     and not exists (select 1 from public.staff_assignments sa
       where sa.department_id = p_department_id and sa.service_provider_id = p.id and sa.status = 'active')
     and not exists (select 1 from public.community_memberships m
       where m.community_id = v_department.community_id and m.profile_id = p.profile_id
         and m.status = 'active' and m.ended_at is null)
     and not exists (select 1 from public.community_memberships m
       where m.profile_id = p.profile_id and m.role in ('worker', 'security') and m.role::text <> v_role
         and m.status = 'active' and m.ended_at is null)
   group by p.id, p.display_name, p.headline, p.phone_e164, p.status,
            p.is_available, p.service_radius_km, p.profile_id, p.location
   order by extensions.st_distance(v_community.location, p.location), lower(p.display_name), p.id
   limit greatest(1, least(coalesce(p_limit, 20), 20))
   offset greatest(0, coalesce(p_offset, 0));
end;
$function$
;

CREATE OR REPLACE FUNCTION public.search_skills(p_query text DEFAULT NULL::text, p_limit integer DEFAULT 10)
 RETURNS TABLE(id uuid, name text, category text, description text, is_exact boolean, score real)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'extensions'
AS $function$
  select
    s.id,
    s.name,
    s.category,
    s.description,
    lower(btrim(s.name)) = lower(btrim(coalesce(p_query, ''))) as is_exact,
    case
      when p_query is null or btrim(p_query) = '' then 0::real
      else similarity(lower(s.name), lower(btrim(p_query)))
    end as score
  from public.skills s
 where s.is_active
   and (
     p_query is null
     or btrim(p_query) = ''
     or lower(s.name) like lower(btrim(p_query)) || '%'
     or similarity(lower(s.name), lower(btrim(p_query))) > 0.15
   )
 order by
   lower(btrim(s.name)) = lower(btrim(coalesce(p_query, ''))) desc,
   case
     when p_query is null or btrim(p_query) = '' then 1
     when lower(s.name) like lower(btrim(p_query)) || '%' then 0
     else 1
   end,
   case
     when p_query is null or btrim(p_query) = '' then 0::real
     else similarity(lower(s.name), lower(btrim(p_query)))
   end desc,
   s.name
 limit greatest(1, least(coalesce(p_limit, 10), 50));
$function$
;

create or replace view "public"."security_incident_overview" as  SELECT i.id,
    i.community_id,
    i.category,
    i.severity,
    i.status,
    i.summary,
    i.details,
    i.location_text,
    i.post_id,
    p.name AS post_name,
    i.occurred_at,
    i.resolved_at,
    i.reported_by_membership_id,
    COALESCE(NULLIF(btrim(pr.full_name), ''::text), 'Security'::text) AS reported_by_name,
    i.source_client_id,
    i.created_at,
    i.updated_at
   FROM (((public.security_incidents i
     LEFT JOIN public.security_posts p ON ((p.id = i.post_id)))
     LEFT JOIN public.community_memberships m ON ((m.id = i.reported_by_membership_id)))
     LEFT JOIN public.profiles pr ON ((pr.id = m.profile_id)));


create or replace view "public"."security_shift_overview" as  SELECT s.id,
    s.community_id,
    s.department_id,
    s.post_id,
    p.name AS post_name,
    s.staff_assignment_id,
    sa.display_name AS guard_name,
    sa.phone_e164 AS guard_phone_e164,
    sa.job_title AS guard_job_title,
    sa.rank AS guard_rank,
    s.starts_at,
    s.ends_at,
    s.status,
    s.notes,
    s.created_at,
    s.updated_at
   FROM ((public.security_shifts s
     LEFT JOIN public.security_posts p ON ((p.id = s.post_id)))
     LEFT JOIN public.staff_assignments sa ON ((sa.id = s.staff_assignment_id)));


create or replace view "public"."service_application_overview" as  SELECT a.id,
    a.community_id,
    a.department_id,
    a.service_provider_id,
    a.direction,
    a.status,
    a.message,
    a.rank,
    a.job_title,
    a.shift,
    a.decision_note,
    a.decided_at,
    a.created_at,
    a.updated_at,
    c.name AS community_name,
    d.name AS department_name,
    d.kind AS department_kind,
    p.display_name AS provider_display_name,
    p.headline AS provider_headline,
    p.phone_e164 AS provider_phone_e164,
    p.status AS provider_status,
    COALESCE(sk.skill_names, '{}'::text[]) AS provider_skill_names,
        CASE
            WHEN ((c.location IS NULL) OR (p.location IS NULL)) THEN NULL::numeric
            ELSE round(((extensions.st_distance(c.location, p.location) / (1000)::double precision))::numeric, 2)
        END AS distance_km
   FROM ((((public.service_applications a
     JOIN public.communities c ON ((c.id = a.community_id)))
     JOIN public.departments d ON ((d.id = a.department_id)))
     JOIN public.service_providers p ON ((p.id = a.service_provider_id)))
     LEFT JOIN LATERAL ( SELECT array_agg(s.name ORDER BY s.name) AS skill_names
           FROM (public.service_provider_skills sps
             JOIN public.skills s ON ((s.id = sps.skill_id)))
          WHERE ((sps.service_provider_id = p.id) AND s.is_active)) sk ON (true));


create or replace view "public"."service_engagement_overview" as  SELECT sa.id AS staff_assignment_id,
    sa.community_id,
    sa.department_id,
    sa.membership_id,
    sa.service_provider_id,
    sa.rank,
    sa.job_title,
    sa.shift,
    sa.status,
    sa.started_at,
    sa.ended_at,
    c.name AS community_name,
    c.city AS community_city,
    d.name AS department_name,
    d.kind AS department_kind,
    (m.role)::text AS membership_role,
    p.profile_id
   FROM ((((public.staff_assignments sa
     JOIN public.service_providers p ON ((p.id = sa.service_provider_id)))
     JOIN public.communities c ON ((c.id = sa.community_id)))
     JOIN public.departments d ON ((d.id = sa.department_id)))
     LEFT JOIN public.community_memberships m ON ((m.id = sa.membership_id)))
  WHERE (sa.service_provider_id IS NOT NULL);


create or replace view "public"."service_provider_overview" as  SELECT p.id,
    p.profile_id,
    p.display_name,
    p.headline,
    p.bio,
    p.phone_e164,
    p.latitude,
    p.longitude,
    p.service_radius_km,
    p.status,
    p.is_available,
    p.created_at,
    p.updated_at,
    COALESCE(sk.skill_ids, ARRAY[]::uuid[]) AS skill_ids,
    COALESCE(sk.skill_names, ARRAY[]::text[]) AS skill_names,
    COALESCE(mem.community_count, (0)::bigint) AS community_count
   FROM ((public.service_providers p
     LEFT JOIN LATERAL ( SELECT array_agg(s.id ORDER BY s.name) AS skill_ids,
            array_agg(s.name ORDER BY s.name) AS skill_names
           FROM (public.service_provider_skills sps
             JOIN public.skills s ON ((s.id = sps.skill_id)))
          WHERE (sps.service_provider_id = p.id)) sk ON (true))
     LEFT JOIN LATERAL ( SELECT count(*) AS community_count
           FROM public.community_memberships m
          WHERE ((m.profile_id = p.profile_id) AND (m.role = ANY (ARRAY['worker'::public.membership_role, 'security'::public.membership_role])) AND (m.status = 'active'::public.membership_status) AND (m.ended_at IS NULL))) mem ON (true));


CREATE OR REPLACE FUNCTION public.set_department_skills(p_department_id uuid, p_skill_ids uuid[])
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_ids uuid[] := coalesce(p_skill_ids, '{}'::uuid[]);
  v_bad uuid;
begin
  if not public.can_manage_department(p_department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  select x into v_bad
    from unnest(v_ids) as x
   where not exists (
     select 1 from public.skills s where s.id = x and s.is_active
   )
   limit 1;

  if v_bad is not null then
    raise exception 'No active skill with id %.', v_bad using errcode = 'HB422';
  end if;

  delete from public.department_skills
   where department_id = p_department_id
     and not (skill_id = any(v_ids));

  insert into public.department_skills (department_id, skill_id)
  select p_department_id, unnest(v_ids)
  on conflict do nothing;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.settle_amenity_booking_payment(p_booking_id uuid, p_payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_community_id uuid;
  v_membership   uuid;
  v_status       public.booking_status;
  v_amenity      text;
  v_charge_id    uuid;
  v_key          text := nullif(btrim(coalesce(p_payload ->> 'idempotency_key', '')), '');
  v_outcome      text := lower(coalesce(p_payload ->> 'status', ''));
  v_amount       numeric(12, 2) := (p_payload ->> 'amount')::numeric;
  v_charged      numeric(12, 2);
  v_paid         numeric(12, 2);
  v_outstanding  numeric(12, 2);
  v_id           uuid;
  v_target       uuid;
begin
  select bk.community_id, bk.booked_by_membership_id, bk.status, am.name
    into v_community_id, v_membership, v_status, v_amenity
    from public.amenity_bookings bk
    join public.amenities am on am.id = bk.amenity_id
   where bk.id = p_booking_id;

  if v_community_id is null then
    raise exception 'Booking not found.' using errcode = 'P0002';
  end if;

  -- Not filtered by `event_type`, unlike `record_amenity_payment`. A key
  -- identifies an attempt, and a replayed attempt that was declined must return
  -- the decline. `0023`'s unique index is on
  -- `(community_id, event_type, payment_reference)`, so falling through would not
  -- even be refused: it would write a `payment` beside the `payment_failed` that
  -- already exists and confirm a booking off the back of a card that declined.
  if v_key is not null then
    select e.id, x.booking_occurrence_id into v_id, v_target
      from public.amenity_financial_events e
      join public.amenity_booking_charges x on x.id = e.booking_charge_id
     where e.community_id = v_community_id
       and e.payment_reference = v_key
     limit 1;

    if v_id is not null then
      if v_target is distinct from p_booking_id then
        raise exception 'That idempotency key already settled a different booking.'
          using errcode = 'HB409';
      end if;
      return public.booking_payment_as_outcome(v_id);
    end if;
  end if;

  if not public.is_own_booking(p_booking_id) then
    raise exception 'You may only pay for your own booking.' using errcode = '42501';
  end if;

  if v_key is null then
    raise exception 'A payment needs an idempotency key.' using errcode = '22004';
  end if;

  if v_outcome not in ('succeeded', 'failed') then
    raise exception 'A settlement must be succeeded or failed.' using errcode = '22P02';
  end if;

  if v_status not in ('requested', 'approved') then
    raise exception 'This booking can no longer be paid for.' using errcode = '23514';
  end if;

  select id, amount into v_charge_id, v_charged
    from public.amenity_booking_charges
   where booking_occurrence_id = p_booking_id
   order by amount desc
   limit 1;

  if v_charge_id is null then
    raise exception 'This booking has nothing to pay.' using errcode = 'HB409';
  end if;

  select coalesce(sum(x.amount), 0), coalesce(sum(e.amount), 0)
    into v_charged, v_paid
    from public.amenity_booking_charges x
    left join public.amenity_financial_events e
           on e.booking_charge_id = x.id and e.event_type = 'payment'
   where x.booking_occurrence_id = p_booking_id;

  v_outstanding := greatest(v_charged - v_paid, 0);

  if v_outstanding <= 0 then
    raise exception 'This booking has already been paid.' using errcode = 'HB409';
  end if;

  if v_amount is null or v_amount <> v_outstanding then
    raise exception 'A payment must settle the full outstanding balance.'
      using errcode = '23514';
  end if;

  insert into public.amenity_financial_events (
    community_id, booking_charge_id, event_type, amount, payment_reference,
    reason, notes, instrument_label, actor_membership_id
  )
  values (
    v_community_id,
    v_charge_id,
    case when v_outcome = 'succeeded' then 'payment' else 'payment_failed' end,
    v_amount,
    v_key,
    case when v_outcome = 'failed'
         then nullif(btrim(coalesce(p_payload ->> 'failure_code', '')), '')
         else null end,
    -- `simulator:` here does the job `provider = 'simulator'` does on `payments`.
    -- The ledger has no provider column, so this prefix is the only thing in an
    -- admin's export that says the money did not move.
    case when v_outcome = 'succeeded'
         then 'simulator: ' || coalesce(p_payload ->> 'instrument_label', 'payment')
         else 'simulator: declined' end,
    nullif(btrim(coalesce(p_payload ->> 'instrument_label', '')), ''),
    v_membership
  )
  returning id into v_id;

  if v_outcome = 'succeeded' then
    -- The half that makes this one transaction rather than two.
    update public.amenity_bookings
       set status            = 'approved',
           approved_at       = coalesce(approved_at, now()),
           aggregate_version = aggregate_version + 1,
           updated_at        = now()
     where id = p_booking_id
       and status = 'requested';
  end if;

  if v_membership is not null then
    perform public.notify_member(
      v_membership,
      case when v_outcome = 'succeeded' then 'payment.succeeded' else 'payment.failed' end,
      jsonb_build_object(
        'title', case when v_outcome = 'succeeded'
                      then 'Booking confirmed' else 'Payment failed' end,
        'body',  case when v_outcome = 'succeeded'
                      then v_amenity || ' is booked and paid for.'
                      else 'Your booking payment did not go through. The booking is unchanged.' end,
        'url',   '/resident/amenities',
        'booking_id', p_booking_id,
        'failure_code', p_payload ->> 'failure_code'
      )
    );
  end if;

  if v_outcome = 'succeeded' then
    -- CHANGED: was `notify_community_staff(v_community_id, …)`.
    perform public.notify_community_roles(
      v_community_id,
      array['admin'],
      'amenity.booking_paid',
      jsonb_build_object(
        'title', 'An amenity booking was paid',
        'body',  v_amenity,
        'url',   '/admin/amenities?booking=' || p_booking_id::text,
        'booking_id', p_booking_id
      ),
      v_membership
    );
  end if;

  return public.booking_payment_as_outcome(v_id);
end;
$function$
;

create or replace view "public"."staff_departure_overview" as  SELECT d.id,
    d.community_id,
    d.department_id,
    d.staff_assignment_id,
    d.service_provider_id,
    d.initiated_by,
    d.reason,
    d.status,
    d.requested_effective_at,
    d.effective_at,
    d.decided_at,
    d.decision_note,
    d.created_at,
    d.updated_at,
    s.display_name,
    s.rank,
    s.job_title,
    s.membership_id,
    dep.name AS department_name,
    dep.kind AS department_kind,
    public.staff_open_commitment_count(d.staff_assignment_id) AS open_commitment_count,
    public.staff_conflict_count(d.staff_assignment_id, COALESCE(d.effective_at, d.requested_effective_at)) AS conflict_count
   FROM ((public.staff_departures d
     JOIN public.staff_assignments s ON ((s.id = d.staff_assignment_id)))
     JOIN public.departments dep ON ((dep.id = d.department_id)));


CREATE OR REPLACE FUNCTION public.unassigned_complaints(p_community_id uuid)
 RETURNS TABLE(id uuid, title text, description text, category text, status text, priority text, created_at timestamp with time zone, raised_by text, unit_code text)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  if not public.is_community_admin(p_community_id) then
    raise exception 'Only an administrator sees the triage queue.'
      using errcode = 'HB403';
  end if;

  return query
    select
      c.id, c.title, c.description, c.category, c.status::text, c.priority,
      c.created_at,
      coalesce(p.full_name, 'A resident'),
      u.unit_code
    from public.complaints c
    left join public.community_memberships m on m.id = c.raised_by_membership_id
    left join public.profiles p              on p.id = m.profile_id
    left join public.unit_residencies ur
           on ur.membership_id = m.id and ur.ended_at is null
    left join public.units u                 on u.id = ur.unit_id
   where c.community_id  = p_community_id
     and c.department_id is null
     and c.status::text <> 'resolved'
   order by c.created_at;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.update_staff_invitation(p_invitation_id uuid, p_email text DEFAULT NULL::text, p_name text DEFAULT NULL::text, p_rank text DEFAULT NULL::text, p_phone text DEFAULT NULL::text, p_job_title text DEFAULT NULL::text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_row   public.staff_invitations%rowtype;
  v_email citext;
  v_name  text;
  v_rank  text;
begin
  select * into v_row
    from public.staff_invitations
   where id = p_invitation_id;

  if v_row.id is null then
    raise exception 'No such invitation.' using errcode = 'HB404';
  end if;

  if not public.can_manage_department(v_row.department_id) then
    raise exception 'You do not manage this department.' using errcode = 'HB403';
  end if;

  -- Both non-pending states are terminal, and they fail differently on purpose:
  -- a claimed invitation has already become a membership and a roster row, so
  -- editing the email here would change nothing about who got in.
  if v_row.status = 'claimed' then
    raise exception 'That invitation has already been claimed.'
      using errcode = 'HB409';
  end if;

  if v_row.status <> 'pending' then
    raise exception 'That invitation has been withdrawn.' using errcode = 'HB409';
  end if;

  v_email := coalesce(lower(btrim(p_email))::citext, v_row.invitee_email);
  v_name  := coalesce(btrim(p_name), v_row.invitee_name);
  v_rank  := coalesce(lower(btrim(p_rank)), v_row.rank);

  if v_email::text = '' or position('@' in v_email::text) = 0 then
    raise exception 'A valid email address is required.' using errcode = 'HB422';
  end if;

  if v_name = '' then
    raise exception 'A name is required.' using errcode = 'HB422';
  end if;

  if v_rank not in ('manager', 'supervisor') then
    raise exception 'Rank must be manager or supervisor.' using errcode = 'HB422';
  end if;

  -- The same two collisions invite_staff_member checks, re-checked because the
  -- email is changing. The second one is also enforced by
  -- staff_invitations_one_open_email, but a unique-violation surfaces to the API
  -- as an unhandled 500; catching it here gives the admin the sentence that tells
  -- them what to do.
  if exists (
    select 1
      from public.community_memberships m
      join public.profiles p on p.id = m.profile_id
     where m.community_id = v_row.community_id
       and p.display_email = v_email
       and m.status = 'active'
       and m.ended_at is null
  ) then
    raise exception 'That person already belongs to this community.'
      using errcode = 'HB409';
  end if;

  if exists (
    select 1
      from public.staff_invitations s
     where s.community_id  = v_row.community_id
       and s.invitee_email = v_email
       and s.status        = 'pending'
       and s.id           <> p_invitation_id
  ) then
    raise exception 'Somebody has already been invited at that address.'
      using errcode = 'HB409';
  end if;

  update public.staff_invitations
     set invitee_email      = v_email,
         invitee_name       = v_name,
         rank               = v_rank,
         invitee_phone_e164 = case
           when p_phone is null then invitee_phone_e164
           else nullif(btrim(p_phone), '')
         end,
         job_title          = case
           when p_job_title is null then job_title
           else nullif(btrim(p_job_title), '')
         end,
         updated_at         = now()
   where id = p_invitation_id;
end;
$function$
;

create or replace view "public"."visitor_pass_overview" as  SELECT id,
    community_id,
    requested_by_membership_id,
    visitor_name,
    visitor_phone_e164,
    purpose,
    purpose_details,
    guest_count,
    status,
    valid_from,
    valid_until,
    approved_by_membership_id,
    checked_in_at,
    checked_out_at,
    decided_at,
    cancelled_at,
    created_at,
    updated_at,
    (((status = ANY (ARRAY['expected'::public.visitor_status, 'pending_approval'::public.visitor_status, 'approved'::public.visitor_status])) AND ((valid_until IS NULL) OR (valid_until >= now()))) OR (status = 'checked_in'::public.visitor_status)) AS is_current,
    ((status = ANY (ARRAY['expected'::public.visitor_status, 'pending_approval'::public.visitor_status, 'approved'::public.visitor_status])) AND (valid_until IS NOT NULL) AND (valid_until < now())) AS is_lapsed
   FROM public.visitor_requests v;


create or replace view "public"."water_tanker_log_overview" as  SELECT t.id,
    t.community_id,
    t.supplier_name,
    t.tanker_number,
    t.volume_litres,
    t.driver_name,
    t.driver_phone_e164,
    t.arrived_at,
    t.departed_at,
    t.post_id,
    p.name AS post_name,
    t.notes,
    t.recorded_by_membership_id,
    t.source_client_id,
    (t.departed_at IS NULL) AS is_on_site
   FROM (public.water_tanker_logs t
     LEFT JOIN public.security_posts p ON ((p.id = t.post_id)));


create or replace view "public"."work_order_assignment_overview" as  SELECT a.id,
    a.work_order_id,
    a.staff_assignment_id,
    a.status,
    a.offered_at,
    a.responded_at,
    a.decline_reason,
    a.is_auto_assigned,
    a.scheduled_start_at,
    a.scheduled_end_at,
    a.assigned_at,
    a.ended_at,
    w.community_id,
    w.department_id,
    w.complaint_id,
    w.status AS work_order_status,
    w.priority AS work_order_priority,
    w.subject_kind,
    w.location_text,
    sa.display_name AS worker_name,
    sa.phone_e164 AS worker_phone_e164,
    sa.membership_id AS worker_membership_id,
    sa.service_provider_id AS worker_provider_id
   FROM ((public.work_order_assignments a
     JOIN public.work_orders w ON ((w.id = a.work_order_id)))
     LEFT JOIN public.staff_assignments sa ON ((sa.id = a.staff_assignment_id)));


create or replace view "public"."work_order_overview" as  SELECT w.id,
    w.community_id,
    w.complaint_id,
    w.department_id,
    w.supervisor_membership_id,
    w.skill_id,
    w.status,
    w.priority,
    w.subject_kind,
    w.location_text,
    w.latitude,
    w.longitude,
    w.scheduled_start_at,
    w.scheduled_end_at,
    w.resident_deadline_at,
    w.failed_attempt_count,
    w.cancelled_reason,
    w.created_at,
    w.updated_at,
    c.title AS complaint_title,
    c.category AS complaint_category,
    (c.status)::text AS complaint_status,
    c.raised_by_membership_id AS resident_membership_id,
    d.name AS department_name,
    d.kind AS department_kind,
    s.name AS skill_name,
    a.assignment_id,
    a.staff_assignment_id,
    a.assignment_status,
    a.assignee_name,
    a.assignee_membership_id,
    a.assignee_provider_id
   FROM ((((public.work_orders w
     LEFT JOIN public.complaints c ON ((c.id = w.complaint_id)))
     LEFT JOIN public.departments d ON ((d.id = w.department_id)))
     LEFT JOIN public.skills s ON ((s.id = w.skill_id)))
     LEFT JOIN LATERAL ( SELECT woa.id AS assignment_id,
            woa.staff_assignment_id,
            woa.status AS assignment_status,
            sa.display_name AS assignee_name,
            sa.membership_id AS assignee_membership_id,
            sa.service_provider_id AS assignee_provider_id
           FROM (public.work_order_assignments woa
             LEFT JOIN public.staff_assignments sa ON ((sa.id = woa.staff_assignment_id)))
          WHERE ((woa.work_order_id = w.id) AND (woa.status = 'accepted'::text))
          ORDER BY woa.offered_at DESC
         LIMIT 1) a ON (true));


grant delete on table "public"."access_requests" to "anon";

grant insert on table "public"."access_requests" to "anon";

grant select on table "public"."access_requests" to "anon";

grant update on table "public"."access_requests" to "anon";

grant delete on table "public"."access_requests" to "authenticated";

grant insert on table "public"."access_requests" to "authenticated";

grant update on table "public"."access_requests" to "authenticated";

grant delete on table "public"."amenities" to "anon";

grant insert on table "public"."amenities" to "anon";

grant select on table "public"."amenities" to "anon";

grant update on table "public"."amenities" to "anon";

grant delete on table "public"."amenities" to "authenticated";

grant insert on table "public"."amenities" to "authenticated";

grant select on table "public"."amenities" to "authenticated";

grant update on table "public"."amenities" to "authenticated";

grant delete on table "public"."amenity_booking_charges" to "anon";

grant insert on table "public"."amenity_booking_charges" to "anon";

grant select on table "public"."amenity_booking_charges" to "anon";

grant update on table "public"."amenity_booking_charges" to "anon";

grant delete on table "public"."amenity_booking_charges" to "authenticated";

grant insert on table "public"."amenity_booking_charges" to "authenticated";

grant update on table "public"."amenity_booking_charges" to "authenticated";

grant delete on table "public"."amenity_booking_guests" to "anon";

grant insert on table "public"."amenity_booking_guests" to "anon";

grant select on table "public"."amenity_booking_guests" to "anon";

grant update on table "public"."amenity_booking_guests" to "anon";

grant delete on table "public"."amenity_booking_guests" to "authenticated";

grant insert on table "public"."amenity_booking_guests" to "authenticated";

grant update on table "public"."amenity_booking_guests" to "authenticated";

grant delete on table "public"."amenity_bookings" to "anon";

grant insert on table "public"."amenity_bookings" to "anon";

grant select on table "public"."amenity_bookings" to "anon";

grant update on table "public"."amenity_bookings" to "anon";

grant delete on table "public"."amenity_bookings" to "authenticated";

grant insert on table "public"."amenity_bookings" to "authenticated";

grant update on table "public"."amenity_bookings" to "authenticated";

grant delete on table "public"."amenity_financial_events" to "anon";

grant insert on table "public"."amenity_financial_events" to "anon";

grant select on table "public"."amenity_financial_events" to "anon";

grant update on table "public"."amenity_financial_events" to "anon";

grant delete on table "public"."amenity_financial_events" to "authenticated";

grant insert on table "public"."amenity_financial_events" to "authenticated";

grant update on table "public"."amenity_financial_events" to "authenticated";

grant delete on table "public"."amenity_rules" to "anon";

grant insert on table "public"."amenity_rules" to "anon";

grant references on table "public"."amenity_rules" to "anon";

grant select on table "public"."amenity_rules" to "anon";

grant trigger on table "public"."amenity_rules" to "anon";

grant truncate on table "public"."amenity_rules" to "anon";

grant update on table "public"."amenity_rules" to "anon";

grant delete on table "public"."amenity_rules" to "authenticated";

grant insert on table "public"."amenity_rules" to "authenticated";

grant references on table "public"."amenity_rules" to "authenticated";

grant select on table "public"."amenity_rules" to "authenticated";

grant trigger on table "public"."amenity_rules" to "authenticated";

grant truncate on table "public"."amenity_rules" to "authenticated";

grant update on table "public"."amenity_rules" to "authenticated";

grant delete on table "public"."amenity_rules" to "service_role";

grant insert on table "public"."amenity_rules" to "service_role";

grant references on table "public"."amenity_rules" to "service_role";

grant select on table "public"."amenity_rules" to "service_role";

grant trigger on table "public"."amenity_rules" to "service_role";

grant truncate on table "public"."amenity_rules" to "service_role";

grant update on table "public"."amenity_rules" to "service_role";

grant delete on table "public"."audit_events" to "anon";

grant insert on table "public"."audit_events" to "anon";

grant select on table "public"."audit_events" to "anon";

grant update on table "public"."audit_events" to "anon";

grant delete on table "public"."audit_events" to "authenticated";

grant insert on table "public"."audit_events" to "authenticated";

grant select on table "public"."audit_events" to "authenticated";

grant update on table "public"."audit_events" to "authenticated";

grant delete on table "public"."blacklisted_residents" to "anon";

grant insert on table "public"."blacklisted_residents" to "anon";

grant select on table "public"."blacklisted_residents" to "anon";

grant update on table "public"."blacklisted_residents" to "anon";

grant delete on table "public"."blacklisted_residents" to "authenticated";

grant insert on table "public"."blacklisted_residents" to "authenticated";

grant update on table "public"."blacklisted_residents" to "authenticated";

grant delete on table "public"."blacklisted_service_providers" to "anon";

grant insert on table "public"."blacklisted_service_providers" to "anon";

grant select on table "public"."blacklisted_service_providers" to "anon";

grant update on table "public"."blacklisted_service_providers" to "anon";

grant delete on table "public"."blacklisted_service_providers" to "authenticated";

grant insert on table "public"."blacklisted_service_providers" to "authenticated";

grant update on table "public"."blacklisted_service_providers" to "authenticated";

grant delete on table "public"."booking_charges" to "anon";

grant insert on table "public"."booking_charges" to "anon";

grant select on table "public"."booking_charges" to "anon";

grant update on table "public"."booking_charges" to "anon";

grant delete on table "public"."booking_charges" to "authenticated";

grant insert on table "public"."booking_charges" to "authenticated";

grant select on table "public"."booking_charges" to "authenticated";

grant update on table "public"."booking_charges" to "authenticated";

grant delete on table "public"."booking_guests" to "anon";

grant insert on table "public"."booking_guests" to "anon";

grant references on table "public"."booking_guests" to "anon";

grant select on table "public"."booking_guests" to "anon";

grant trigger on table "public"."booking_guests" to "anon";

grant truncate on table "public"."booking_guests" to "anon";

grant update on table "public"."booking_guests" to "anon";

grant delete on table "public"."booking_guests" to "authenticated";

grant insert on table "public"."booking_guests" to "authenticated";

grant references on table "public"."booking_guests" to "authenticated";

grant select on table "public"."booking_guests" to "authenticated";

grant trigger on table "public"."booking_guests" to "authenticated";

grant truncate on table "public"."booking_guests" to "authenticated";

grant update on table "public"."booking_guests" to "authenticated";

grant delete on table "public"."booking_guests" to "service_role";

grant insert on table "public"."booking_guests" to "service_role";

grant references on table "public"."booking_guests" to "service_role";

grant select on table "public"."booking_guests" to "service_role";

grant trigger on table "public"."booking_guests" to "service_role";

grant truncate on table "public"."booking_guests" to "service_role";

grant update on table "public"."booking_guests" to "service_role";

grant delete on table "public"."booking_refunds" to "anon";

grant insert on table "public"."booking_refunds" to "anon";

grant select on table "public"."booking_refunds" to "anon";

grant update on table "public"."booking_refunds" to "anon";

grant delete on table "public"."booking_refunds" to "authenticated";

grant insert on table "public"."booking_refunds" to "authenticated";

grant select on table "public"."booking_refunds" to "authenticated";

grant update on table "public"."booking_refunds" to "authenticated";

grant delete on table "public"."buildings" to "anon";

grant insert on table "public"."buildings" to "anon";

grant select on table "public"."buildings" to "anon";

grant update on table "public"."buildings" to "anon";

grant delete on table "public"."buildings" to "authenticated";

grant insert on table "public"."buildings" to "authenticated";

grant select on table "public"."buildings" to "authenticated";

grant update on table "public"."buildings" to "authenticated";

grant delete on table "public"."communities" to "anon";

grant insert on table "public"."communities" to "anon";

grant select on table "public"."communities" to "anon";

grant update on table "public"."communities" to "anon";

grant delete on table "public"."communities" to "authenticated";

grant insert on table "public"."communities" to "authenticated";

grant update on table "public"."communities" to "authenticated";

grant delete on table "public"."community_admin_terms" to "anon";

grant insert on table "public"."community_admin_terms" to "anon";

grant select on table "public"."community_admin_terms" to "anon";

grant update on table "public"."community_admin_terms" to "anon";

grant delete on table "public"."community_admin_terms" to "authenticated";

grant insert on table "public"."community_admin_terms" to "authenticated";

grant select on table "public"."community_admin_terms" to "authenticated";

grant update on table "public"."community_admin_terms" to "authenticated";

grant delete on table "public"."community_billing_settings" to "anon";

grant insert on table "public"."community_billing_settings" to "anon";

grant select on table "public"."community_billing_settings" to "anon";

grant update on table "public"."community_billing_settings" to "anon";

grant delete on table "public"."community_billing_settings" to "authenticated";

grant insert on table "public"."community_billing_settings" to "authenticated";

grant update on table "public"."community_billing_settings" to "authenticated";

grant delete on table "public"."community_features" to "anon";

grant insert on table "public"."community_features" to "anon";

grant select on table "public"."community_features" to "anon";

grant update on table "public"."community_features" to "anon";

grant delete on table "public"."community_features" to "authenticated";

grant insert on table "public"."community_features" to "authenticated";

grant select on table "public"."community_features" to "authenticated";

grant update on table "public"."community_features" to "authenticated";

grant delete on table "public"."community_memberships" to "anon";

grant insert on table "public"."community_memberships" to "anon";

grant select on table "public"."community_memberships" to "anon";

grant update on table "public"."community_memberships" to "anon";

grant delete on table "public"."community_memberships" to "authenticated";

grant insert on table "public"."community_memberships" to "authenticated";

grant update on table "public"."community_memberships" to "authenticated";

grant delete on table "public"."community_registration_requests" to "anon";

grant insert on table "public"."community_registration_requests" to "anon";

grant references on table "public"."community_registration_requests" to "anon";

grant select on table "public"."community_registration_requests" to "anon";

grant trigger on table "public"."community_registration_requests" to "anon";

grant truncate on table "public"."community_registration_requests" to "anon";

grant update on table "public"."community_registration_requests" to "anon";

grant delete on table "public"."community_registration_requests" to "authenticated";

grant insert on table "public"."community_registration_requests" to "authenticated";

grant references on table "public"."community_registration_requests" to "authenticated";

grant select on table "public"."community_registration_requests" to "authenticated";

grant trigger on table "public"."community_registration_requests" to "authenticated";

grant truncate on table "public"."community_registration_requests" to "authenticated";

grant update on table "public"."community_registration_requests" to "authenticated";

grant delete on table "public"."community_registration_requests" to "service_role";

grant insert on table "public"."community_registration_requests" to "service_role";

grant references on table "public"."community_registration_requests" to "service_role";

grant select on table "public"."community_registration_requests" to "service_role";

grant trigger on table "public"."community_registration_requests" to "service_role";

grant truncate on table "public"."community_registration_requests" to "service_role";

grant update on table "public"."community_registration_requests" to "service_role";

grant delete on table "public"."community_settings" to "anon";

grant insert on table "public"."community_settings" to "anon";

grant select on table "public"."community_settings" to "anon";

grant update on table "public"."community_settings" to "anon";

grant delete on table "public"."community_settings" to "authenticated";

grant insert on table "public"."community_settings" to "authenticated";

grant update on table "public"."community_settings" to "authenticated";

grant delete on table "public"."complaint_categories" to "anon";

grant insert on table "public"."complaint_categories" to "anon";

grant select on table "public"."complaint_categories" to "anon";

grant update on table "public"."complaint_categories" to "anon";

grant delete on table "public"."complaint_categories" to "authenticated";

grant insert on table "public"."complaint_categories" to "authenticated";

grant update on table "public"."complaint_categories" to "authenticated";

grant delete on table "public"."complaint_comments" to "anon";

grant insert on table "public"."complaint_comments" to "anon";

grant select on table "public"."complaint_comments" to "anon";

grant update on table "public"."complaint_comments" to "anon";

grant delete on table "public"."complaint_comments" to "authenticated";

grant insert on table "public"."complaint_comments" to "authenticated";

grant update on table "public"."complaint_comments" to "authenticated";

grant delete on table "public"."complaint_department_requests" to "anon";

grant insert on table "public"."complaint_department_requests" to "anon";

grant select on table "public"."complaint_department_requests" to "anon";

grant update on table "public"."complaint_department_requests" to "anon";

grant delete on table "public"."complaint_department_requests" to "authenticated";

grant insert on table "public"."complaint_department_requests" to "authenticated";

grant update on table "public"."complaint_department_requests" to "authenticated";

grant delete on table "public"."complaint_events" to "anon";

grant insert on table "public"."complaint_events" to "anon";

grant select on table "public"."complaint_events" to "anon";

grant update on table "public"."complaint_events" to "anon";

grant delete on table "public"."complaint_events" to "authenticated";

grant insert on table "public"."complaint_events" to "authenticated";

grant update on table "public"."complaint_events" to "authenticated";

grant delete on table "public"."complaint_read_state" to "anon";

grant insert on table "public"."complaint_read_state" to "anon";

grant select on table "public"."complaint_read_state" to "anon";

grant update on table "public"."complaint_read_state" to "anon";

grant delete on table "public"."complaint_read_state" to "authenticated";

grant insert on table "public"."complaint_read_state" to "authenticated";

grant update on table "public"."complaint_read_state" to "authenticated";

grant delete on table "public"."complaints" to "anon";

grant insert on table "public"."complaints" to "anon";

grant select on table "public"."complaints" to "anon";

grant update on table "public"."complaints" to "anon";

grant delete on table "public"."complaints" to "authenticated";

grant insert on table "public"."complaints" to "authenticated";

grant update on table "public"."complaints" to "authenticated";

grant delete on table "public"."conversation_messages" to "anon";

grant insert on table "public"."conversation_messages" to "anon";

grant select on table "public"."conversation_messages" to "anon";

grant update on table "public"."conversation_messages" to "anon";

grant delete on table "public"."conversation_messages" to "authenticated";

grant insert on table "public"."conversation_messages" to "authenticated";

grant update on table "public"."conversation_messages" to "authenticated";

grant delete on table "public"."conversations" to "anon";

grant insert on table "public"."conversations" to "anon";

grant select on table "public"."conversations" to "anon";

grant update on table "public"."conversations" to "anon";

grant delete on table "public"."conversations" to "authenticated";

grant insert on table "public"."conversations" to "authenticated";

grant update on table "public"."conversations" to "authenticated";

grant delete on table "public"."department_categories" to "anon";

grant insert on table "public"."department_categories" to "anon";

grant select on table "public"."department_categories" to "anon";

grant update on table "public"."department_categories" to "anon";

grant delete on table "public"."department_categories" to "authenticated";

grant insert on table "public"."department_categories" to "authenticated";

grant update on table "public"."department_categories" to "authenticated";

grant delete on table "public"."department_skills" to "anon";

grant insert on table "public"."department_skills" to "anon";

grant select on table "public"."department_skills" to "anon";

grant update on table "public"."department_skills" to "anon";

grant delete on table "public"."department_skills" to "authenticated";

grant insert on table "public"."department_skills" to "authenticated";

grant update on table "public"."department_skills" to "authenticated";

grant delete on table "public"."departments" to "anon";

grant insert on table "public"."departments" to "anon";

grant select on table "public"."departments" to "anon";

grant update on table "public"."departments" to "anon";

grant delete on table "public"."departments" to "authenticated";

grant insert on table "public"."departments" to "authenticated";

grant update on table "public"."departments" to "authenticated";

grant delete on table "public"."dispatch_tasks" to "anon";

grant insert on table "public"."dispatch_tasks" to "anon";

grant select on table "public"."dispatch_tasks" to "anon";

grant update on table "public"."dispatch_tasks" to "anon";

grant delete on table "public"."dispatch_tasks" to "authenticated";

grant insert on table "public"."dispatch_tasks" to "authenticated";

grant update on table "public"."dispatch_tasks" to "authenticated";

grant delete on table "public"."dm_messages" to "anon";

grant insert on table "public"."dm_messages" to "anon";

grant select on table "public"."dm_messages" to "anon";

grant update on table "public"."dm_messages" to "anon";

grant delete on table "public"."dm_messages" to "authenticated";

grant insert on table "public"."dm_messages" to "authenticated";

grant update on table "public"."dm_messages" to "authenticated";

grant delete on table "public"."dm_threads" to "anon";

grant insert on table "public"."dm_threads" to "anon";

grant select on table "public"."dm_threads" to "anon";

grant update on table "public"."dm_threads" to "anon";

grant delete on table "public"."dm_threads" to "authenticated";

grant insert on table "public"."dm_threads" to "authenticated";

grant update on table "public"."dm_threads" to "authenticated";

grant delete on table "public"."feature_catalog" to "anon";

grant insert on table "public"."feature_catalog" to "anon";

grant select on table "public"."feature_catalog" to "anon";

grant update on table "public"."feature_catalog" to "anon";

grant delete on table "public"."feature_catalog" to "authenticated";

grant insert on table "public"."feature_catalog" to "authenticated";

grant select on table "public"."feature_catalog" to "authenticated";

grant update on table "public"."feature_catalog" to "authenticated";

grant delete on table "public"."invoice_line_items" to "anon";

grant insert on table "public"."invoice_line_items" to "anon";

grant select on table "public"."invoice_line_items" to "anon";

grant update on table "public"."invoice_line_items" to "anon";

grant delete on table "public"."invoice_line_items" to "authenticated";

grant insert on table "public"."invoice_line_items" to "authenticated";

grant update on table "public"."invoice_line_items" to "authenticated";

grant delete on table "public"."invoices" to "anon";

grant insert on table "public"."invoices" to "anon";

grant select on table "public"."invoices" to "anon";

grant update on table "public"."invoices" to "anon";

grant delete on table "public"."invoices" to "authenticated";

grant insert on table "public"."invoices" to "authenticated";

grant update on table "public"."invoices" to "authenticated";

grant delete on table "public"."legacy_amenity_booking_charges" to "anon";

grant insert on table "public"."legacy_amenity_booking_charges" to "anon";

grant references on table "public"."legacy_amenity_booking_charges" to "anon";

grant select on table "public"."legacy_amenity_booking_charges" to "anon";

grant trigger on table "public"."legacy_amenity_booking_charges" to "anon";

grant truncate on table "public"."legacy_amenity_booking_charges" to "anon";

grant update on table "public"."legacy_amenity_booking_charges" to "anon";

grant delete on table "public"."legacy_amenity_booking_charges" to "authenticated";

grant insert on table "public"."legacy_amenity_booking_charges" to "authenticated";

grant references on table "public"."legacy_amenity_booking_charges" to "authenticated";

grant select on table "public"."legacy_amenity_booking_charges" to "authenticated";

grant trigger on table "public"."legacy_amenity_booking_charges" to "authenticated";

grant truncate on table "public"."legacy_amenity_booking_charges" to "authenticated";

grant update on table "public"."legacy_amenity_booking_charges" to "authenticated";

grant delete on table "public"."legacy_amenity_booking_charges" to "service_role";

grant insert on table "public"."legacy_amenity_booking_charges" to "service_role";

grant references on table "public"."legacy_amenity_booking_charges" to "service_role";

grant select on table "public"."legacy_amenity_booking_charges" to "service_role";

grant trigger on table "public"."legacy_amenity_booking_charges" to "service_role";

grant truncate on table "public"."legacy_amenity_booking_charges" to "service_role";

grant update on table "public"."legacy_amenity_booking_charges" to "service_role";

grant delete on table "public"."legacy_amenity_booking_occurrences" to "anon";

grant insert on table "public"."legacy_amenity_booking_occurrences" to "anon";

grant references on table "public"."legacy_amenity_booking_occurrences" to "anon";

grant select on table "public"."legacy_amenity_booking_occurrences" to "anon";

grant trigger on table "public"."legacy_amenity_booking_occurrences" to "anon";

grant truncate on table "public"."legacy_amenity_booking_occurrences" to "anon";

grant update on table "public"."legacy_amenity_booking_occurrences" to "anon";

grant delete on table "public"."legacy_amenity_booking_occurrences" to "authenticated";

grant insert on table "public"."legacy_amenity_booking_occurrences" to "authenticated";

grant references on table "public"."legacy_amenity_booking_occurrences" to "authenticated";

grant select on table "public"."legacy_amenity_booking_occurrences" to "authenticated";

grant trigger on table "public"."legacy_amenity_booking_occurrences" to "authenticated";

grant truncate on table "public"."legacy_amenity_booking_occurrences" to "authenticated";

grant update on table "public"."legacy_amenity_booking_occurrences" to "authenticated";

grant delete on table "public"."legacy_amenity_booking_occurrences" to "service_role";

grant insert on table "public"."legacy_amenity_booking_occurrences" to "service_role";

grant references on table "public"."legacy_amenity_booking_occurrences" to "service_role";

grant select on table "public"."legacy_amenity_booking_occurrences" to "service_role";

grant trigger on table "public"."legacy_amenity_booking_occurrences" to "service_role";

grant truncate on table "public"."legacy_amenity_booking_occurrences" to "service_role";

grant update on table "public"."legacy_amenity_booking_occurrences" to "service_role";

grant delete on table "public"."legacy_amenity_booking_series" to "anon";

grant insert on table "public"."legacy_amenity_booking_series" to "anon";

grant references on table "public"."legacy_amenity_booking_series" to "anon";

grant select on table "public"."legacy_amenity_booking_series" to "anon";

grant trigger on table "public"."legacy_amenity_booking_series" to "anon";

grant truncate on table "public"."legacy_amenity_booking_series" to "anon";

grant update on table "public"."legacy_amenity_booking_series" to "anon";

grant delete on table "public"."legacy_amenity_booking_series" to "authenticated";

grant insert on table "public"."legacy_amenity_booking_series" to "authenticated";

grant references on table "public"."legacy_amenity_booking_series" to "authenticated";

grant select on table "public"."legacy_amenity_booking_series" to "authenticated";

grant trigger on table "public"."legacy_amenity_booking_series" to "authenticated";

grant truncate on table "public"."legacy_amenity_booking_series" to "authenticated";

grant update on table "public"."legacy_amenity_booking_series" to "authenticated";

grant delete on table "public"."legacy_amenity_booking_series" to "service_role";

grant insert on table "public"."legacy_amenity_booking_series" to "service_role";

grant references on table "public"."legacy_amenity_booking_series" to "service_role";

grant select on table "public"."legacy_amenity_booking_series" to "service_role";

grant trigger on table "public"."legacy_amenity_booking_series" to "service_role";

grant truncate on table "public"."legacy_amenity_booking_series" to "service_role";

grant update on table "public"."legacy_amenity_booking_series" to "service_role";

grant delete on table "public"."legacy_amenity_financial_events" to "anon";

grant insert on table "public"."legacy_amenity_financial_events" to "anon";

grant references on table "public"."legacy_amenity_financial_events" to "anon";

grant select on table "public"."legacy_amenity_financial_events" to "anon";

grant trigger on table "public"."legacy_amenity_financial_events" to "anon";

grant truncate on table "public"."legacy_amenity_financial_events" to "anon";

grant update on table "public"."legacy_amenity_financial_events" to "anon";

grant delete on table "public"."legacy_amenity_financial_events" to "authenticated";

grant insert on table "public"."legacy_amenity_financial_events" to "authenticated";

grant references on table "public"."legacy_amenity_financial_events" to "authenticated";

grant select on table "public"."legacy_amenity_financial_events" to "authenticated";

grant trigger on table "public"."legacy_amenity_financial_events" to "authenticated";

grant truncate on table "public"."legacy_amenity_financial_events" to "authenticated";

grant update on table "public"."legacy_amenity_financial_events" to "authenticated";

grant delete on table "public"."legacy_amenity_financial_events" to "service_role";

grant insert on table "public"."legacy_amenity_financial_events" to "service_role";

grant references on table "public"."legacy_amenity_financial_events" to "service_role";

grant select on table "public"."legacy_amenity_financial_events" to "service_role";

grant trigger on table "public"."legacy_amenity_financial_events" to "service_role";

grant truncate on table "public"."legacy_amenity_financial_events" to "service_role";

grant update on table "public"."legacy_amenity_financial_events" to "service_role";

grant delete on table "public"."legacy_notifications" to "anon";

grant insert on table "public"."legacy_notifications" to "anon";

grant references on table "public"."legacy_notifications" to "anon";

grant select on table "public"."legacy_notifications" to "anon";

grant trigger on table "public"."legacy_notifications" to "anon";

grant truncate on table "public"."legacy_notifications" to "anon";

grant update on table "public"."legacy_notifications" to "anon";

grant delete on table "public"."legacy_notifications" to "authenticated";

grant insert on table "public"."legacy_notifications" to "authenticated";

grant references on table "public"."legacy_notifications" to "authenticated";

grant select on table "public"."legacy_notifications" to "authenticated";

grant trigger on table "public"."legacy_notifications" to "authenticated";

grant truncate on table "public"."legacy_notifications" to "authenticated";

grant update on table "public"."legacy_notifications" to "authenticated";

grant delete on table "public"."legacy_notifications" to "service_role";

grant insert on table "public"."legacy_notifications" to "service_role";

grant references on table "public"."legacy_notifications" to "service_role";

grant select on table "public"."legacy_notifications" to "service_role";

grant trigger on table "public"."legacy_notifications" to "service_role";

grant truncate on table "public"."legacy_notifications" to "service_role";

grant update on table "public"."legacy_notifications" to "service_role";

grant delete on table "public"."legacy_visitor_events" to "anon";

grant insert on table "public"."legacy_visitor_events" to "anon";

grant references on table "public"."legacy_visitor_events" to "anon";

grant select on table "public"."legacy_visitor_events" to "anon";

grant trigger on table "public"."legacy_visitor_events" to "anon";

grant truncate on table "public"."legacy_visitor_events" to "anon";

grant update on table "public"."legacy_visitor_events" to "anon";

grant delete on table "public"."legacy_visitor_events" to "authenticated";

grant insert on table "public"."legacy_visitor_events" to "authenticated";

grant references on table "public"."legacy_visitor_events" to "authenticated";

grant select on table "public"."legacy_visitor_events" to "authenticated";

grant trigger on table "public"."legacy_visitor_events" to "authenticated";

grant truncate on table "public"."legacy_visitor_events" to "authenticated";

grant update on table "public"."legacy_visitor_events" to "authenticated";

grant delete on table "public"."legacy_visitor_events" to "service_role";

grant insert on table "public"."legacy_visitor_events" to "service_role";

grant references on table "public"."legacy_visitor_events" to "service_role";

grant select on table "public"."legacy_visitor_events" to "service_role";

grant trigger on table "public"."legacy_visitor_events" to "service_role";

grant truncate on table "public"."legacy_visitor_events" to "service_role";

grant update on table "public"."legacy_visitor_events" to "service_role";

grant delete on table "public"."material_movements" to "anon";

grant insert on table "public"."material_movements" to "anon";

grant select on table "public"."material_movements" to "anon";

grant update on table "public"."material_movements" to "anon";

grant delete on table "public"."material_movements" to "authenticated";

grant insert on table "public"."material_movements" to "authenticated";

grant update on table "public"."material_movements" to "authenticated";

grant delete on table "public"."media_assets" to "anon";

grant insert on table "public"."media_assets" to "anon";

grant references on table "public"."media_assets" to "anon";

grant select on table "public"."media_assets" to "anon";

grant trigger on table "public"."media_assets" to "anon";

grant truncate on table "public"."media_assets" to "anon";

grant update on table "public"."media_assets" to "anon";

grant delete on table "public"."media_assets" to "authenticated";

grant insert on table "public"."media_assets" to "authenticated";

grant references on table "public"."media_assets" to "authenticated";

grant select on table "public"."media_assets" to "authenticated";

grant trigger on table "public"."media_assets" to "authenticated";

grant truncate on table "public"."media_assets" to "authenticated";

grant update on table "public"."media_assets" to "authenticated";

grant delete on table "public"."media_assets" to "service_role";

grant insert on table "public"."media_assets" to "service_role";

grant references on table "public"."media_assets" to "service_role";

grant select on table "public"."media_assets" to "service_role";

grant trigger on table "public"."media_assets" to "service_role";

grant truncate on table "public"."media_assets" to "service_role";

grant update on table "public"."media_assets" to "service_role";

grant delete on table "public"."notices" to "anon";

grant insert on table "public"."notices" to "anon";

grant select on table "public"."notices" to "anon";

grant update on table "public"."notices" to "anon";

grant delete on table "public"."notices" to "authenticated";

grant insert on table "public"."notices" to "authenticated";

grant update on table "public"."notices" to "authenticated";

grant delete on table "public"."notification_deliveries" to "anon";

grant insert on table "public"."notification_deliveries" to "anon";

grant references on table "public"."notification_deliveries" to "anon";

grant select on table "public"."notification_deliveries" to "anon";

grant trigger on table "public"."notification_deliveries" to "anon";

grant truncate on table "public"."notification_deliveries" to "anon";

grant update on table "public"."notification_deliveries" to "anon";

grant delete on table "public"."notification_deliveries" to "authenticated";

grant insert on table "public"."notification_deliveries" to "authenticated";

grant references on table "public"."notification_deliveries" to "authenticated";

grant select on table "public"."notification_deliveries" to "authenticated";

grant trigger on table "public"."notification_deliveries" to "authenticated";

grant truncate on table "public"."notification_deliveries" to "authenticated";

grant update on table "public"."notification_deliveries" to "authenticated";

grant delete on table "public"."notification_deliveries" to "service_role";

grant insert on table "public"."notification_deliveries" to "service_role";

grant references on table "public"."notification_deliveries" to "service_role";

grant select on table "public"."notification_deliveries" to "service_role";

grant trigger on table "public"."notification_deliveries" to "service_role";

grant truncate on table "public"."notification_deliveries" to "service_role";

grant update on table "public"."notification_deliveries" to "service_role";

grant delete on table "public"."notifications" to "anon";

grant insert on table "public"."notifications" to "anon";

grant select on table "public"."notifications" to "anon";

grant update on table "public"."notifications" to "anon";

grant delete on table "public"."notifications" to "authenticated";

grant insert on table "public"."notifications" to "authenticated";

grant update on table "public"."notifications" to "authenticated";

grant delete on table "public"."offline_reconcile_log" to "anon";

grant insert on table "public"."offline_reconcile_log" to "anon";

grant select on table "public"."offline_reconcile_log" to "anon";

grant update on table "public"."offline_reconcile_log" to "anon";

grant delete on table "public"."offline_reconcile_log" to "authenticated";

grant insert on table "public"."offline_reconcile_log" to "authenticated";

grant update on table "public"."offline_reconcile_log" to "authenticated";

grant delete on table "public"."payment_events" to "anon";

grant insert on table "public"."payment_events" to "anon";

grant select on table "public"."payment_events" to "anon";

grant update on table "public"."payment_events" to "anon";

grant delete on table "public"."payment_events" to "authenticated";

grant insert on table "public"."payment_events" to "authenticated";

grant update on table "public"."payment_events" to "authenticated";

grant delete on table "public"."payments" to "anon";

grant insert on table "public"."payments" to "anon";

grant select on table "public"."payments" to "anon";

grant update on table "public"."payments" to "anon";

grant delete on table "public"."payments" to "authenticated";

grant insert on table "public"."payments" to "authenticated";

grant update on table "public"."payments" to "authenticated";

grant delete on table "public"."policies" to "anon";

grant insert on table "public"."policies" to "anon";

grant references on table "public"."policies" to "anon";

grant select on table "public"."policies" to "anon";

grant trigger on table "public"."policies" to "anon";

grant truncate on table "public"."policies" to "anon";

grant update on table "public"."policies" to "anon";

grant delete on table "public"."policies" to "authenticated";

grant insert on table "public"."policies" to "authenticated";

grant references on table "public"."policies" to "authenticated";

grant select on table "public"."policies" to "authenticated";

grant trigger on table "public"."policies" to "authenticated";

grant truncate on table "public"."policies" to "authenticated";

grant update on table "public"."policies" to "authenticated";

grant delete on table "public"."policies" to "service_role";

grant insert on table "public"."policies" to "service_role";

grant references on table "public"."policies" to "service_role";

grant select on table "public"."policies" to "service_role";

grant trigger on table "public"."policies" to "service_role";

grant truncate on table "public"."policies" to "service_role";

grant update on table "public"."policies" to "service_role";

grant delete on table "public"."policy_revisions" to "anon";

grant insert on table "public"."policy_revisions" to "anon";

grant references on table "public"."policy_revisions" to "anon";

grant select on table "public"."policy_revisions" to "anon";

grant trigger on table "public"."policy_revisions" to "anon";

grant truncate on table "public"."policy_revisions" to "anon";

grant update on table "public"."policy_revisions" to "anon";

grant delete on table "public"."policy_revisions" to "authenticated";

grant insert on table "public"."policy_revisions" to "authenticated";

grant references on table "public"."policy_revisions" to "authenticated";

grant select on table "public"."policy_revisions" to "authenticated";

grant trigger on table "public"."policy_revisions" to "authenticated";

grant truncate on table "public"."policy_revisions" to "authenticated";

grant update on table "public"."policy_revisions" to "authenticated";

grant delete on table "public"."policy_revisions" to "service_role";

grant insert on table "public"."policy_revisions" to "service_role";

grant references on table "public"."policy_revisions" to "service_role";

grant select on table "public"."policy_revisions" to "service_role";

grant trigger on table "public"."policy_revisions" to "service_role";

grant truncate on table "public"."policy_revisions" to "service_role";

grant update on table "public"."policy_revisions" to "service_role";

grant delete on table "public"."profiles" to "anon";

grant insert on table "public"."profiles" to "anon";

grant select on table "public"."profiles" to "anon";

grant update on table "public"."profiles" to "anon";

grant delete on table "public"."profiles" to "authenticated";

grant insert on table "public"."profiles" to "authenticated";

grant update on table "public"."profiles" to "authenticated";

grant select on table "public"."profiles" to "supabase_auth_admin";

grant delete on table "public"."push_subscriptions" to "anon";

grant insert on table "public"."push_subscriptions" to "anon";

grant select on table "public"."push_subscriptions" to "anon";

grant update on table "public"."push_subscriptions" to "anon";

grant delete on table "public"."push_subscriptions" to "authenticated";

grant insert on table "public"."push_subscriptions" to "authenticated";

grant update on table "public"."push_subscriptions" to "authenticated";

grant delete on table "public"."resident_invites" to "anon";

grant insert on table "public"."resident_invites" to "anon";

grant select on table "public"."resident_invites" to "anon";

grant update on table "public"."resident_invites" to "anon";

grant delete on table "public"."resident_invites" to "authenticated";

grant insert on table "public"."resident_invites" to "authenticated";

grant update on table "public"."resident_invites" to "authenticated";

grant delete on table "public"."saved_visitors" to "anon";

grant insert on table "public"."saved_visitors" to "anon";

grant references on table "public"."saved_visitors" to "anon";

grant select on table "public"."saved_visitors" to "anon";

grant trigger on table "public"."saved_visitors" to "anon";

grant truncate on table "public"."saved_visitors" to "anon";

grant update on table "public"."saved_visitors" to "anon";

grant delete on table "public"."saved_visitors" to "authenticated";

grant insert on table "public"."saved_visitors" to "authenticated";

grant references on table "public"."saved_visitors" to "authenticated";

grant select on table "public"."saved_visitors" to "authenticated";

grant trigger on table "public"."saved_visitors" to "authenticated";

grant truncate on table "public"."saved_visitors" to "authenticated";

grant update on table "public"."saved_visitors" to "authenticated";

grant delete on table "public"."saved_visitors" to "service_role";

grant insert on table "public"."saved_visitors" to "service_role";

grant references on table "public"."saved_visitors" to "service_role";

grant select on table "public"."saved_visitors" to "service_role";

grant trigger on table "public"."saved_visitors" to "service_role";

grant truncate on table "public"."saved_visitors" to "service_role";

grant update on table "public"."saved_visitors" to "service_role";

grant delete on table "public"."security_incidents" to "anon";

grant insert on table "public"."security_incidents" to "anon";

grant select on table "public"."security_incidents" to "anon";

grant update on table "public"."security_incidents" to "anon";

grant delete on table "public"."security_incidents" to "authenticated";

grant insert on table "public"."security_incidents" to "authenticated";

grant update on table "public"."security_incidents" to "authenticated";

grant delete on table "public"."security_posts" to "anon";

grant insert on table "public"."security_posts" to "anon";

grant select on table "public"."security_posts" to "anon";

grant update on table "public"."security_posts" to "anon";

grant delete on table "public"."security_posts" to "authenticated";

grant insert on table "public"."security_posts" to "authenticated";

grant update on table "public"."security_posts" to "authenticated";

grant delete on table "public"."security_shifts" to "anon";

grant insert on table "public"."security_shifts" to "anon";

grant select on table "public"."security_shifts" to "anon";

grant update on table "public"."security_shifts" to "anon";

grant delete on table "public"."security_shifts" to "authenticated";

grant insert on table "public"."security_shifts" to "authenticated";

grant update on table "public"."security_shifts" to "authenticated";

grant delete on table "public"."service_applications" to "anon";

grant insert on table "public"."service_applications" to "anon";

grant select on table "public"."service_applications" to "anon";

grant update on table "public"."service_applications" to "anon";

grant delete on table "public"."service_applications" to "authenticated";

grant insert on table "public"."service_applications" to "authenticated";

grant update on table "public"."service_applications" to "authenticated";

grant delete on table "public"."service_provider_skills" to "anon";

grant insert on table "public"."service_provider_skills" to "anon";

grant select on table "public"."service_provider_skills" to "anon";

grant update on table "public"."service_provider_skills" to "anon";

grant delete on table "public"."service_provider_skills" to "authenticated";

grant insert on table "public"."service_provider_skills" to "authenticated";

grant update on table "public"."service_provider_skills" to "authenticated";

grant delete on table "public"."service_providers" to "anon";

grant insert on table "public"."service_providers" to "anon";

grant select on table "public"."service_providers" to "anon";

grant update on table "public"."service_providers" to "anon";

grant delete on table "public"."service_providers" to "authenticated";

grant insert on table "public"."service_providers" to "authenticated";

grant update on table "public"."service_providers" to "authenticated";

grant delete on table "public"."skills" to "anon";

grant insert on table "public"."skills" to "anon";

grant select on table "public"."skills" to "anon";

grant update on table "public"."skills" to "anon";

grant delete on table "public"."skills" to "authenticated";

grant insert on table "public"."skills" to "authenticated";

grant update on table "public"."skills" to "authenticated";

grant delete on table "public"."sse_events" to "anon";

grant insert on table "public"."sse_events" to "anon";

grant select on table "public"."sse_events" to "anon";

grant update on table "public"."sse_events" to "anon";

grant delete on table "public"."sse_events" to "authenticated";

grant insert on table "public"."sse_events" to "authenticated";

grant update on table "public"."sse_events" to "authenticated";

grant delete on table "public"."staff_assignments" to "anon";

grant insert on table "public"."staff_assignments" to "anon";

grant select on table "public"."staff_assignments" to "anon";

grant update on table "public"."staff_assignments" to "anon";

grant delete on table "public"."staff_assignments" to "authenticated";

grant delete on table "public"."staff_departures" to "anon";

grant insert on table "public"."staff_departures" to "anon";

grant select on table "public"."staff_departures" to "anon";

grant update on table "public"."staff_departures" to "anon";

grant delete on table "public"."staff_departures" to "authenticated";

grant insert on table "public"."staff_departures" to "authenticated";

grant update on table "public"."staff_departures" to "authenticated";

grant delete on table "public"."staff_invitations" to "anon";

grant insert on table "public"."staff_invitations" to "anon";

grant select on table "public"."staff_invitations" to "anon";

grant update on table "public"."staff_invitations" to "anon";

grant delete on table "public"."staff_invitations" to "authenticated";

grant insert on table "public"."staff_invitations" to "authenticated";

grant update on table "public"."staff_invitations" to "authenticated";

grant delete on table "public"."unit_contacts" to "anon";

grant insert on table "public"."unit_contacts" to "anon";

grant select on table "public"."unit_contacts" to "anon";

grant update on table "public"."unit_contacts" to "anon";

grant delete on table "public"."unit_contacts" to "authenticated";

grant insert on table "public"."unit_contacts" to "authenticated";

grant update on table "public"."unit_contacts" to "authenticated";

grant delete on table "public"."unit_residencies" to "anon";

grant insert on table "public"."unit_residencies" to "anon";

grant select on table "public"."unit_residencies" to "anon";

grant update on table "public"."unit_residencies" to "anon";

grant delete on table "public"."unit_residencies" to "authenticated";

grant insert on table "public"."unit_residencies" to "authenticated";

grant update on table "public"."unit_residencies" to "authenticated";

grant delete on table "public"."units" to "anon";

grant insert on table "public"."units" to "anon";

grant select on table "public"."units" to "anon";

grant update on table "public"."units" to "anon";

grant delete on table "public"."units" to "authenticated";

grant insert on table "public"."units" to "authenticated";

grant update on table "public"."units" to "authenticated";

grant delete on table "public"."visitor_access_requests" to "anon";

grant insert on table "public"."visitor_access_requests" to "anon";

grant references on table "public"."visitor_access_requests" to "anon";

grant select on table "public"."visitor_access_requests" to "anon";

grant trigger on table "public"."visitor_access_requests" to "anon";

grant truncate on table "public"."visitor_access_requests" to "anon";

grant update on table "public"."visitor_access_requests" to "anon";

grant delete on table "public"."visitor_access_requests" to "authenticated";

grant insert on table "public"."visitor_access_requests" to "authenticated";

grant references on table "public"."visitor_access_requests" to "authenticated";

grant select on table "public"."visitor_access_requests" to "authenticated";

grant trigger on table "public"."visitor_access_requests" to "authenticated";

grant truncate on table "public"."visitor_access_requests" to "authenticated";

grant update on table "public"."visitor_access_requests" to "authenticated";

grant delete on table "public"."visitor_access_requests" to "service_role";

grant insert on table "public"."visitor_access_requests" to "service_role";

grant references on table "public"."visitor_access_requests" to "service_role";

grant select on table "public"."visitor_access_requests" to "service_role";

grant trigger on table "public"."visitor_access_requests" to "service_role";

grant truncate on table "public"."visitor_access_requests" to "service_role";

grant update on table "public"."visitor_access_requests" to "service_role";

grant delete on table "public"."visitor_attachments" to "anon";

grant insert on table "public"."visitor_attachments" to "anon";

grant references on table "public"."visitor_attachments" to "anon";

grant select on table "public"."visitor_attachments" to "anon";

grant trigger on table "public"."visitor_attachments" to "anon";

grant truncate on table "public"."visitor_attachments" to "anon";

grant update on table "public"."visitor_attachments" to "anon";

grant delete on table "public"."visitor_attachments" to "authenticated";

grant insert on table "public"."visitor_attachments" to "authenticated";

grant references on table "public"."visitor_attachments" to "authenticated";

grant select on table "public"."visitor_attachments" to "authenticated";

grant trigger on table "public"."visitor_attachments" to "authenticated";

grant truncate on table "public"."visitor_attachments" to "authenticated";

grant update on table "public"."visitor_attachments" to "authenticated";

grant delete on table "public"."visitor_attachments" to "service_role";

grant insert on table "public"."visitor_attachments" to "service_role";

grant references on table "public"."visitor_attachments" to "service_role";

grant select on table "public"."visitor_attachments" to "service_role";

grant trigger on table "public"."visitor_attachments" to "service_role";

grant truncate on table "public"."visitor_attachments" to "service_role";

grant update on table "public"."visitor_attachments" to "service_role";

grant delete on table "public"."visitor_events" to "anon";

grant insert on table "public"."visitor_events" to "anon";

grant select on table "public"."visitor_events" to "anon";

grant update on table "public"."visitor_events" to "anon";

grant delete on table "public"."visitor_events" to "authenticated";

grant insert on table "public"."visitor_events" to "authenticated";

grant update on table "public"."visitor_events" to "authenticated";

grant delete on table "public"."visitor_requests" to "anon";

grant insert on table "public"."visitor_requests" to "anon";

grant select on table "public"."visitor_requests" to "anon";

grant update on table "public"."visitor_requests" to "anon";

grant delete on table "public"."visitor_requests" to "authenticated";

grant insert on table "public"."visitor_requests" to "authenticated";

grant update on table "public"."visitor_requests" to "authenticated";

grant delete on table "public"."water_tanker_logs" to "anon";

grant insert on table "public"."water_tanker_logs" to "anon";

grant select on table "public"."water_tanker_logs" to "anon";

grant update on table "public"."water_tanker_logs" to "anon";

grant delete on table "public"."water_tanker_logs" to "authenticated";

grant insert on table "public"."water_tanker_logs" to "authenticated";

grant update on table "public"."water_tanker_logs" to "authenticated";

grant delete on table "public"."work_order_assignments" to "anon";

grant insert on table "public"."work_order_assignments" to "anon";

grant select on table "public"."work_order_assignments" to "anon";

grant update on table "public"."work_order_assignments" to "anon";

grant delete on table "public"."work_order_assignments" to "authenticated";

grant insert on table "public"."work_order_assignments" to "authenticated";

grant update on table "public"."work_order_assignments" to "authenticated";

grant delete on table "public"."work_order_attachments" to "anon";

grant insert on table "public"."work_order_attachments" to "anon";

grant references on table "public"."work_order_attachments" to "anon";

grant select on table "public"."work_order_attachments" to "anon";

grant trigger on table "public"."work_order_attachments" to "anon";

grant truncate on table "public"."work_order_attachments" to "anon";

grant update on table "public"."work_order_attachments" to "anon";

grant delete on table "public"."work_order_attachments" to "authenticated";

grant insert on table "public"."work_order_attachments" to "authenticated";

grant references on table "public"."work_order_attachments" to "authenticated";

grant select on table "public"."work_order_attachments" to "authenticated";

grant trigger on table "public"."work_order_attachments" to "authenticated";

grant truncate on table "public"."work_order_attachments" to "authenticated";

grant update on table "public"."work_order_attachments" to "authenticated";

grant delete on table "public"."work_order_attachments" to "service_role";

grant insert on table "public"."work_order_attachments" to "service_role";

grant references on table "public"."work_order_attachments" to "service_role";

grant select on table "public"."work_order_attachments" to "service_role";

grant trigger on table "public"."work_order_attachments" to "service_role";

grant truncate on table "public"."work_order_attachments" to "service_role";

grant update on table "public"."work_order_attachments" to "service_role";

grant delete on table "public"."work_order_completion_verifications" to "anon";

grant insert on table "public"."work_order_completion_verifications" to "anon";

grant references on table "public"."work_order_completion_verifications" to "anon";

grant select on table "public"."work_order_completion_verifications" to "anon";

grant trigger on table "public"."work_order_completion_verifications" to "anon";

grant truncate on table "public"."work_order_completion_verifications" to "anon";

grant update on table "public"."work_order_completion_verifications" to "anon";

grant delete on table "public"."work_order_completion_verifications" to "authenticated";

grant insert on table "public"."work_order_completion_verifications" to "authenticated";

grant references on table "public"."work_order_completion_verifications" to "authenticated";

grant select on table "public"."work_order_completion_verifications" to "authenticated";

grant trigger on table "public"."work_order_completion_verifications" to "authenticated";

grant truncate on table "public"."work_order_completion_verifications" to "authenticated";

grant update on table "public"."work_order_completion_verifications" to "authenticated";

grant delete on table "public"."work_order_completion_verifications" to "service_role";

grant insert on table "public"."work_order_completion_verifications" to "service_role";

grant references on table "public"."work_order_completion_verifications" to "service_role";

grant select on table "public"."work_order_completion_verifications" to "service_role";

grant trigger on table "public"."work_order_completion_verifications" to "service_role";

grant truncate on table "public"."work_order_completion_verifications" to "service_role";

grant update on table "public"."work_order_completion_verifications" to "service_role";

grant delete on table "public"."work_order_proposals" to "anon";

grant insert on table "public"."work_order_proposals" to "anon";

grant references on table "public"."work_order_proposals" to "anon";

grant select on table "public"."work_order_proposals" to "anon";

grant trigger on table "public"."work_order_proposals" to "anon";

grant truncate on table "public"."work_order_proposals" to "anon";

grant update on table "public"."work_order_proposals" to "anon";

grant delete on table "public"."work_order_proposals" to "authenticated";

grant insert on table "public"."work_order_proposals" to "authenticated";

grant references on table "public"."work_order_proposals" to "authenticated";

grant select on table "public"."work_order_proposals" to "authenticated";

grant trigger on table "public"."work_order_proposals" to "authenticated";

grant truncate on table "public"."work_order_proposals" to "authenticated";

grant update on table "public"."work_order_proposals" to "authenticated";

grant delete on table "public"."work_order_proposals" to "service_role";

grant insert on table "public"."work_order_proposals" to "service_role";

grant references on table "public"."work_order_proposals" to "service_role";

grant select on table "public"."work_order_proposals" to "service_role";

grant trigger on table "public"."work_order_proposals" to "service_role";

grant truncate on table "public"."work_order_proposals" to "service_role";

grant update on table "public"."work_order_proposals" to "service_role";

grant delete on table "public"."work_order_views" to "anon";

grant insert on table "public"."work_order_views" to "anon";

grant references on table "public"."work_order_views" to "anon";

grant select on table "public"."work_order_views" to "anon";

grant trigger on table "public"."work_order_views" to "anon";

grant truncate on table "public"."work_order_views" to "anon";

grant update on table "public"."work_order_views" to "anon";

grant delete on table "public"."work_order_views" to "authenticated";

grant insert on table "public"."work_order_views" to "authenticated";

grant references on table "public"."work_order_views" to "authenticated";

grant select on table "public"."work_order_views" to "authenticated";

grant trigger on table "public"."work_order_views" to "authenticated";

grant truncate on table "public"."work_order_views" to "authenticated";

grant update on table "public"."work_order_views" to "authenticated";

grant delete on table "public"."work_order_views" to "service_role";

grant insert on table "public"."work_order_views" to "service_role";

grant references on table "public"."work_order_views" to "service_role";

grant select on table "public"."work_order_views" to "service_role";

grant trigger on table "public"."work_order_views" to "service_role";

grant truncate on table "public"."work_order_views" to "service_role";

grant update on table "public"."work_order_views" to "service_role";

grant delete on table "public"."work_orders" to "anon";

grant insert on table "public"."work_orders" to "anon";

grant select on table "public"."work_orders" to "anon";

grant update on table "public"."work_orders" to "anon";

grant delete on table "public"."work_orders" to "authenticated";

grant insert on table "public"."work_orders" to "authenticated";

grant update on table "public"."work_orders" to "authenticated";

grant delete on table "public"."worker_availability_rules" to "anon";

grant insert on table "public"."worker_availability_rules" to "anon";

grant select on table "public"."worker_availability_rules" to "anon";

grant update on table "public"."worker_availability_rules" to "anon";

grant delete on table "public"."worker_availability_rules" to "authenticated";

grant insert on table "public"."worker_availability_rules" to "authenticated";

grant update on table "public"."worker_availability_rules" to "authenticated";

grant delete on table "public"."worker_unavailability" to "anon";

grant insert on table "public"."worker_unavailability" to "anon";

grant select on table "public"."worker_unavailability" to "anon";

grant update on table "public"."worker_unavailability" to "anon";

grant delete on table "public"."worker_unavailability" to "authenticated";

grant insert on table "public"."worker_unavailability" to "authenticated";

grant update on table "public"."worker_unavailability" to "authenticated";


  create policy "access_requests_select_admin"
  on "public"."access_requests"
  as permissive
  for select
  to public
using (public.current_user_has_community_role(community_id, ARRAY['admin'::public.membership_role]));



  create policy "amenities_select_member"
  on "public"."amenities"
  as permissive
  for select
  to public
using (public.current_user_is_active_member(community_id));



  create policy "amenity_rules_select_member"
  on "public"."amenity_rules"
  as permissive
  for select
  to public
using ((EXISTS ( SELECT 1
   FROM public.amenities a
  WHERE ((a.id = amenity_rules.amenity_id) AND public.current_user_is_active_member(a.community_id)))));



  create policy "audit_events_select_manager_or_admin"
  on "public"."audit_events"
  as permissive
  for select
  to public
using (public.current_user_has_community_role(community_id, ARRAY['manager'::public.membership_role, 'admin'::public.membership_role]));



  create policy "booking_guests_select_authorized"
  on "public"."booking_guests"
  as permissive
  for select
  to public
using (public.current_user_can_access_booking(booking_occurrence_id));



  create policy "buildings_select_member"
  on "public"."buildings"
  as permissive
  for select
  to public
using (public.current_user_is_active_member(community_id));



  create policy "communities_select_member"
  on "public"."communities"
  as permissive
  for select
  to public
using (public.current_user_is_active_member(id));



  create policy "admin_terms_select_member"
  on "public"."community_admin_terms"
  as permissive
  for select
  to public
using (public.current_user_is_active_member(community_id));



  create policy "community_features_select_member"
  on "public"."community_features"
  as permissive
  for select
  to public
using (public.current_user_is_active_member(community_id));



  create policy "memberships_select_same_community"
  on "public"."community_memberships"
  as permissive
  for select
  to public
using (public.current_user_is_active_member(community_id));



  create policy "registration_requests_select_admin"
  on "public"."community_registration_requests"
  as permissive
  for select
  to public
using (((approved_community_id IS NOT NULL) AND public.current_user_has_community_role(approved_community_id, ARRAY['admin'::public.membership_role])));



  create policy "complaint_events_select_authorized"
  on "public"."complaint_events"
  as permissive
  for select
  to public
using (public.current_user_can_access_complaint(complaint_id));



  create policy "complaints_insert_resident"
  on "public"."complaints"
  as permissive
  for insert
  to public
with check ((public.current_user_owns_membership(raised_by_membership_id, community_id) AND public.current_user_has_community_role(community_id, ARRAY['resident'::public.membership_role, 'admin'::public.membership_role])));



  create policy "complaints_select_authorized"
  on "public"."complaints"
  as permissive
  for select
  to public
using (public.current_user_can_access_complaint(id));



  create policy "departments_select_member"
  on "public"."departments"
  as permissive
  for select
  to public
using (public.current_user_is_active_member(community_id));



  create policy "feature_catalog_select_authenticated"
  on "public"."feature_catalog"
  as permissive
  for select
  to authenticated
using (is_active);



  create policy "invoice_items_select_authorized"
  on "public"."invoice_line_items"
  as permissive
  for select
  to public
using (public.current_user_can_access_invoice(invoice_id));



  create policy "invoices_select_authorized"
  on "public"."invoices"
  as permissive
  for select
  to public
using (public.current_user_can_access_invoice(id));



  create policy "booking_charges_select_authorized"
  on "public"."legacy_amenity_booking_charges"
  as permissive
  for select
  to public
using (public.current_user_can_access_booking(booking_occurrence_id));



  create policy "booking_occurrences_select_authorized"
  on "public"."legacy_amenity_booking_occurrences"
  as permissive
  for select
  to public
using (public.current_user_can_access_booking(id));



  create policy "booking_series_insert_resident"
  on "public"."legacy_amenity_booking_series"
  as permissive
  for insert
  to public
with check ((public.current_user_owns_membership(booked_by_membership_id, community_id) AND public.current_user_is_active_unit_resident(liable_unit_id)));



  create policy "booking_series_select_authorized"
  on "public"."legacy_amenity_booking_series"
  as permissive
  for select
  to public
using ((public.current_user_owns_membership(booked_by_membership_id, community_id) OR public.current_user_has_community_role(community_id, ARRAY['manager'::public.membership_role, 'admin'::public.membership_role])));



  create policy "amenity_events_select_authorized"
  on "public"."legacy_amenity_financial_events"
  as permissive
  for select
  to public
using (public.current_user_can_access_booking(booking_occurrence_id));



  create policy "notifications_mark_read"
  on "public"."legacy_notifications"
  as permissive
  for update
  to public
using (public.current_user_owns_membership(recipient_membership_id, community_id))
with check (public.current_user_owns_membership(recipient_membership_id, community_id));



  create policy "notifications_select_recipient"
  on "public"."legacy_notifications"
  as permissive
  for select
  to public
using (public.current_user_owns_membership(recipient_membership_id, community_id));



  create policy "visitor_events_select_authorized"
  on "public"."legacy_visitor_events"
  as permissive
  for select
  to public
using (public.current_user_can_access_visitor(visitor_access_request_id));



  create policy "media_assets_select_manager_or_admin"
  on "public"."media_assets"
  as permissive
  for select
  to public
using (public.current_user_has_community_role(community_id, ARRAY['manager'::public.membership_role, 'admin'::public.membership_role]));



  create policy "notices_select_member"
  on "public"."notices"
  as permissive
  for select
  to public
using ((public.current_user_is_active_member(community_id) AND ((audience_role IS NULL) OR public.current_user_has_community_role(community_id, ARRAY[audience_role]))));



  create policy "deliveries_select_recipient"
  on "public"."notification_deliveries"
  as permissive
  for select
  to public
using ((EXISTS ( SELECT 1
   FROM public.legacy_notifications n
  WHERE ((n.id = notification_deliveries.notification_id) AND public.current_user_owns_membership(n.recipient_membership_id, n.community_id)))));



  create policy "payment_events_select_authorized"
  on "public"."payment_events"
  as permissive
  for select
  to public
using ((EXISTS ( SELECT 1
   FROM public.payments p
  WHERE ((p.id = payment_events.payment_id) AND public.current_user_can_access_invoice(p.invoice_id)))));



  create policy "payments_select_authorized"
  on "public"."payments"
  as permissive
  for select
  to public
using (public.current_user_can_access_invoice(invoice_id));



  create policy "policies_select_manager_or_admin"
  on "public"."policies"
  as permissive
  for select
  to public
using (public.current_user_has_community_role(community_id, ARRAY['manager'::public.membership_role, 'admin'::public.membership_role]));



  create policy "policy_revisions_select_manager_or_admin"
  on "public"."policy_revisions"
  as permissive
  for select
  to public
using ((EXISTS ( SELECT 1
   FROM public.policies p
  WHERE ((p.id = policy_revisions.policy_id) AND public.current_user_has_community_role(p.community_id, ARRAY['manager'::public.membership_role, 'admin'::public.membership_role])))));



  create policy "profiles_select_self"
  on "public"."profiles"
  as permissive
  for select
  to public
using ((id = auth.uid()));



  create policy "resident_invites_select_admin"
  on "public"."resident_invites"
  as permissive
  for select
  to public
using (public.current_user_has_community_role(community_id, ARRAY['admin'::public.membership_role]));



  create policy "saved_visitors_select_owner"
  on "public"."saved_visitors"
  as permissive
  for select
  to public
using (public.current_user_owns_membership(created_by_membership_id, community_id));



  create policy "skills_select_authenticated"
  on "public"."skills"
  as permissive
  for select
  to authenticated
using (true);



  create policy "staff_assignments_select_member"
  on "public"."staff_assignments"
  as permissive
  for select
  to public
using ((EXISTS ( SELECT 1
   FROM public.community_memberships cm
  WHERE ((cm.id = staff_assignments.membership_id) AND public.current_user_is_active_member(cm.community_id)))));



  create policy "unit_residencies_select_member"
  on "public"."unit_residencies"
  as permissive
  for select
  to public
using ((EXISTS ( SELECT 1
   FROM public.units u
  WHERE ((u.id = unit_residencies.unit_id) AND public.current_user_is_active_member(u.community_id)))));



  create policy "units_select_member"
  on "public"."units"
  as permissive
  for select
  to public
using (public.current_user_is_active_member(community_id));



  create policy "visitor_requests_insert_resident"
  on "public"."visitor_access_requests"
  as permissive
  for insert
  to public
with check ((public.current_user_owns_membership(requested_by_membership_id, community_id) AND public.current_user_is_active_unit_resident(unit_id)));



  create policy "visitor_requests_select_authorized"
  on "public"."visitor_access_requests"
  as permissive
  for select
  to public
using (public.current_user_can_access_visitor(id));



  create policy "visitor_attachments_select_authorized"
  on "public"."visitor_attachments"
  as permissive
  for select
  to public
using (public.current_user_can_access_visitor(visitor_access_request_id));



  create policy "work_order_assignments_select_authorized"
  on "public"."work_order_assignments"
  as permissive
  for select
  to public
using (public.current_user_can_access_work_order(work_order_id));



  create policy "work_order_attachments_select_authorized"
  on "public"."work_order_attachments"
  as permissive
  for select
  to public
using (public.current_user_can_access_work_order(work_order_id));



  create policy "work_order_verifications_select_authorized"
  on "public"."work_order_completion_verifications"
  as permissive
  for select
  to public
using (public.current_user_can_access_work_order(work_order_id));



  create policy "work_order_proposals_select_authorized"
  on "public"."work_order_proposals"
  as permissive
  for select
  to public
using (public.current_user_can_access_work_order(work_order_id));



  create policy "work_order_views_select_authorized"
  on "public"."work_order_views"
  as permissive
  for select
  to public
using (public.current_user_can_access_work_order(work_order_id));



  create policy "work_orders_select_authorized"
  on "public"."work_orders"
  as permissive
  for select
  to public
using (public.current_user_can_access_work_order(id));



  create policy "availability_select_self_or_manager"
  on "public"."worker_availability_rules"
  as permissive
  for select
  to public
using ((EXISTS ( SELECT 1
   FROM (public.staff_assignments sa
     JOIN public.community_memberships cm ON ((cm.id = sa.membership_id)))
  WHERE ((sa.id = worker_availability_rules.staff_assignment_id) AND ((cm.profile_id = auth.uid()) OR public.current_user_has_community_role(cm.community_id, ARRAY['manager'::public.membership_role, 'admin'::public.membership_role]))))));



  create policy "unavailability_select_self_or_manager"
  on "public"."worker_unavailability"
  as permissive
  for select
  to public
using ((EXISTS ( SELECT 1
   FROM (public.staff_assignments sa
     JOIN public.community_memberships cm ON ((cm.id = sa.membership_id)))
  WHERE ((sa.id = worker_unavailability.staff_assignment_id) AND ((cm.profile_id = auth.uid()) OR public.current_user_has_community_role(cm.community_id, ARRAY['manager'::public.membership_role, 'admin'::public.membership_role]))))));



  create policy "amenity_booking_charges_read"
  on "public"."amenity_booking_charges"
  as permissive
  for select
  to authenticated
using ((public.is_community_admin(community_id) OR public.is_own_booking(booking_occurrence_id)));



  create policy "amenity_booking_guests_read"
  on "public"."amenity_booking_guests"
  as permissive
  for select
  to authenticated
using (public.is_community_member(community_id));



  create policy "amenity_bookings_admin_write"
  on "public"."amenity_bookings"
  as permissive
  for all
  to authenticated
using (public.is_community_admin(community_id))
with check (public.is_community_admin(community_id));



  create policy "amenity_bookings_read"
  on "public"."amenity_bookings"
  as permissive
  for select
  to authenticated
using (public.is_community_member(community_id));



  create policy "amenity_financial_events_read"
  on "public"."amenity_financial_events"
  as permissive
  for select
  to authenticated
using ((public.is_community_admin(community_id) OR (EXISTS ( SELECT 1
   FROM public.amenity_booking_charges ch
  WHERE ((ch.id = amenity_financial_events.booking_charge_id) AND public.is_own_booking(ch.booking_occurrence_id))))));



  create policy "blacklisted_providers_read"
  on "public"."blacklisted_service_providers"
  as permissive
  for select
  to authenticated
using ((public.is_community_admin(community_id) OR (EXISTS ( SELECT 1
   FROM public.community_memberships m
  WHERE ((m.community_id = blacklisted_service_providers.community_id) AND (m.profile_id = auth.uid()) AND (m.role = 'manager'::public.membership_role) AND (m.status = 'active'::public.membership_status) AND (m.ended_at IS NULL))))));



  create policy "communities_service_application_read"
  on "public"."communities"
  as permissive
  for select
  to authenticated
using ((EXISTS ( SELECT 1
   FROM (public.service_applications a
     JOIN public.service_providers p ON ((p.id = a.service_provider_id)))
  WHERE ((a.community_id = communities.id) AND (p.profile_id = auth.uid())))));



  create policy "billing_settings_admin_write"
  on "public"."community_billing_settings"
  as permissive
  for all
  to public
using ((EXISTS ( SELECT 1
   FROM public.community_memberships m
  WHERE ((m.community_id = community_billing_settings.community_id) AND (m.profile_id = auth.uid()) AND (m.role = 'admin'::public.membership_role) AND (m.status = 'active'::public.membership_status) AND (m.ended_at IS NULL)))))
with check ((EXISTS ( SELECT 1
   FROM public.community_memberships m
  WHERE ((m.community_id = community_billing_settings.community_id) AND (m.profile_id = auth.uid()) AND (m.role = 'admin'::public.membership_role) AND (m.status = 'active'::public.membership_status) AND (m.ended_at IS NULL)))));



  create policy "billing_settings_member_read"
  on "public"."community_billing_settings"
  as permissive
  for select
  to public
using ((EXISTS ( SELECT 1
   FROM public.community_memberships m
  WHERE ((m.community_id = community_billing_settings.community_id) AND (m.profile_id = auth.uid()) AND (m.status = 'active'::public.membership_status) AND (m.ended_at IS NULL)))));



  create policy "community_settings_admin_write"
  on "public"."community_settings"
  as permissive
  for all
  to public
using ((EXISTS ( SELECT 1
   FROM public.community_memberships m
  WHERE ((m.community_id = community_settings.community_id) AND (m.profile_id = auth.uid()) AND (m.role = 'admin'::public.membership_role) AND (m.status = 'active'::public.membership_status) AND (m.ended_at IS NULL)))))
with check ((EXISTS ( SELECT 1
   FROM public.community_memberships m
  WHERE ((m.community_id = community_settings.community_id) AND (m.profile_id = auth.uid()) AND (m.role = 'admin'::public.membership_role) AND (m.status = 'active'::public.membership_status) AND (m.ended_at IS NULL)))));



  create policy "community_settings_member_read"
  on "public"."community_settings"
  as permissive
  for select
  to public
using ((EXISTS ( SELECT 1
   FROM public.community_memberships m
  WHERE ((m.community_id = community_settings.community_id) AND (m.profile_id = auth.uid()) AND (m.status = 'active'::public.membership_status) AND (m.ended_at IS NULL)))));



  create policy "complaint_categories_read"
  on "public"."complaint_categories"
  as permissive
  for select
  to authenticated
using (public.is_community_member(community_id));



  create policy "complaint_categories_write"
  on "public"."complaint_categories"
  as permissive
  for all
  to authenticated
using (public.is_community_admin(community_id))
with check (public.is_community_admin(community_id));



  create policy "complaint_comments_read"
  on "public"."complaint_comments"
  as permissive
  for select
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.complaints c
  WHERE ((c.id = complaint_comments.complaint_id) AND (public.is_community_admin(c.community_id) OR public.is_own_membership(c.raised_by_membership_id)) AND ((complaint_comments.visibility = 'public'::text) OR public.is_community_admin(c.community_id))))));



  create policy "complaint_department_requests_read"
  on "public"."complaint_department_requests"
  as permissive
  for select
  to public
using (public.can_supervise_department(from_department_id));



  create policy "complaint_events_read"
  on "public"."complaint_events"
  as permissive
  for select
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.complaints c
  WHERE ((c.id = complaint_events.complaint_id) AND (public.is_community_admin(c.community_id) OR public.is_own_membership(c.raised_by_membership_id))))));



  create policy "complaint_read_state_read"
  on "public"."complaint_read_state"
  as permissive
  for select
  to authenticated
using (public.is_own_membership(membership_id));



  create policy "complaints_read"
  on "public"."complaints"
  as permissive
  for select
  to authenticated
using ((public.is_community_admin(community_id) OR public.is_own_membership(raised_by_membership_id)));



  create policy "conversation_messages_read"
  on "public"."conversation_messages"
  as permissive
  for select
  to authenticated
using (public.is_conversation_participant(conversation_id));



  create policy "conversations_read"
  on "public"."conversations"
  as permissive
  for select
  to authenticated
using ((public.can_manage_department(department_id) OR (EXISTS ( SELECT 1
   FROM public.service_providers p
  WHERE ((p.id = conversations.service_provider_id) AND (p.profile_id = auth.uid()))))));



  create policy "department_categories_read"
  on "public"."department_categories"
  as permissive
  for select
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.departments d
  WHERE ((d.id = department_categories.department_id) AND public.is_community_member(d.community_id)))));



  create policy "department_categories_write"
  on "public"."department_categories"
  as permissive
  for all
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.departments d
  WHERE ((d.id = department_categories.department_id) AND public.is_community_admin(d.community_id)))))
with check ((EXISTS ( SELECT 1
   FROM public.departments d
  WHERE ((d.id = department_categories.department_id) AND public.is_community_admin(d.community_id)))));



  create policy "department_skills_read"
  on "public"."department_skills"
  as permissive
  for select
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.departments d
  WHERE ((d.id = department_skills.department_id) AND public.is_community_member(d.community_id)))));



  create policy "departments_admin_write"
  on "public"."departments"
  as permissive
  for all
  to authenticated
using (public.is_community_admin(community_id))
with check (public.is_community_admin(community_id));



  create policy "departments_read"
  on "public"."departments"
  as permissive
  for select
  to authenticated
using (public.is_community_member(community_id));



  create policy "departments_service_application_read"
  on "public"."departments"
  as permissive
  for select
  to authenticated
using ((EXISTS ( SELECT 1
   FROM (public.service_applications a
     JOIN public.service_providers p ON ((p.id = a.service_provider_id)))
  WHERE ((a.department_id = departments.id) AND (p.profile_id = auth.uid())))));



  create policy "dm_messages_read"
  on "public"."dm_messages"
  as permissive
  for select
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.dm_threads t
  WHERE ((t.id = dm_messages.thread_id) AND ((t.participant_a_profile_id = auth.uid()) OR (t.participant_b_profile_id = auth.uid()))))));



  create policy "invoice_line_items_read"
  on "public"."invoice_line_items"
  as permissive
  for select
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.invoices i
  WHERE ((i.id = invoice_line_items.invoice_id) AND (public.is_community_admin(i.community_id) OR public.is_own_invoice(i.id))))));



  create policy "invoices_admin_write"
  on "public"."invoices"
  as permissive
  for all
  to authenticated
using (public.is_community_admin(community_id))
with check (public.is_community_admin(community_id));



  create policy "invoices_read"
  on "public"."invoices"
  as permissive
  for select
  to authenticated
using ((public.is_community_admin(community_id) OR (EXISTS ( SELECT 1
   FROM public.community_memberships m
  WHERE ((m.id = invoices.membership_id) AND (m.profile_id = auth.uid())))) OR (EXISTS ( SELECT 1
   FROM (public.unit_residencies r
     JOIN public.community_memberships m ON ((m.id = r.membership_id)))
  WHERE ((r.unit_id = invoices.unit_id) AND (r.ended_at IS NULL) AND (m.profile_id = auth.uid()))))));



  create policy "material_movements_read"
  on "public"."material_movements"
  as permissive
  for select
  to authenticated
using ((public.is_community_security(community_id) OR public.is_community_admin(community_id)));



  create policy "notices_admin_write"
  on "public"."notices"
  as permissive
  for all
  to authenticated
using (public.is_community_admin(community_id))
with check (public.is_community_admin(community_id));



  create policy "notices_read"
  on "public"."notices"
  as permissive
  for select
  to authenticated
using (((public.is_community_member(community_id) AND (published_at IS NOT NULL)) OR public.is_community_admin(community_id) OR (EXISTS ( SELECT 1
   FROM public.community_memberships m
  WHERE ((m.community_id = notices.community_id) AND (m.profile_id = auth.uid()) AND (m.role = 'manager'::public.membership_role) AND (m.status = 'active'::public.membership_status) AND (m.ended_at IS NULL))))));



  create policy "offline_reconcile_log_read"
  on "public"."offline_reconcile_log"
  as permissive
  for select
  to authenticated
using (public.is_community_admin(community_id));



  create policy "payment_events_read"
  on "public"."payment_events"
  as permissive
  for select
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.payments p
  WHERE ((p.id = payment_events.payment_id) AND public.is_community_admin(p.community_id)))));



  create policy "payments_read"
  on "public"."payments"
  as permissive
  for select
  to authenticated
using ((public.is_community_admin(community_id) OR (payer_profile_id = auth.uid()) OR ((invoice_id IS NOT NULL) AND public.is_own_invoice(invoice_id))));



  create policy "security_incidents_read"
  on "public"."security_incidents"
  as permissive
  for select
  to authenticated
using ((public.is_community_security(community_id) OR public.is_community_admin(community_id)));



  create policy "security_posts_read"
  on "public"."security_posts"
  as permissive
  for select
  to authenticated
using ((public.is_community_security(community_id) OR public.is_community_admin(community_id)));



  create policy "security_shifts_read"
  on "public"."security_shifts"
  as permissive
  for select
  to authenticated
using ((public.is_community_security(community_id) OR public.is_community_admin(community_id) OR public.is_own_staff_assignment(staff_assignment_id)));



  create policy "service_applications_read"
  on "public"."service_applications"
  as permissive
  for select
  to authenticated
using ((public.can_hire_for_department(department_id) OR (EXISTS ( SELECT 1
   FROM public.service_providers p
  WHERE ((p.id = service_applications.service_provider_id) AND (p.profile_id = auth.uid()))))));



  create policy "staff_assignments_admin_write"
  on "public"."staff_assignments"
  as permissive
  for all
  to authenticated
using (public.is_community_admin(community_id))
with check (public.is_community_admin(community_id));



  create policy "staff_assignments_read"
  on "public"."staff_assignments"
  as permissive
  for select
  to authenticated
using ((public.is_community_member(community_id) OR (EXISTS ( SELECT 1
   FROM public.service_providers p
  WHERE ((p.id = staff_assignments.service_provider_id) AND (p.profile_id = auth.uid()))))));



  create policy "staff_departures_read"
  on "public"."staff_departures"
  as permissive
  for select
  to authenticated
using ((public.is_community_admin(community_id) OR public.can_supervise_department(department_id) OR public.is_own_staff_assignment(staff_assignment_id)));



  create policy "staff_invitations_read"
  on "public"."staff_invitations"
  as permissive
  for select
  to authenticated
using (public.is_community_member(community_id));



  create policy "unit_contacts_read"
  on "public"."unit_contacts"
  as permissive
  for select
  to authenticated
using ((public.is_community_admin(community_id) OR (EXISTS ( SELECT 1
   FROM (public.unit_residencies r
     JOIN public.community_memberships m ON ((m.id = r.membership_id)))
  WHERE ((r.unit_id = unit_contacts.unit_id) AND (r.ended_at IS NULL) AND (m.profile_id = auth.uid()))))));



  create policy "unit_residencies_read"
  on "public"."unit_residencies"
  as permissive
  for select
  to authenticated
using ((public.is_own_membership(membership_id) OR public.is_current_unit_resident(unit_id) OR (EXISTS ( SELECT 1
   FROM public.community_memberships m
  WHERE ((m.id = unit_residencies.membership_id) AND public.is_community_admin(m.community_id))))));



  create policy "visitor_events_read"
  on "public"."visitor_events"
  as permissive
  for select
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.visitor_requests v
  WHERE ((v.id = visitor_events.visitor_request_id) AND (public.is_own_membership(v.requested_by_membership_id) OR public.is_community_admin(v.community_id) OR public.is_community_security(v.community_id))))));



  create policy "visitor_requests_read"
  on "public"."visitor_requests"
  as permissive
  for select
  to authenticated
using ((public.is_own_membership(requested_by_membership_id) OR public.is_community_admin(community_id) OR public.is_community_security(community_id)));



  create policy "water_tanker_logs_read"
  on "public"."water_tanker_logs"
  as permissive
  for select
  to authenticated
using ((public.is_community_security(community_id) OR public.is_community_admin(community_id)));



  create policy "work_order_assignments_read"
  on "public"."work_order_assignments"
  as permissive
  for select
  to authenticated
using (public.can_read_work_order(work_order_id));



  create policy "work_orders_read"
  on "public"."work_orders"
  as permissive
  for select
  to authenticated
using (public.can_read_work_order(id));



  create policy "worker_availability_rules_read"
  on "public"."worker_availability_rules"
  as permissive
  for select
  to authenticated
using ((((staff_assignment_id IS NOT NULL) AND (public.is_own_staff_assignment(staff_assignment_id) OR (EXISTS ( SELECT 1
   FROM public.staff_assignments sa
  WHERE ((sa.id = worker_availability_rules.staff_assignment_id) AND public.can_supervise_department(sa.department_id)))))) OR ((service_provider_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM public.service_providers p
  WHERE ((p.id = worker_availability_rules.service_provider_id) AND (p.profile_id = auth.uid())))))));



  create policy "worker_unavailability_read"
  on "public"."worker_unavailability"
  as permissive
  for select
  to authenticated
using ((((staff_assignment_id IS NOT NULL) AND (public.is_own_staff_assignment(staff_assignment_id) OR (EXISTS ( SELECT 1
   FROM public.staff_assignments sa
  WHERE ((sa.id = worker_unavailability.staff_assignment_id) AND public.can_supervise_department(sa.department_id)))))) OR ((service_provider_id IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM public.service_providers p
  WHERE ((p.id = worker_unavailability.service_provider_id) AND (p.profile_id = auth.uid())))))));


CREATE TRIGGER access_requests_set_updated_at BEFORE UPDATE ON public.access_requests FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER amenities_set_updated_at BEFORE UPDATE ON public.amenities FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER buildings_set_updated_at BEFORE UPDATE ON public.buildings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER communities_set_updated_at BEFORE UPDATE ON public.communities FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER community_admin_terms_validate BEFORE INSERT OR UPDATE ON public.community_admin_terms FOR EACH ROW EXECUTE FUNCTION public.validate_community_admin_term();

CREATE TRIGGER community_features_set_updated_at BEFORE UPDATE ON public.community_features FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER community_memberships_set_updated_at BEFORE UPDATE ON public.community_memberships FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER community_registration_requests_set_updated_at BEFORE UPDATE ON public.community_registration_requests FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER complaints_set_updated_at BEFORE UPDATE ON public.complaints FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER departments_set_updated_at BEFORE UPDATE ON public.departments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER invoices_set_updated_at BEFORE UPDATE ON public.invoices FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER amenity_booking_occurrences_set_updated_at BEFORE UPDATE ON public.legacy_amenity_booking_occurrences FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER amenity_booking_series_set_updated_at BEFORE UPDATE ON public.legacy_amenity_booking_series FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER dashboard_sse_amenity_booking_series AFTER INSERT OR DELETE OR UPDATE ON public.legacy_amenity_booking_series FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER notices_set_updated_at BEFORE UPDATE ON public.notices FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER policies_set_updated_at BEFORE UPDATE ON public.policies FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER profiles_set_updated_at BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER resident_invites_set_updated_at BEFORE UPDATE ON public.resident_invites FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER saved_visitors_set_updated_at BEFORE UPDATE ON public.saved_visitors FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER staff_assignments_set_updated_at BEFORE UPDATE ON public.staff_assignments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER unit_residencies_set_updated_at BEFORE UPDATE ON public.unit_residencies FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER units_set_updated_at BEFORE UPDATE ON public.units FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER dashboard_sse_visitor_access_requests AFTER INSERT OR DELETE OR UPDATE ON public.visitor_access_requests FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER visitor_access_requests_set_updated_at BEFORE UPDATE ON public.visitor_access_requests FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER access_request_sse AFTER INSERT OR UPDATE ON public.access_requests FOR EACH ROW EXECUTE FUNCTION public.emit_access_request_sse_event();

CREATE TRIGGER dashboard_sse_access_requests AFTER INSERT OR DELETE OR UPDATE ON public.access_requests FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER amenities_sse AFTER INSERT OR DELETE OR UPDATE ON public.amenities FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER amenities_sync_status BEFORE INSERT OR UPDATE ON public.amenities FOR EACH ROW EXECUTE FUNCTION public.sync_amenity_status();

CREATE TRIGGER dashboard_sse_amenities AFTER INSERT OR DELETE OR UPDATE ON public.amenities FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER amenity_bookings_sse AFTER INSERT OR DELETE OR UPDATE ON public.amenity_bookings FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER community_billing_settings_set_updated_at BEFORE UPDATE ON public.community_billing_settings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER dashboard_sse_community_billing_settings AFTER INSERT OR DELETE OR UPDATE ON public.community_billing_settings FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER community_memberships_professional_mode BEFORE INSERT OR UPDATE OF role, status, ended_at ON public.community_memberships FOR EACH ROW EXECUTE FUNCTION public.enforce_professional_membership_mode();

CREATE TRIGGER dashboard_sse_community_memberships AFTER INSERT OR DELETE OR UPDATE ON public.community_memberships FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER community_settings_set_updated_at BEFORE UPDATE ON public.community_settings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER dashboard_sse_community_settings AFTER INSERT OR DELETE OR UPDATE ON public.community_settings FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER complaint_categories_link_skill BEFORE INSERT OR UPDATE OF name ON public.complaint_categories FOR EACH ROW EXECUTE FUNCTION public.link_category_skill();

CREATE TRIGGER complaint_comments_sse AFTER INSERT OR DELETE OR UPDATE ON public.complaint_comments FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER complaints_department_live_work_guard BEFORE UPDATE OF department_id ON public.complaints FOR EACH ROW EXECUTE FUNCTION public.guard_complaint_department_transfer();

CREATE TRIGGER complaints_on_resolved AFTER UPDATE OF status ON public.complaints FOR EACH ROW EXECUTE FUNCTION public.on_complaint_resolved();

CREATE TRIGGER complaints_sse AFTER INSERT OR DELETE OR UPDATE ON public.complaints FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER dashboard_sse_complaints AFTER INSERT OR DELETE OR UPDATE ON public.complaints FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER dashboard_sse_departments AFTER INSERT OR DELETE OR UPDATE ON public.departments FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER departments_sse AFTER INSERT OR DELETE OR UPDATE ON public.departments FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER departments_sync_status BEFORE INSERT OR UPDATE ON public.departments FOR EACH ROW EXECUTE FUNCTION public.sync_department_status();

CREATE TRIGGER dashboard_sse_invoices AFTER INSERT OR DELETE OR UPDATE ON public.invoices FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER invoices_sse AFTER INSERT OR DELETE OR UPDATE ON public.invoices FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER dashboard_sse_notices AFTER INSERT OR DELETE OR UPDATE ON public.notices FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER notices_notify_residents AFTER INSERT ON public.notices FOR EACH ROW WHEN ((new.published_at IS NOT NULL)) EXECUTE FUNCTION public.emit_notice_published();

CREATE TRIGGER notifications_sse_event AFTER INSERT ON public.notifications FOR EACH ROW EXECUTE FUNCTION public.emit_notification_sse_event();

CREATE TRIGGER dashboard_sse_payments AFTER INSERT OR DELETE OR UPDATE ON public.payments FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER payments_sse AFTER INSERT OR DELETE OR UPDATE ON public.payments FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER security_shifts_block_departing BEFORE INSERT OR UPDATE OF status, staff_assignment_id, starts_at ON public.security_shifts FOR EACH ROW EXECUTE FUNCTION public.block_departing_shift();

CREATE TRIGGER service_applications_notify_invited AFTER INSERT ON public.service_applications FOR EACH ROW WHEN ((new.direction = 'invited'::text)) EXECUTE FUNCTION public.emit_service_application_notice();

CREATE TRIGGER service_applications_notify_rejected AFTER UPDATE OF status ON public.service_applications FOR EACH ROW WHEN (((old.status = 'pending'::text) AND (new.status = 'rejected'::text) AND (new.direction = 'applied'::text))) EXECUTE FUNCTION public.emit_service_application_notice();

CREATE TRIGGER service_applications_set_updated_at BEFORE UPDATE ON public.service_applications FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER service_providers_set_updated_at BEFORE UPDATE ON public.service_providers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER staff_assignments_sse AFTER INSERT OR DELETE OR UPDATE ON public.staff_assignments FOR EACH ROW EXECUTE FUNCTION public.emit_dashboard_sse_event();

CREATE TRIGGER work_order_assignments_block_departing BEFORE INSERT OR UPDATE OF status, staff_assignment_id, scheduled_start_at ON public.work_order_assignments FOR EACH ROW EXECUTE FUNCTION public.block_departing_assignment();

CREATE TRIGGER work_order_assignments_open_chat AFTER INSERT OR UPDATE OF status ON public.work_order_assignments FOR EACH ROW WHEN ((new.status = 'accepted'::text)) EXECUTE FUNCTION public.open_accepted_work_order_thread();

CREATE TRIGGER work_order_assignments_project_complaint AFTER INSERT ON public.work_order_assignments FOR EACH ROW WHEN ((new.status = 'offered'::text)) EXECUTE FUNCTION public.project_complaint_from_jobs();

CREATE TRIGGER work_orders_clear_complaint_pool_flag AFTER INSERT ON public.work_orders FOR EACH ROW EXECUTE FUNCTION public.clear_complaint_pool_flag();

CREATE TRIGGER work_orders_lock_dm_threads AFTER INSERT OR UPDATE OF status ON public.work_orders FOR EACH ROW EXECUTE FUNCTION public.lock_work_order_threads();

CREATE TRIGGER work_orders_project_complaint AFTER UPDATE OF status ON public.work_orders FOR EACH ROW WHEN ((new.status = ANY (ARRAY['in_progress'::text, 'completed'::text]))) EXECUTE FUNCTION public.project_complaint_from_jobs();

CREATE TRIGGER work_orders_set_updated_at BEFORE UPDATE ON public.work_orders FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER work_orders_sync_dispatch AFTER INSERT OR UPDATE ON public.work_orders FOR EACH ROW EXECUTE FUNCTION public.sync_dispatch_tasks();

CREATE TRIGGER work_orders_terminal_complaint_guard BEFORE INSERT ON public.work_orders FOR EACH ROW EXECUTE FUNCTION public.guard_live_work_order_complaint();

CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


  create policy "community_media_delete"
  on "storage"."objects"
  as permissive
  for delete
  to authenticated
using (((bucket_id = 'community-media'::text) AND public.current_user_has_community_role(((storage.foldername(name))[1])::uuid, ARRAY['manager'::public.membership_role, 'admin'::public.membership_role])));



  create policy "community_media_insert"
  on "storage"."objects"
  as permissive
  for insert
  to authenticated
with check (((bucket_id = 'community-media'::text) AND public.current_user_is_active_member(((storage.foldername(name))[1])::uuid)));



  create policy "community_media_select"
  on "storage"."objects"
  as permissive
  for select
  to authenticated
using (((bucket_id = 'community-media'::text) AND public.current_user_is_active_member(((storage.foldername(name))[1])::uuid)));



