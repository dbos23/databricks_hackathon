-- @param business_name STRING
WITH recent_reviews AS (
  -- 1. Grab the latest 100 reviews
  SELECT r.full_text 
  FROM genieology.gold.reviews_and_tips r
  JOIN genieology.gold.business b ON r.business_id = b.business_id
  WHERE b.business_name = :business_name
  ORDER BY r.posted_at DESC
  LIMIT 100
),
sentiment_data AS (
  -- 2. Ask the AI to categorize each one
  SELECT ai_analyze_sentiment(full_text) AS sentiment_category
  FROM recent_reviews
)
-- 3. Group and count the final text results
SELECT 
  sentiment_category, 
  COUNT(*) AS category_count
FROM sentiment_data
GROUP BY sentiment_category
ORDER BY category_count DESC