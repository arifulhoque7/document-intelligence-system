-- Generated with pg_dump --schema-only from the running database. Source of truth: backend/app/models.py

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';
CREATE TABLE public.document_pages (
    id bigint NOT NULL,
    document_id uuid NOT NULL,
    page_no integer NOT NULL,
    sheet_name character varying(255),
    text text NOT NULL,
    method character varying(10) NOT NULL,
    ocr_confidence double precision,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, COALESCE(text, ''::text))) STORED NOT NULL
);
CREATE SEQUENCE public.document_pages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.document_pages_id_seq OWNED BY public.document_pages.id;
CREATE TABLE public.documents (
    id uuid NOT NULL,
    filename character varying(255) NOT NULL,
    file_type character varying(10) NOT NULL,
    size_bytes bigint NOT NULL,
    sha256 character varying(64) NOT NULL,
    storage_path character varying(500) NOT NULL,
    status character varying(20) NOT NULL,
    progress integer NOT NULL,
    page_count integer,
    error text,
    attempts integer NOT NULL,
    processing_ms integer,
    uploaded_by integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE public.invoice_revisions (
    id bigint NOT NULL,
    invoice_id uuid NOT NULL,
    version integer NOT NULL,
    source character varying(20) NOT NULL,
    data jsonb NOT NULL,
    changes jsonb NOT NULL,
    user_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE SEQUENCE public.invoice_revisions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.invoice_revisions_id_seq OWNED BY public.invoice_revisions.id;
CREATE TABLE public.invoices (
    id uuid NOT NULL,
    document_id uuid NOT NULL,
    seq integer NOT NULL,
    source_ref character varying(100),
    source_text text NOT NULL,
    invoice_number character varying(100),
    invoice_number_norm character varying(100),
    invoice_date date,
    supplier_name character varying(255),
    customer_name character varying(255),
    subtotal numeric(18,2),
    tax numeric(18,2),
    total numeric(18,2),
    currency character varying(3),
    line_items jsonb NOT NULL,
    confidence jsonb NOT NULL,
    status character varying(20) NOT NULL,
    needs_review boolean NOT NULL,
    extracted_by character varying(100),
    embedding public.vector(768),
    embedding_model character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    search_tsv tsvector GENERATED ALWAYS AS ((setweight(to_tsvector('simple'::regconfig, (((((COALESCE(invoice_number, ''::character varying))::text || ' '::text) || (COALESCE(supplier_name, ''::character varying))::text) || ' '::text) || (COALESCE(customer_name, ''::character varying))::text)), 'A'::"char") || setweight(to_tsvector('simple'::regconfig, COALESCE(source_text, ''::text)), 'B'::"char"))) STORED NOT NULL
);
CREATE TABLE public.processing_events (
    id bigint NOT NULL,
    document_id uuid NOT NULL,
    stage character varying(30) NOT NULL,
    status character varying(10) NOT NULL,
    message text,
    duration_ms integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE SEQUENCE public.processing_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.processing_events_id_seq OWNED BY public.processing_events.id;
CREATE TABLE public.provider_settings (
    provider character varying(20) NOT NULL,
    api_key_enc text,
    base_url character varying(500),
    model character varying(100),
    embedding_model character varying(100),
    active_llm boolean NOT NULL,
    active_embedding boolean NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;
CREATE TABLE public.validation_issues (
    id bigint NOT NULL,
    invoice_id uuid NOT NULL,
    code character varying(40) NOT NULL,
    field character varying(40),
    severity character varying(10) NOT NULL,
    message text NOT NULL
);
CREATE SEQUENCE public.validation_issues_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.validation_issues_id_seq OWNED BY public.validation_issues.id;
ALTER TABLE ONLY public.document_pages ALTER COLUMN id SET DEFAULT nextval('public.document_pages_id_seq'::regclass);
ALTER TABLE ONLY public.invoice_revisions ALTER COLUMN id SET DEFAULT nextval('public.invoice_revisions_id_seq'::regclass);
ALTER TABLE ONLY public.processing_events ALTER COLUMN id SET DEFAULT nextval('public.processing_events_id_seq'::regclass);
ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);
ALTER TABLE ONLY public.validation_issues ALTER COLUMN id SET DEFAULT nextval('public.validation_issues_id_seq'::regclass);
ALTER TABLE ONLY public.document_pages
    ADD CONSTRAINT document_pages_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.invoice_revisions
    ADD CONSTRAINT invoice_revisions_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.processing_events
    ADD CONSTRAINT processing_events_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.provider_settings
    ADD CONSTRAINT provider_settings_pkey PRIMARY KEY (provider);
ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);
ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.validation_issues
    ADD CONSTRAINT validation_issues_pkey PRIMARY KEY (id);
CREATE INDEX ix_document_pages_document_id ON public.document_pages USING btree (document_id);
CREATE INDEX ix_documents_created_at ON public.documents USING btree (created_at);
CREATE INDEX ix_documents_sha256 ON public.documents USING btree (sha256);
CREATE INDEX ix_documents_status ON public.documents USING btree (status);
CREATE INDEX ix_invoice_revisions_invoice_id ON public.invoice_revisions USING btree (invoice_id);
CREATE INDEX ix_invoices_document_id ON public.invoices USING btree (document_id);
CREATE INDEX ix_invoices_embedding ON public.invoices USING hnsw (embedding public.vector_cosine_ops);
CREATE INDEX ix_invoices_invoice_date ON public.invoices USING btree (invoice_date);
CREATE INDEX ix_invoices_invoice_number ON public.invoices USING btree (invoice_number);
CREATE INDEX ix_invoices_invoice_number_norm ON public.invoices USING btree (invoice_number_norm);
CREATE INDEX ix_invoices_needs_review ON public.invoices USING btree (needs_review);
CREATE INDEX ix_invoices_total ON public.invoices USING btree (total);
CREATE INDEX ix_invoices_tsv ON public.invoices USING gin (search_tsv);
CREATE INDEX ix_pages_tsv ON public.document_pages USING gin (tsv);
CREATE INDEX ix_processing_events_document_id ON public.processing_events USING btree (document_id);
CREATE INDEX ix_validation_issues_code ON public.validation_issues USING btree (code);
CREATE INDEX ix_validation_issues_invoice_id ON public.validation_issues USING btree (invoice_id);
ALTER TABLE ONLY public.document_pages
    ADD CONSTRAINT document_pages_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id);
ALTER TABLE ONLY public.invoice_revisions
    ADD CONSTRAINT invoice_revisions_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.invoices(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.invoice_revisions
    ADD CONSTRAINT invoice_revisions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);
ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.processing_events
    ADD CONSTRAINT processing_events_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.validation_issues
    ADD CONSTRAINT validation_issues_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.invoices(id) ON DELETE CASCADE;
