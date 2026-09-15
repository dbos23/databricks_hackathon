create or refresh materialized view gold.reviews_and_tips_chunked as (
    select
        text_id,
        posexplode(genieology.dev.chunk_by_size(full_text, 150, 20)) as (chunk_id, text_chunk) 
    from genieology.gold.reviews_and_tips
);