create or refresh materialized view genieology.silver.dim_business as (
    select
        bronze.business.business_id,
        name as business_name,
        city,
        state,
        address,
        postal_code,
        latitude,
        longitude,
        review_count,
        stars as rating,
        categories as subcategories
    from genieology.bronze.business
        inner join genieology.bronze.metro_areas
            on business.business_id = genieology.bronze.metro_areas.business_id
    where
        is_open = 1
        and genieology.bronze.metro_areas.metro_area = 'New Orleans'
);