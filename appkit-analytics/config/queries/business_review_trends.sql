-- @param business_name STRING
SELECT 
  DATE_TRUNC('month', r.posted_at) AS review_month,
  COUNT(*) AS review_count
FROM genieology.gold.reviews_and_tips r
JOIN genieology.gold.business b ON r.business_id = b.business_id
WHERE b.business_name = :business_name
  AND r.posted_at IS NOT NULL
GROUP BY 1
ORDER BY 1 ASC