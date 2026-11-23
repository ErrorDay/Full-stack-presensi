create extension if not exists vector;

-- Data lama disimpan sebagai JSON/TEXT. Konversi sekali menjadi pgvector.
alter table public.face_embeddings
    alter column embedding type vector(512)
    using embedding::vector(512);

create index if not exists face_embeddings_embedding_hnsw_idx
    on public.face_embeddings
    using hnsw (embedding vector_cosine_ops);

create or replace function public.cari_siswa_terdekat(
    query_embedding vector(512),
    match_threshold double precision default 0.4,
    match_count integer default 1
)
returns table (
    siswa_id integer,
    nama text,
    cosine_distance double precision
)
language sql
stable
as $$
    select
        fe.siswa_id,
        s.nama,
        (fe.embedding <=> query_embedding)::double precision as cosine_distance
    from public.face_embeddings fe
    join public.siswa s on s.id = fe.siswa_id
    where s.status = 'AKTIF'
      and (fe.embedding <=> query_embedding) <= match_threshold
    order by fe.embedding <=> query_embedding
    limit greatest(match_count, 1);
$$;
