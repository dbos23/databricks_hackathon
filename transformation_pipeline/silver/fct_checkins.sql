create or refresh materialized view genieology.silver.fct_checkins
tblproperties (delta.enableRowTracking = true)
as (

    with

    exploded as (
        
        select
            business_id,
            explode(split(date, ',')) as checkin_date
        from genieology.bronze.checkin

    )

    select
        business_id,
        count(*) as checkin_count,
        min(checkin_date::timestamp)::date as first_checkin,
        max(checkin_date::timestamp)::date as latest_checkin
    from exploded
    group by business_id

);