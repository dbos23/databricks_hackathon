create or refresh streaming table genieology.silver.dim_business as (
    select
        business.business_id,
        name as business_name,
        categories as subcategories,
        city,
        state,
        address,
        postal_code,
        latitude,
        longitude,
        review_count,
        stars as rating,
        ai_classify(business_name || ': ' || subcategories, '[
            "Restaurants and cuisines",
            "Home and repair services",
            "Retail shopping",
            "Arts, culture, and entertainment",
            "Bars, breweries, and nightlife",
            "Health and medical",
            "Professional and financial services",
            "Beauty, spas, and personal care",
            "Education and family services",
            "Cafes, bakeries, and sweets",
            "Fitness and recreation",
            "Marketing, IT, and media",
            "Grocery markets and specialty food",
            "Travel and transportation",
            "Other"
            ]',
            map('version', '2.1', 'enableConfidenceScores', 'true'))
                ::struct<
                    error_message: string,
                    metadata: struct<
                        version: string
                        >,
                    response: array<struct<
                        confidence_score: float,
                        value: string
                >>>
            as raw_response,
        raw_response.error_message as error_message,
        raw_response.response[0].confidence_score as confidence_score,
        raw_response.response[0].value as category        
    from stream(genieology.bronze.business)
        inner join genieology.bronze.metro_areas
            on business.business_id = metro_areas.business_id
    where
        is_open = 1
        and metro_areas.metro_area = 'New Orleans'
);