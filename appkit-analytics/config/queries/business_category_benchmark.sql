-- @param business_name STRING
WITH target_biz AS (
  SELECT category, rating FROM genieology.gold.business WHERE business_name = :business_name LIMIT 1
)
SELECT 
  t.rating AS business_rating,
  t.category,
  AVG(b.rating) AS category_avg,
  COUNT(b.business_id) AS category_size
FROM target_biz t
JOIN genieology.gold.business b ON b.category = t.category
GROUP BY 1, 2