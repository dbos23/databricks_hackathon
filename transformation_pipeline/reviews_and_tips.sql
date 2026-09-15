create or replace materialized view genieology.gold.reviews_and_tips as (
    -- business is already filtered to New Orleans so the inner joins filter this table to New Orleans too
    select
        review_id as text_id,
        fct_reviews.business_id,
        'review' as type,
        posted_at,
        review_text as full_text
    from genieology.silver.fct_reviews
        inner join genieology.gold.business
                on fct_reviews.business_id = business.business_id
    union
    select
        tip_id::varchar(50) as text_id,
        fct_tips.business_id,
        'tip' as type,
        posted_at,
        tip_text as full_text
    from genieology.silver.fct_tips
        inner join genieology.gold.business
                on fct_tips.business_id = business.business_id
);