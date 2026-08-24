--
-- PostgreSQL database dump
--

\restrict AYtbCR98TdYDVORSguAXcSXNGbaaM5mmQq3af4003iyvtJy1JiSdIBr54p9jZ1k

-- Dumped from database version 16.15
-- Dumped by pg_dump version 16.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: billing_cycle; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.billing_cycle AS ENUM (
    'MONTHLY',
    'QUARTERLY'
);


--
-- Name: complaint_priority; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.complaint_priority AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH'
);


--
-- Name: complaint_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.complaint_status AS ENUM (
    'OPEN',
    'IN_PROGRESS',
    'RESOLVED'
);


--
-- Name: document_entity; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.document_entity AS ENUM (
    'COMPLAINT',
    'INVOICE',
    'EXPENSE'
);


--
-- Name: expense_category; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.expense_category AS ENUM (
    'ELECTRICITY',
    'WATER',
    'SECURITY',
    'REPAIRS',
    'CLEANING',
    'SALARIES',
    'OTHER'
);


--
-- Name: expense_frequency; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.expense_frequency AS ENUM (
    'MONTHLY',
    'QUARTERLY',
    'ANNUAL'
);


--
-- Name: fund_transaction_source; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.fund_transaction_source AS ENUM (
    'MAINTENANCE_PAYMENT',
    'EXPENSE',
    'MANUAL_CREDIT',
    'MANUAL_DEBIT',
    'ADJUSTMENT'
);


--
-- Name: fund_transaction_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.fund_transaction_type AS ENUM (
    'CREDIT',
    'DEBIT'
);


--
-- Name: invoice_item_kind; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.invoice_item_kind AS ENUM (
    'CHARGE',
    'LATE_FEE'
);


--
-- Name: invoice_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.invoice_status AS ENUM (
    'PENDING',
    'PARTIALLY_PAID',
    'PAID',
    'OVERDUE',
    'CANCELLED'
);


--
-- Name: notification_channel; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.notification_channel AS ENUM (
    'EMAIL'
);


--
-- Name: notification_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.notification_status AS ENUM (
    'PENDING',
    'SENT',
    'FAILED'
);


--
-- Name: payment_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.payment_status AS ENUM (
    'PENDING',
    'SUCCESS',
    'FAILED'
);


--
-- Name: reconciliation_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.reconciliation_status AS ENUM (
    'MATCHED',
    'UNMATCHED',
    'MANUAL_REVIEW'
);


--
-- Name: user_role; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_role AS ENUM (
    'RESIDENT',
    'ADMIN',
    'COMMITTEE',
    'ACCOUNTANT'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
--

    version_num character varying(32) NOT NULL
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id uuid NOT NULL,
    actor_id uuid,
    action character varying(100) NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id uuid,
    old_value jsonb,
    new_value jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: complaint_sla; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.complaint_sla (
    id uuid NOT NULL,
    complaint_id uuid NOT NULL,
    target_days integer NOT NULL,
    due_at timestamp without time zone NOT NULL,
    breached boolean DEFAULT false NOT NULL
);


--
-- Name: complaint_status_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.complaint_status_history (
    id uuid NOT NULL,
    complaint_id uuid NOT NULL,
    status public.complaint_status NOT NULL,
    changed_by uuid NOT NULL,
    note text,
    changed_at timestamp without time zone NOT NULL
);


--
-- Name: complaints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.complaints (
    id uuid NOT NULL,
    resident_id uuid NOT NULL,
    category character varying(100) NOT NULL,
    description text NOT NULL,
    photo_url text,
    status public.complaint_status NOT NULL,
    priority public.complaint_priority NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    resolved_at timestamp without time zone
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id uuid NOT NULL,
    entity_type public.document_entity NOT NULL,
    entity_id uuid NOT NULL,
    uploaded_by uuid,
    file_url character varying(500) NOT NULL,
    original_filename character varying(255) NOT NULL,
    content_type character varying(100) NOT NULL,
    size_bytes bigint NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: expenses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.expenses (
    id uuid NOT NULL,
    title character varying(200) NOT NULL,
    description text,
    category public.expense_category NOT NULL,
    amount numeric(12,2) NOT NULL,
    expense_date date NOT NULL,
    vendor character varying(200),
    receipt_file_path character varying(500),
    source_recurring_id uuid,
    generated_period character varying(7),
    created_by uuid,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: fund_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fund_transactions (
    id uuid NOT NULL,
    fund_id uuid NOT NULL,
    type public.fund_transaction_type NOT NULL,
    source public.fund_transaction_source NOT NULL,
    amount numeric(12,2) NOT NULL,
    balance_after numeric(14,2) NOT NULL,
    reference_id uuid,
    description character varying(500),
    created_by uuid,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: invoice_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_items (
    id uuid NOT NULL,
    invoice_id uuid NOT NULL,
    kind public.invoice_item_kind NOT NULL,
    description character varying(255) NOT NULL,
    unit_price numeric(12,2) NOT NULL,
    amount numeric(12,2) NOT NULL
);


--
-- Name: invoices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoices (
    id uuid NOT NULL,
    invoice_number character varying(30) NOT NULL,
    resident_id uuid NOT NULL,
    plan_id uuid,
    billing_period character varying(7) NOT NULL,
    period_start date,
    subtotal numeric(12,2) NOT NULL,
    late_fee numeric(12,2) NOT NULL,
    total_amount numeric(12,2) NOT NULL,
    amount_paid numeric(12,2) NOT NULL,
    status public.invoice_status NOT NULL,
    due_date date NOT NULL,
    notes text,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: maintenance_funds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maintenance_funds (
    id uuid NOT NULL,
    name character varying(150) NOT NULL,
    balance numeric(14,2) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: maintenance_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maintenance_plans (
    id uuid NOT NULL,
    name character varying(150) NOT NULL,
    description text,
    amount numeric(12,2) NOT NULL,
    cycle public.billing_cycle NOT NULL,
    due_day_of_month integer NOT NULL,
    late_fee_amount numeric(12,2) DEFAULT 0 NOT NULL,
    late_fee_grace_days integer DEFAULT 0 NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: notices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notices (
    id uuid NOT NULL,
    title character varying(200) NOT NULL,
    content text NOT NULL,
    is_important boolean NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id uuid NOT NULL,
    user_id uuid,
    recipient_email character varying(255) NOT NULL,
    channel public.notification_channel NOT NULL,
    event character varying(50) NOT NULL,
    payload jsonb,
    subject character varying(300) NOT NULL,
    body text NOT NULL,
    status public.notification_status NOT NULL,
    provider_message_id character varying(255),
    error text,
    sent_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: payment_reconciliations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_reconciliations (
    id uuid NOT NULL,
    payment_id uuid NOT NULL,
    status public.reconciliation_status NOT NULL,
    matched_by uuid,
    note character varying(500),
    reconciled_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payments (
    id uuid NOT NULL,
    invoice_id uuid,
    resident_id uuid NOT NULL,
    provider character varying(30) NOT NULL,
    provider_order_id character varying(100),
    provider_payment_id character varying(100),
    amount numeric(12,2) NOT NULL,
    currency character varying(3) NOT NULL,
    status public.payment_status NOT NULL,
    signature_verified boolean DEFAULT false NOT NULL,
    failure_reason character varying(255),
    paid_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: recurring_expenses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recurring_expenses (
    id uuid NOT NULL,
    title character varying(200) NOT NULL,
    category public.expense_category NOT NULL,
    amount numeric(12,2) NOT NULL,
    vendor character varying(200),
    frequency public.expense_frequency NOT NULL,
    day_of_month integer NOT NULL,
    next_run_date date NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    last_generated_period character varying(7),
    created_at timestamp without time zone NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    email character varying(255) NOT NULL,
    password_hash text NOT NULL,
    role public.user_role NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
--



--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: complaint_sla complaint_sla_complaint_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_sla
    ADD CONSTRAINT complaint_sla_complaint_id_key UNIQUE (complaint_id);


--
-- Name: complaint_sla complaint_sla_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_sla
    ADD CONSTRAINT complaint_sla_pkey PRIMARY KEY (id);


--
-- Name: complaint_status_history complaint_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_status_history
    ADD CONSTRAINT complaint_status_history_pkey PRIMARY KEY (id);


--
-- Name: complaints complaints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaints
    ADD CONSTRAINT complaints_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: expenses expenses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_pkey PRIMARY KEY (id);


--
-- Name: fund_transactions fund_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fund_transactions
    ADD CONSTRAINT fund_transactions_pkey PRIMARY KEY (id);


--
-- Name: invoice_items invoice_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_items
    ADD CONSTRAINT invoice_items_pkey PRIMARY KEY (id);


--
-- Name: invoices invoices_invoice_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_invoice_number_key UNIQUE (invoice_number);


--
-- Name: invoices invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_pkey PRIMARY KEY (id);


--
-- Name: maintenance_funds maintenance_funds_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_funds
    ADD CONSTRAINT maintenance_funds_name_key UNIQUE (name);


--
-- Name: maintenance_funds maintenance_funds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_funds
    ADD CONSTRAINT maintenance_funds_pkey PRIMARY KEY (id);


--
-- Name: maintenance_plans maintenance_plans_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_plans
    ADD CONSTRAINT maintenance_plans_name_key UNIQUE (name);


--
-- Name: maintenance_plans maintenance_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_plans
    ADD CONSTRAINT maintenance_plans_pkey PRIMARY KEY (id);


--
-- Name: notices notices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notices
    ADD CONSTRAINT notices_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: payment_reconciliations payment_reconciliations_payment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_reconciliations
    ADD CONSTRAINT payment_reconciliations_payment_id_key UNIQUE (payment_id);


--
-- Name: payment_reconciliations payment_reconciliations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_reconciliations
    ADD CONSTRAINT payment_reconciliations_pkey PRIMARY KEY (id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (id);


--
-- Name: payments payments_provider_payment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_provider_payment_id_key UNIQUE (provider_payment_id);


--
-- Name: recurring_expenses recurring_expenses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_expenses
    ADD CONSTRAINT recurring_expenses_pkey PRIMARY KEY (id);


--
-- Name: invoices uq_invoice_resident_plan_period; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT uq_invoice_resident_plan_period UNIQUE (resident_id, plan_id, billing_period);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_audit_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_created_at ON public.audit_logs USING btree (created_at);


--
-- Name: ix_complaint_sla_due_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_complaint_sla_due_at ON public.complaint_sla USING btree (due_at);


--
-- Name: ix_complaint_status_history_complaint_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_complaint_status_history_complaint_id ON public.complaint_status_history USING btree (complaint_id);


--
-- Name: ix_complaints_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_complaints_category ON public.complaints USING btree (category);


--
-- Name: ix_complaints_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_complaints_created_at ON public.complaints USING btree (created_at);


--
-- Name: ix_complaints_resident_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_complaints_resident_id ON public.complaints USING btree (resident_id);


--
-- Name: ix_complaints_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_complaints_status ON public.complaints USING btree (status);


--
-- Name: ix_documents_entity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_entity_id ON public.documents USING btree (entity_id);


--
-- Name: ix_documents_entity_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_entity_type ON public.documents USING btree (entity_type);


--
-- Name: ix_expenses_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expenses_category ON public.expenses USING btree (category);


--
-- Name: ix_expenses_expense_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expenses_expense_date ON public.expenses USING btree (expense_date);


--
-- Name: ix_fund_transactions_fund_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fund_transactions_fund_id ON public.fund_transactions USING btree (fund_id);


--
-- Name: ix_invoice_items_invoice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_items_invoice_id ON public.invoice_items USING btree (invoice_id);


--
-- Name: ix_invoices_billing_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoices_billing_period ON public.invoices USING btree (billing_period);


--
-- Name: ix_invoices_resident_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoices_resident_id ON public.invoices USING btree (resident_id);


--
-- Name: ix_invoices_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoices_status ON public.invoices USING btree (status);


--
-- Name: ix_notices_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notices_created_at ON public.notices USING btree (created_at);


--
-- Name: ix_notifications_event; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_event ON public.notifications USING btree (event);


--
-- Name: ix_notifications_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_status ON public.notifications USING btree (status);


--
-- Name: ix_notifications_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_user_id ON public.notifications USING btree (user_id);


--
-- Name: ix_payment_reconciliations_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_reconciliations_status ON public.payment_reconciliations USING btree (status);


--
-- Name: ix_payments_invoice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payments_invoice_id ON public.payments USING btree (invoice_id);


--
-- Name: ix_payments_provider_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payments_provider_order_id ON public.payments USING btree (provider_order_id);


--
-- Name: ix_payments_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payments_status ON public.payments USING btree (status);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: audit_logs audit_logs_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id);


--
-- Name: complaint_sla complaint_sla_complaint_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_sla
    ADD CONSTRAINT complaint_sla_complaint_id_fkey FOREIGN KEY (complaint_id) REFERENCES public.complaints(id) ON DELETE CASCADE;


--
-- Name: complaint_status_history complaint_status_history_changed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_status_history
    ADD CONSTRAINT complaint_status_history_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES public.users(id);


--
-- Name: complaint_status_history complaint_status_history_complaint_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_status_history
    ADD CONSTRAINT complaint_status_history_complaint_id_fkey FOREIGN KEY (complaint_id) REFERENCES public.complaints(id) ON DELETE CASCADE;


--
-- Name: complaints complaints_resident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaints
    ADD CONSTRAINT complaints_resident_id_fkey FOREIGN KEY (resident_id) REFERENCES public.users(id);


--
-- Name: documents documents_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id);


--
-- Name: expenses expenses_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: expenses expenses_source_recurring_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_source_recurring_id_fkey FOREIGN KEY (source_recurring_id) REFERENCES public.recurring_expenses(id);


--
-- Name: fund_transactions fund_transactions_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fund_transactions
    ADD CONSTRAINT fund_transactions_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: fund_transactions fund_transactions_fund_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fund_transactions
    ADD CONSTRAINT fund_transactions_fund_id_fkey FOREIGN KEY (fund_id) REFERENCES public.maintenance_funds(id);


--
-- Name: invoice_items invoice_items_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_items
    ADD CONSTRAINT invoice_items_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.invoices(id) ON DELETE CASCADE;


--
-- Name: invoices invoices_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.maintenance_plans(id);


--
-- Name: invoices invoices_resident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_resident_id_fkey FOREIGN KEY (resident_id) REFERENCES public.users(id);


--
-- Name: notices notices_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notices
    ADD CONSTRAINT notices_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: payment_reconciliations payment_reconciliations_matched_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_reconciliations
    ADD CONSTRAINT payment_reconciliations_matched_by_fkey FOREIGN KEY (matched_by) REFERENCES public.users(id);


--
-- Name: payment_reconciliations payment_reconciliations_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_reconciliations
    ADD CONSTRAINT payment_reconciliations_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(id);


--
-- Name: payments payments_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.invoices(id);


--
-- Name: payments payments_resident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_resident_id_fkey FOREIGN KEY (resident_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--

\unrestrict AYtbCR98TdYDVORSguAXcSXNGbaaM5mmQq3af4003iyvtJy1JiSdIBr54p9jZ1k

