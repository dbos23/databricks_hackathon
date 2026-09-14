create or refresh materialized view genieology.gold.business as (
    select
        dim_business.business_id,
        dim_business.business_name,
        dim_business.subcategories,
        dim_business.city,
        dim_business.state,
        dim_business.address,
        dim_business.postal_code,
        dim_business.latitude,
        dim_business.longitude,
        dim_business.review_count,
        dim_business.rating,
        fct_checkins.checkin_count,
        fct_checkins.first_checkin,
        fct_checkins.latest_checkin
    from genieology.silver.dim_business
        inner join genieology.silver.fct_checkins
            on dim_business.business_id = fct_checkins.business_id
);