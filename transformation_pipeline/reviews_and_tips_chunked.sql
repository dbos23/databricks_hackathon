create or refresh materialized view gold.reviews_and_tips_chunked as (
-- business is already filtered to New Orleans so an inner join will also filter the reviews and tips
    with new_orleans_only as (
        select
            reviews_and_tips.text_id,
            reviews_and_tips.full_text
        from genieology.gold.reviews_and_tips
            inner join genieology.gold.business
                on reviews_and_tips.business_id = business.business_id
    )

    select
        text_id,
        posexplode(genieology.dev.chunk_by_size(full_text, 150, 20)) as (chunk_id, text_chunk) 
    from new_orleans_only
);