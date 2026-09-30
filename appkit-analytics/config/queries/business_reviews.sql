-- @param business_name STRING
SELECT 
  r.text_id,
  r.business_id,
  r.full_text,
  r.posted_at,
  r.type
FROM genieology.gold.reviews_and_tips r
JOIN genieology.gold.business b 
  ON r.business_id = b.business_id
WHERE b.business_name = :business_name
LIMIT 50