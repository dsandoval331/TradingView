create table public.research_artifact_readback_chunks (
  artifact_id uuid not null references public.research_job_artifacts(artifact_id) on delete restrict,
  chunk_no integer not null check (chunk_no >= 0),
  size_bytes integer not null check (size_bytes between 1 and 1048576),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  content_base64 text not null,
  created_at timestamptz not null default now(),
  primary key (artifact_id, chunk_no),
  check (octet_length(decode(content_base64,'base64'))=size_bytes),
  check (encode(sha256(decode(content_base64,'base64')),'hex')=sha256)
);
alter table public.research_artifact_readback_chunks enable row level security;
revoke all on public.research_artifact_readback_chunks from public, anon, authenticated;
grant select, insert on public.research_artifact_readback_chunks to service_role;
comment on table public.research_artifact_readback_chunks is 'Private immutable 1MiB lossless readback chunks; verified complete physical/logical reconstruction. No scientific semantics.';
