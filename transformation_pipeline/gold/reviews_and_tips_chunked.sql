create or refresh materialized view gold.reviews_and_tips_chunked as (
    select
        reviews_and_tips.text_id,
        chunks.pos as chunk_id,
        substring(reviews_and_tips.full_text, 1 + chunks.pos * 130, 150) as text_chunk
    from genieology.gold.reviews_and_tips
        join lateral posexplode(
            sequence(0, greatest(0, cast(ceil((length(reviews_and_tips.full_text) - 150.0) / 130.0) as int)))
            ) as chunks(pos, val)
    where reviews_and_tips.full_text is not null and length(reviews_and_tips.full_text) > 0
);