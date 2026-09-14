create or replace materialized view genieology.gold.reviews_and_tips as (
    select
        review_id as text_id,
        business_id,
        'review' as type,
        posted_at,
        review_text as full_text
    from genieology.silver.fct_reviews
    union
    select
        tip_id::varchar(50) as text_id,
        business_id,
        'tip' as type,
        posted_at,
        tip_text as full_text
    from genieology.silver.fct_tips
);