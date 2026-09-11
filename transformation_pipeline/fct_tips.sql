create or refresh materialized view genieology.silver.fct_tips as (

    select
        row_number() over(order by business_id) as tip_id,
        business_id,
        date::timestamp as tip_timestamp,
        text as tip_text,
        compliment_count as tip_compliment_count
    from genieology.bronze.tip

);