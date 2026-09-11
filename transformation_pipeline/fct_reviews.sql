create or refresh materialized view genieology.silver.fct_reviews as (

    select
        review_id,
        business_id,
        date::timestamp as review_timestamp,
        stars as rating,
        text as review_text,
        cool as cool_count,
        funny as funny_count,
        useful as useful_count
    from genieology.bronze.review

);